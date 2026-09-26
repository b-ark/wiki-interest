"""In-memory implementations of the ports for fast, deterministic tests.

Each fake mirrors the documented contract of its port (gap semantics, absence handling) and
records the calls it received so tests can assert on request counts and arguments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from pathlib import Path

from PIL import Image

from wiki_interest.adapters.fpdf_report import FpdfReportRenderer
from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.adapters.report_theme import ReportTheme
from wiki_interest.application.pipeline import Renderers
from wiki_interest.cli.container import Container
from wiki_interest.config import Settings
from wiki_interest.contracts.charts import ChartSpec
from wiki_interest.domain.models import (
    Access,
    Agent,
    EntityCandidate,
    Granularity,
    Point,
    Series,
    SeriesUnit,
    WikiProject,
    Window,
)
from wiki_interest.i18n import Translator
from wiki_interest.ports.mediawiki import Mention, PageInfo
from wiki_interest.ports.wikidata import EntitySummary

__all__ = [
    "AstronomyWorld",
    "BlankChartRenderer",
    "FakeClock",
    "FakeEntity",
    "FakeMediaWiki",
    "FakePage",
    "FakePageviews",
    "FakeWikidata",
    "astronomy_world",
    "fake_container",
]


# ---------------------------------------------------------------------------
# Wikidata
# ---------------------------------------------------------------------------


@dataclass
class FakeEntity:
    """A Wikidata item as the fake knows it."""

    qid: str
    labels: dict[str, str]
    sitelinks: dict[WikiProject, str] = field(default_factory=dict)
    claims: dict[str, list[str]] = field(default_factory=dict)
    description: str | None = None


class FakeWikidata:
    """Implements :class:`~wiki_interest.ports.wikidata.WikidataGateway` over a dict of entities."""

    def __init__(self, entities: Sequence[FakeEntity] = ()) -> None:
        self.entities: dict[str, FakeEntity] = {e.qid: e for e in entities}
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def add(self, entity: FakeEntity) -> FakeEntity:
        """Register an entity and return it (for fluent test setup)."""
        self.entities[entity.qid] = entity
        return entity

    def search_entities(
        self, query: str, language: str, *, limit: int = 5
    ) -> Sequence[EntityCandidate]:
        self.calls.append(("search_entities", (query, language, limit)))
        needle = query.casefold()
        hits: list[EntityCandidate] = []
        for entity in self.entities.values():
            label = entity.labels.get(language) or entity.labels.get("en", "")
            if needle in label.casefold():
                hits.append(
                    EntityCandidate(
                        qid=entity.qid,
                        label=label,
                        description=entity.description,
                        exact_label_match=label.casefold() == needle,
                    )
                )
        hits.sort(key=lambda c: (not c.exact_label_match, c.qid))
        return hits[:limit]

    def sitelinks(
        self, qids: Sequence[str], projects: Sequence[WikiProject]
    ) -> Mapping[str, Mapping[WikiProject, str]]:
        self.calls.append(("sitelinks", (tuple(qids), tuple(projects))))
        wanted = set(projects)
        return {
            qid: {p: t for p, t in self.entities[qid].sitelinks.items() if p in wanted}
            for qid in qids
            if qid in self.entities
        }

    def labels(
        self, qids: Sequence[str], language: str, *, fallback: bool = True
    ) -> Mapping[str, str]:
        self.calls.append(("labels", (tuple(qids), language)))
        out: dict[str, str] = {}
        for qid in qids:
            entity = self.entities.get(qid)
            if entity is None:
                continue
            label = entity.labels.get(language) or (entity.labels.get("en") if fallback else None)
            if label:
                out[qid] = label
        return out

    def summary(self, qid: str, language: str) -> EntitySummary | None:
        self.calls.append(("summary", (qid, language)))
        entity = self.entities.get(qid)
        if entity is None:
            return None
        return EntitySummary(
            qid=qid,
            label=entity.labels.get(language) or entity.labels.get("en"),
            description=entity.description,
            languages=tuple(p.language for p in entity.sitelinks),
        )

    def summaries(self, qids: Sequence[str], language: str) -> Mapping[str, EntitySummary]:
        self.calls.append(("summaries", (tuple(qids), language)))
        out: dict[str, EntitySummary] = {}
        for qid in qids:
            entity = self.entities.get(qid)
            if entity is not None:
                out[qid] = EntitySummary(
                    qid=qid,
                    label=entity.labels.get(language) or entity.labels.get("en"),
                    description=entity.description,
                    languages=tuple(p.language for p in entity.sitelinks),
                )
        return out

    def related_entities(
        self, qid: str, properties: Sequence[str]
    ) -> Mapping[str, tuple[str, ...]]:
        self.calls.append(("related_entities", (qid, tuple(properties))))
        claims = self.entities[qid].claims if qid in self.entities else {}
        return {prop: tuple(claims.get(prop, ())) for prop in properties}


# ---------------------------------------------------------------------------
# MediaWiki
# ---------------------------------------------------------------------------


@dataclass
class FakePage:
    """An existing article in one edition."""

    title: str
    qid: str | None = None
    redirects: list[str] = field(default_factory=list)
    redirect_sections: dict[str, str] = field(default_factory=dict)
    """Redirect title -> section of this page it points into."""


class FakeMediaWiki:
    """Implements :class:`~wiki_interest.ports.mediawiki.MediaWikiGateway` over dicts."""

    def __init__(self) -> None:
        self.pages: dict[WikiProject, dict[str, FakePage]] = {}
        self.search_index: dict[WikiProject, dict[str, list[str]]] = {}
        self.mention_index: dict[WikiProject, dict[str, list[Mention]]] = {}
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def add_page(self, project: WikiProject, page: FakePage) -> FakePage:
        """Register a page; its redirects become resolvable aliases."""
        self.pages.setdefault(project, {})[page.title] = page
        return page

    def add_search(self, project: WikiProject, query: str, titles: Sequence[str]) -> None:
        """Define full-text search results for an exact query string."""
        self.search_index.setdefault(project, {})[query] = list(titles)

    def add_mentions(self, project: WikiProject, phrase: str, mentions: Sequence[Mention]) -> None:
        """Define the articles that contain ``phrase`` verbatim."""
        self.mention_index.setdefault(project, {})[phrase] = list(mentions)

    def _target(self, project: WikiProject, title: str) -> tuple[FakePage, str | None] | None:
        pages = self.pages.get(project, {})
        if title in pages:
            return pages[title], None
        for page in pages.values():
            if title in page.redirects:
                return page, title
        return None

    def page_info(
        self, project: WikiProject, titles: Sequence[str]
    ) -> Mapping[str, PageInfo | None]:
        self.calls.append(("page_info", (project, tuple(titles))))
        result: dict[str, PageInfo | None] = {}
        for title in titles:
            found = self._target(project, title)
            if found is None:
                result[title] = None
            else:
                page, redirected_from = found
                result[title] = PageInfo(
                    page.title,
                    page.qid,
                    redirected_from,
                    redirect_title=redirected_from,
                    fragment=page.redirect_sections.get(redirected_from or ""),
                )
        return result

    def redirects_to(self, project: WikiProject, title: str) -> Sequence[str]:
        self.calls.append(("redirects_to", (project, title)))
        page = self.pages.get(project, {}).get(title)
        return list(page.redirects) if page else []

    def search(self, project: WikiProject, query: str, *, limit: int = 5) -> Sequence[str]:
        self.calls.append(("search", (project, query, limit)))
        return self.search_index.get(project, {}).get(query, [])[:limit]

    def mentions(self, project: WikiProject, phrase: str, *, limit: int = 5) -> Sequence[Mention]:
        self.calls.append(("mentions", (project, phrase, limit)))
        return self.mention_index.get(project, {}).get(phrase, [])[:limit]


# ---------------------------------------------------------------------------
# Pageviews
# ---------------------------------------------------------------------------

_ArticleKey = tuple[str, str, Granularity, Agent, Access]
_AggregateKey = tuple[str, Granularity, Agent, Access]


class FakePageviews:
    """Implements :class:`~wiki_interest.ports.pageviews.PageviewsSource` over dicts of points.

    Unknown articles or buckets yield ``None`` values, exactly like a 404 from the real API.
    """

    def __init__(self) -> None:
        self.articles: dict[_ArticleKey, dict[date, float]] = {}
        self.aggregates: dict[_AggregateKey, dict[date, float]] = {}
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def set_article(
        self,
        project: WikiProject,
        title: str,
        values: Mapping[date, float],
        *,
        granularity: Granularity = Granularity.MONTHLY,
        agent: Agent = Agent.USER,
        access: Access = Access.ALL,
    ) -> None:
        """Define the views of an article for one filter combination."""
        self.articles[(project.domain, title, granularity, agent, access)] = dict(values)

    def set_aggregate(
        self,
        project: WikiProject,
        values: Mapping[date, float],
        *,
        granularity: Granularity = Granularity.MONTHLY,
        agent: Agent = Agent.USER,
        access: Access = Access.ALL,
    ) -> None:
        """Define the edition-wide totals for one filter combination."""
        self.aggregates[(project.domain, granularity, agent, access)] = dict(values)

    def per_article(
        self,
        project: WikiProject,
        title: str,
        window: Window,
        *,
        access: Access,
        agent: Agent,
    ) -> Series:
        self.calls.append(("per_article", (project, title, window, access, agent)))
        values = self.articles.get((project.domain, title, window.granularity, agent, access), {})
        return _aligned(values, window)

    def aggregate(
        self, project: WikiProject, window: Window, *, access: Access, agent: Agent
    ) -> Series:
        self.calls.append(("aggregate", (project, window, access, agent)))
        values = self.aggregates.get((project.domain, window.granularity, agent, access), {})
        return _aligned(values, window)


def _aligned(values: Mapping[date, float], window: Window) -> Series:
    points = tuple(Point(bucket, values.get(bucket)) for bucket in window.buckets())
    return Series(window.granularity, SeriesUnit.VIEWS, points)


# ---------------------------------------------------------------------------
# A small consistent world for end-to-end tests
# ---------------------------------------------------------------------------


@dataclass
class AstronomyWorld:
    """Fakes describing "astronomy" in the Ukrainian and Czech editions with 24 months of data.

    Ukrainian interest rises steadily; Czech interest is flat. Polish has no article. The
    topic "astrology" shares the prefix "astro" so a fuzzy query is ambiguous.
    """

    wikidata: FakeWikidata
    mediawiki: FakeMediaWiki
    pageviews: FakePageviews
    clock: FakeClock
    months: tuple[date, ...]


def astronomy_world(*, start: date = date(2024, 9, 1), months: int = 24) -> AstronomyWorld:
    """Build the fixture world; ``start`` is the first month with data."""
    uk, cs = WikiProject("uk"), WikiProject("cs")
    wikidata = FakeWikidata(
        [
            FakeEntity(
                "Q333",
                {"en": "astronomy", "uk": "астрономія", "cs": "astronomie"},
                sitelinks={uk: "Астрономія", cs: "Astronomie"},
                claims={"P527": ["Q4213"]},
                description="natural science of celestial objects",
            ),
            FakeEntity(
                "Q4213",
                {"en": "telescope", "uk": "телескоп"},
                sitelinks={uk: "Телескоп", cs: "Dalekohled"},
            ),
            FakeEntity(
                "Q999",
                {"en": "astrology", "uk": "астрологія"},
                sitelinks={uk: "Астрологія"},
                description="pseudoscience",
            ),
        ]
    )
    mediawiki = FakeMediaWiki()
    mediawiki.add_page(uk, FakePage("Астрономія", qid="Q333", redirects=["Astronomy"]))
    mediawiki.add_page(uk, FakePage("Телескоп", qid="Q4213"))
    mediawiki.add_page(uk, FakePage("Астрологія", qid="Q999"))
    mediawiki.add_page(cs, FakePage("Astronomie", qid="Q333"))
    mediawiki.add_page(cs, FakePage("Dalekohled", qid="Q4213"))

    periods = tuple(_add_months(start, i) for i in range(months))
    pageviews = FakePageviews()
    pageviews.set_article(uk, "Астрономія", {m: 3000.0 + 60.0 * i for i, m in enumerate(periods)})
    pageviews.set_article(uk, "Astronomy", dict.fromkeys(periods, 100.0))
    pageviews.set_article(uk, "Телескоп", {m: 900.0 + 10.0 * i for i, m in enumerate(periods)})
    pageviews.set_aggregate(uk, dict.fromkeys(periods, 100000000.0))
    # Flat with small aperiodic noise, so neither a trend nor a seasonal pattern is detected.
    pageviews.set_article(
        cs, "Astronomie", {m: 2000.0 + ((i * 37) % 11 - 5) for i, m in enumerate(periods)}
    )
    pageviews.set_article(cs, "Dalekohled", dict.fromkeys(periods, 700.0))
    pageviews.set_aggregate(cs, dict.fromkeys(periods, 50000000.0))
    daily_start = periods[0]
    daily_end = _add_months(periods[-1], 1) - timedelta(days=1)
    daily = {
        daily_start + timedelta(days=d): 100.0 for d in range((daily_end - daily_start).days + 1)
    }
    pageviews.set_article(uk, "Астрономія", daily, granularity=Granularity.DAILY)
    today = _add_months(periods[-1], 1) + timedelta(days=21)
    return AstronomyWorld(wikidata, mediawiki, pageviews, FakeClock(today), periods)


def _add_months(value: date, months: int) -> date:
    index = value.year * 12 + value.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def fake_container(
    world: AstronomyWorld, tmp_path: Path, *, draw_charts: bool = False
) -> Container:
    """A composition root over the fake world, writing runs and cache under ``tmp_path``.

    Args:
        world: The fake Wikimedia the run reads.
        tmp_path: Where the runs and the cache go.
        draw_charts: Draw the charts with matplotlib, as a real run does. Without it each chart
            is a blank image of its size (:class:`BlankChartRenderer`): the PDF is laid out and
            written the same way, a second or so faster per run. A test that looks at a chart's
            picture or depends on its exact height asks for the real drawing.
    """
    settings = Settings(cache_path=tmp_path / "cache" / "http.sqlite", runs_dir=tmp_path / "runs")
    return _FakeContainer(
        settings=settings,
        clock=world.clock,
        http=HttpJsonClient(settings, InMemoryCache()),
        pageviews=world.pageviews,
        wikidata=world.wikidata,
        mediawiki=world.mediawiki,
        draw_charts=draw_charts,
    )


@dataclass
class _FakeContainer(Container):
    """The container with blank charts unless ``draw_charts`` is set."""

    draw_charts: bool = False

    def renderers_for(self, language: str) -> tuple[Translator, Renderers]:
        translator, renderers = super().renderers_for(language)
        if self.draw_charts:
            return translator, renderers
        charts = BlankChartRenderer()
        return translator, replace(
            renderers,
            charts=charts,
            report_pdf=FpdfReportRenderer(translator, charts=charts),
        )


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------


PIXELS_PER_MM = 2
"""Enough for the PDF to read an image's shape; the real charts are drawn at 300 dpi."""


