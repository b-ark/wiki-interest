"""``request.json``: what the agent asks the pipeline to analyse.

The schema is deliberately forgiving on input (several spellings of a project, ``"YYYY-MM"``
periods, defaults for everything but topics and projects) and strict on unknown fields, so a
typo in a key fails loudly instead of being silently ignored.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any, Literal, Self
from urllib.parse import unquote

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

from wiki_interest.domain.models import RankingWeights, WikiProject

__all__ = [
    "EARLIEST_MONTH",
    "AnalysisRequest",
    "BundleMode",
    "Period",
    "QuestionType",
    "RankingWeightsSpec",
    "ReportOptions",
    "SubstituteChoice",
    "SubstituteSpec",
    "TopicSpec",
]

QuestionType = Literal["compare", "assess", "rank"]
"""What the user wants to know.

* ``compare`` - how interest differs between several editions or topics;
* ``assess``  - whether interest in one topic grows and how much to trust that;
* ``rank``    - which (topic, edition) pairs look most promising under the given weights.
"""

BundleMode = Literal["main", "auto", "manual"]
"""How a topic maps to articles: only the main article, main plus automatically found related
articles (default), or exactly the titles listed in ``extra_titles``."""

EARLIEST_MONTH = date(2015, 7, 1)
"""First month with data in the Wikimedia Pageviews API."""

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ARTICLE_URL_RE = re.compile(
    r"^https?://(?P<lang>[a-z][a-z0-9-]*)\.(?:m\.)?wikipedia\.org/wiki/(?P<title>[^?#]+)"
)
_YEAR_MONTH_RE = re.compile(r"^(\d{4})-(\d{2})$")
_MIN_COMPARE_COMBINATIONS = 2

Slug = Annotated[str, Field(pattern=_SLUG_RE.pattern, max_length=64)]


class _StrictModel(BaseModel):
    """Common configuration: immutable, unknown keys rejected, enums by value."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)


class SubstituteSpec(_StrictModel):
    """A page the user chose to stand in for an article that does not exist in an edition.

    The run that found the gap lists the options, each with a ready ``choose`` value, so the
    agent copies one verbatim instead of composing it.

    Attributes:
        title: Page title in that edition. For ``redirect`` it is the redirect itself, whose
            views count only visits under that name; otherwise the article it names.
        kind: What the page is relative to the topic; see
            :class:`~wiki_interest.domain.models.SubstituteKind`.
    """

    title: str = Field(min_length=1, max_length=255)
    kind: Literal["redirect", "broader", "mention"]


SubstituteChoice = SubstituteSpec | Literal["skip"]
"""What to do in an edition without an article: measure a substitute page, or leave the
edition out and report "no article" (``"skip"``)."""


