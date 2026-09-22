"""In-memory implementations of the ports for fast, deterministic tests.

Each fake mirrors the documented contract of its port (gap semantics, absence handling) and
records the calls it received so tests can assert on request counts and arguments.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date

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
from wiki_interest.ports.mediawiki import PageInfo

__all__ = [
    "FakeClock",
    "FakeEntity",
    "FakeMediaWiki",
    "FakePage",
    "FakePageviews",
    "FakeWikidata",
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

    def labels(self, qids: Sequence[str], language: str) -> Mapping[str, str]:
        self.calls.append(("labels", (tuple(qids), language)))
        out: dict[str, str] = {}
        for qid in qids:
            entity = self.entities.get(qid)
            if entity is None:
                continue
            label = entity.labels.get(language) or entity.labels.get("en")
            if label:
                out[qid] = label
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
    lead_links: list[str] = field(default_factory=list)


class FakeMediaWiki:
    """Implements :class:`~wiki_interest.ports.mediawiki.MediaWikiGateway` over dicts."""

    def __init__(self) -> None:
        self.pages: dict[WikiProject, dict[str, FakePage]] = {}
        self.search_index: dict[WikiProject, dict[str, list[str]]] = {}
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def add_page(self, project: WikiProject, page: FakePage) -> FakePage:
        """Register a page; its redirects become resolvable aliases."""
        self.pages.setdefault(project, {})[page.title] = page
        return page

    def add_search(self, project: WikiProject, query: str, titles: Sequence[str]) -> None:
        """Define full-text search results for an exact query string."""
        self.search_index.setdefault(project, {})[query] = list(titles)

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
                result[title] = PageInfo(page.title, page.qid, redirected_from)
        return result

    def redirects_to(self, project: WikiProject, title: str) -> Sequence[str]:
        self.calls.append(("redirects_to", (project, title)))
        page = self.pages.get(project, {}).get(title)
        return list(page.redirects) if page else []

    def lead_links(self, project: WikiProject, title: str) -> Sequence[str]:
        self.calls.append(("lead_links", (project, title)))
        page = self.pages.get(project, {}).get(title)
        return list(page.lead_links) if page else []

    def search(self, project: WikiProject, query: str, *, limit: int = 5) -> Sequence[str]:
        self.calls.append(("search", (project, query, limit)))
        return self.search_index.get(project, {}).get(query, [])[:limit]


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
# Clock
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FakeClock:
    """A clock frozen at a fixed date."""

    fixed: date = date(2026, 9, 22)

    def today(self) -> date:
        return self.fixed