class BlankChartRenderer:
    """Writes a blank PNG and an empty SVG of each chart's size instead of drawing it.

    The size is the theme's for the chart's ``size``, or its ``height_mm`` when set. The real
    renderer adds room for legends and rows under some charts, so a PDF laid out over blank
    charts may tighten one step earlier or later; the sections it holds are the same.
    """

    def __init__(self) -> None:
        self._chart = ReportTheme.load().chart
        self.rendered: list[str] = []
        """Ids of the charts drawn, in order."""

    def render(self, spec: ChartSpec, output_dir: Path) -> Sequence[Path]:
        """Write ``<id>.png`` and ``<id>.svg`` into ``output_dir``."""
        chart = self._chart
        width, height = {
            "half": (chart.half_width_mm, chart.half_height_mm),
            "strip": (chart.width_mm, chart.strip_height_mm),
        }.get(spec.size, (chart.width_mm, chart.height_mm))
        height = spec.height_mm or height
        output_dir.mkdir(parents=True, exist_ok=True)
        png = output_dir / f"{spec.id}.png"
        svg = output_dir / f"{spec.id}.svg"
        size = (round(width * PIXELS_PER_MM), round(height * PIXELS_PER_MM))
        Image.new("RGB", size, "white").save(png)
        svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
        self.rendered.append(spec.id)
        return [png, svg]


# ---------------------------------------------------------------------------
# Clock
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeClock:
    """A clock frozen at a fixed date."""

    fixed: date = date(2026, 9, 22)

    def today(self) -> date:
        return self.fixed