class TopicSpec(_StrictModel):
    """One topic to analyse.

    Attributes:
        query: The topic as the user phrased it, in any language.
        query_language: Language code of ``query``; used for the Wikidata search.
        query_en: The topic in English, used only when the search in ``query_language`` finds
            nothing. Wikidata labels are matched per language and an item often has no label
            exactly in the languages where it has no article, while English labels are nearly
            universal: "post przerywany" finds nothing in Polish, "intermittent fasting" finds
            the item.
        id: Stable identifier used in outputs and file names; derived from ``query`` when
            omitted (``"topic-1"``, ``"topic-2"`` … for non-Latin queries).
        qid: Wikidata item to use instead of searching; set this after a clarification.
        bundle: How to expand the topic into articles.
        extra_titles: Additional article titles per project (``{"uk.wikipedia": ["Телескоп"]}``).
        exclude_titles: Titles per project to drop from the automatic bundle.
        local_terms: How the topic is usually called in an edition's language
            (``{"pl.wikipedia": "post przerywany"}``). Optional; used only when the edition
            has no article linked from Wikidata, to find a redirect or articles that mention
            the topic. Wikidata often lacks a label exactly where the article is missing.
        substitutes: The user's decision per edition that has no article, taken from the
            options a previous run listed: a substitute page or ``"skip"``.
        meaning: What the user means, in a few English words (``"the chemical element Hg"``),
            decided by the agent from the conversation. The pipeline does not interpret it; it
            is recorded so the reports and the agent can check the resolved entity against it.
        article_url: Link to a Wikipedia article about the topic, given by the user when the
            topic could not be found by name. Its Wikidata item replaces the search.
    """

    query: str = Field(min_length=1, max_length=200)
    query_language: str = Field(default="en", pattern=r"^[a-z]{2,3}(-[a-z0-9]+)?$")
    query_en: str | None = Field(default=None, min_length=1, max_length=200)
    id: Slug | None = None
    qid: str | None = Field(default=None, pattern=r"^Q[1-9]\d*$")
    bundle: BundleMode = "auto"
    extra_titles: dict[str, list[str]] = Field(default_factory=dict)
    exclude_titles: dict[str, list[str]] = Field(default_factory=dict)
    local_terms: dict[str, Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        default_factory=dict
    )
    substitutes: dict[str, SubstituteChoice] = Field(default_factory=dict)
    meaning: str | None = Field(default=None, min_length=1, max_length=200)
    article_url: str | None = Field(default=None, pattern=_ARTICLE_URL_RE.pattern)

    @property
    def article_ref(self) -> tuple[WikiProject, str] | None:
        """``(edition, title)`` named by ``article_url``, with the title URL-decoded."""
        if self.article_url is None:
            return None
        match = _ARTICLE_URL_RE.match(self.article_url)
        assert match is not None  # guaranteed by the field pattern
        title = unquote(match.group("title")).replace("_", " ")
        return WikiProject(match.group("lang")), title

    @field_validator("extra_titles", "exclude_titles", mode="before")
    @classmethod
    def _normalise_project_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        normalised: dict[str, list[str]] = {}
        for key, titles in value.items():
            project = WikiProject.parse(str(key)).domain
            normalised.setdefault(project, []).extend(titles)
        return normalised

    @field_validator("local_terms", "substitutes", mode="before")
    @classmethod
    def _normalise_single_value_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        return {WikiProject.parse(str(key)).domain: item for key, item in value.items()}

    @model_validator(mode="after")
    def _manual_bundle_needs_titles(self) -> Self:
        if self.bundle == "manual" and not any(self.extra_titles.values()):
            msg = 'bundle="manual" requires at least one title in extra_titles'
            raise ValueError(msg)
        return self


class Period(_StrictModel):
    """Inclusive range of whole months. Accepts and serialises ``"YYYY-MM"`` strings."""

    start: date
    end: date

    @field_validator("start", "end", mode="before")
    @classmethod
    def _parse_year_month(cls, value: Any) -> Any:
        if isinstance(value, str):
            match = _YEAR_MONTH_RE.match(value.strip())
            if not match:
                msg = f"Expected 'YYYY-MM', got {value!r}"
                raise ValueError(msg)
            return date(int(match.group(1)), int(match.group(2)), 1)
        if isinstance(value, date):
            return value.replace(day=1)
        return value

    @field_serializer("start", "end")
    def _serialise_year_month(self, value: date) -> str:
        return value.strftime("%Y-%m")

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        if self.start < EARLIEST_MONTH:
            msg = f"Pageview data starts in {EARLIEST_MONTH:%Y-%m}; got start={self.start:%Y-%m}"
            raise ValueError(msg)
        if self.end < self.start:
            msg = f"Period end {self.end:%Y-%m} is before start {self.start:%Y-%m}"
            raise ValueError(msg)
        return self

    @property
    def months(self) -> int:
        """Number of months in the period, inclusive."""
        return (self.end.year - self.start.year) * 12 + (self.end.month - self.start.month) + 1

    @classmethod
    def last_full_months(cls, today: date, count: int = 24) -> Period:
        """Build the default period: the ``count`` complete months before ``today``'s month.

        The current month is excluded because its data is partial and would read as a drop.
        """
        if count < 1:
            msg = "count must be at least 1"
            raise ValueError(msg)
        first_of_this_month = today.replace(day=1)
        end = _shift_months(first_of_this_month, -1)
        start = _shift_months(end, -(count - 1))
        return cls(start=max(start, EARLIEST_MONTH), end=end)


def _shift_months(value: date, months: int) -> date:
    """Return the first day of the month ``months`` after (or before) ``value``'s month."""
    index = value.year * 12 + (value.month - 1) + months
    return date(index // 12, index % 12 + 1, 1)


class RankingWeightsSpec(_StrictModel):
    """Relative importance of ranking components. Any non-negative numbers; normalised on use."""

    growth: float = Field(default=0.4, ge=0)
    volume: float = Field(default=0.3, ge=0)
    stability: float = Field(default=0.2, ge=0)
    reliability: float = Field(default=0.1, ge=0)

    @model_validator(mode="after")
    def _not_all_zero(self) -> Self:
        if self.growth + self.volume + self.stability + self.reliability <= 0:
            msg = "At least one ranking weight must be positive"
            raise ValueError(msg)
        return self

    def to_domain(self) -> RankingWeights:
        """Convert to the domain value object."""
        return RankingWeights(
            growth=self.growth,
            volume=self.volume,
            stability=self.stability,
            reliability=self.reliability,
        )


class ReportOptions(_StrictModel):
    """How the report should be written."""

    language: str = Field(default="en", pattern=r"^[a-z]{2,3}$")
    title: str | None = Field(default=None, max_length=120)
    audience_note: str | None = Field(default=None, max_length=500)
    formats: list[Literal["pdf", "md"]] = Field(default=["pdf", "md"])
    seasonality: Literal["auto", "show"] = "auto"
    """``show`` when the user asked about timing (months, seasons, when to launch): the
    seasonal pattern is then always reported and charted. ``auto`` shows it only when it is
    material, and charts it only with enough history to trust it."""


class AnalysisRequest(_StrictModel):
    """Top-level request. See ``references/request-schema.md`` for worked examples."""

    schema_version: Literal["1"] = "1"
    question_type: QuestionType
    topics: list[TopicSpec] = Field(min_length=1, max_length=10)
    projects: list[str] = Field(min_length=1, max_length=10)
    period: Period | None = None
    agent: Literal["user", "all-agents"] = "user"
    access: Literal["all-access", "desktop", "mobile-web", "mobile-app"] = "all-access"
    normalization: Literal["per_million", "absolute"] = "per_million"
    ranking_weights: RankingWeightsSpec = Field(default_factory=RankingWeightsSpec)
    report: ReportOptions = Field(default_factory=ReportOptions)
    session: Slug | None = None

    @field_validator("projects", mode="before")
    @classmethod
    def _normalise_projects(cls, value: Any) -> Any:
        if not isinstance(value, list):
            return value
        seen: dict[str, None] = {}
        for item in value:
            seen.setdefault(WikiProject.parse(str(item)).domain, None)
        return list(seen)

    @model_validator(mode="before")
    @classmethod
    def _fill_topic_ids(cls, data: Any) -> Any:
        if not isinstance(data, dict) or not isinstance(data.get("topics"), list):
            return data
        topics = []
        for index, spec in enumerate(data["topics"], start=1):
            filled = spec
            if isinstance(spec, dict) and not spec.get("id"):
                filled = {**spec, "id": _slug_for(str(spec.get("query", "")), index)}
            elif isinstance(spec, TopicSpec) and spec.id is None:
                filled = spec.model_copy(update={"id": _slug_for(spec.query, index)})
            topics.append(filled)
        return {**data, "topics": topics}

    @model_validator(mode="after")
    def _check_consistency(self) -> Self:
        ids = [t.id for t in self.topics]
        if len(set(ids)) != len(ids):
            msg = f"Topic ids must be unique, got {ids}"
            raise ValueError(msg)
        known = set(self.projects)
        for topic in self.topics:
            mappings: tuple[dict[str, Any], ...] = (
                topic.extra_titles,
                topic.exclude_titles,
                topic.local_terms,
                topic.substitutes,
            )
            for mapping in mappings:
                unknown = sorted(set(mapping) - known)
                if unknown:
                    msg = (
                        f"Topic {topic.id!r} names projects that are not in the request: {unknown}"
                    )
                    raise ValueError(msg)
        combinations = len(self.topics) * len(self.projects)
        if self.question_type == "compare" and combinations < _MIN_COMPARE_COMBINATIONS:
            msg = 'question_type="compare" needs at least two (topic, project) combinations'
            raise ValueError(msg)
        return self

    @property
    def project_objects(self) -> tuple[WikiProject, ...]:
        """Projects as domain objects, in request order."""
        return tuple(WikiProject.parse(p) for p in self.projects)


def _slug_for(query: str, index: int) -> str:
    """Derive an ASCII slug from a query, falling back to ``topic-<index>``."""
    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")[:64].strip("-")
    return slug if slug and _SLUG_RE.match(slug) else f"topic-{index}"
