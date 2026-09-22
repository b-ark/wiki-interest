"""Core domain types.

Immutable value objects describing what the skill analyses (projects, articles, topic bundles),
the data it works on (time series) and what it concludes (metrics, reliability, ranking).
No I/O, no pandas: the calculations that use numeric libraries live in sibling modules and
consume these types.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

__all__ = [
    "Access",
    "Agent",
    "ArticleRef",
    "ArticleRole",
    "AudienceProfile",
    "BundleStatus",
    "Check",
    "CheckStatus",
    "EntityCandidate",
    "Granularity",
    "Point",
    "RankedAudience",
    "RankingWeights",
    "Reliability",
    "ReliabilityLevel",
    "ReliabilityThresholds",
    "ResolutionSource",
    "Series",
    "SeriesUnit",
    "TopicBundle",
    "TrendDirection",
    "TrendMetrics",
    "WikiProject",
    "Window",
    "sorted_by_score",
]


# ---------------------------------------------------------------------------
# Pageviews API vocabulary
# ---------------------------------------------------------------------------


class Agent(StrEnum):
    """Traffic classes the Wikimedia Pageviews API distinguishes.

    ``USER`` is the default for interest analysis: ``SPIDER`` and ``AUTOMATED`` traffic says
    nothing about human interest and can dwarf it. ``AUTOMATED`` data is not available for
    every project and period; adapters report that as missing data, not as an error.
    """

    USER = "user"
    SPIDER = "spider"
    AUTOMATED = "automated"
    ALL = "all-agents"


class Access(StrEnum):
    """Access methods the Wikimedia Pageviews API distinguishes."""

    ALL = "all-access"
    DESKTOP = "desktop"
    MOBILE_WEB = "mobile-web"
    MOBILE_APP = "mobile-app"


class Granularity(StrEnum):
    """Time resolution of a series; a :class:`Point` period is the first day of its bucket."""

    DAILY = "daily"
    MONTHLY = "monthly"


@dataclass(frozen=True, slots=True)
class Window:
    """An inclusive range of buckets at one granularity.

    Every series in a run is aligned to a window, so adapters fill gaps against
    :meth:`buckets` and the domain never has to reconcile differently shaped series.
    """

    granularity: Granularity
    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            msg = f"Window end {self.end} is before start {self.start}"
            raise ValueError(msg)
        if self.granularity is Granularity.MONTHLY and (self.start.day != 1 or self.end.day != 1):
            msg = "Monthly window bounds must be the first day of a month"
            raise ValueError(msg)

    def buckets(self) -> tuple[date, ...]:
        """All bucket start dates from ``start`` to ``end`` inclusive."""
        if self.granularity is Granularity.DAILY:
            ordinals = range(self.start.toordinal(), self.end.toordinal() + 1)
            return tuple(date.fromordinal(o) for o in ordinals)
        first = self.start.year * 12 + self.start.month - 1
        last = self.end.year * 12 + self.end.month - 1
        return tuple(date(i // 12, i % 12 + 1, 1) for i in range(first, last + 1))

    @property
    def count(self) -> int:
        """Number of buckets in the window."""
        return len(self.buckets())


# ---------------------------------------------------------------------------
# Projects and articles
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True, order=True)
class WikiProject:
    """A Wikipedia language edition, identified by its language code (for example ``"uk"``).

    The same edition is named differently by each Wikimedia API; the properties below produce
    the right spelling for each so adapters never build these strings by hand.
    """

    language: str

    def __post_init__(self) -> None:
        code = self.language.lower()
        if not code or not code[0].isalpha() or not all(ch.isalnum() or ch == "-" for ch in code):
            msg = f"Invalid Wikipedia language code: {self.language!r}"
            raise ValueError(msg)
        object.__setattr__(self, "language", code)

    @classmethod
    def parse(cls, value: str) -> WikiProject:
        """Build a project from any accepted spelling.

        Accepts ``"uk"``, ``"uk.wikipedia"``, ``"uk.wikipedia.org"`` and ``"ukwiki"``.

        Args:
            value: Project spelling as found in requests or API responses.

        Returns:
            The corresponding project.

        Raises:
            ValueError: If the value is not a recognisable Wikipedia project.
        """
        text = value.strip().lower()
        for suffix in (".wikipedia.org", ".wikipedia", "wiki"):
            if text.endswith(suffix):
                text = text[: -len(suffix)]
                break
        return cls(text)

    @property
    def domain(self) -> str:
        """Spelling used by the Pageviews API, e.g. ``"uk.wikipedia"``."""
        return f"{self.language}.wikipedia"

    @property
    def host(self) -> str:
        """Host name of the MediaWiki API, e.g. ``"uk.wikipedia.org"``."""
        return f"{self.language}.wikipedia.org"

    @property
    def site_id(self) -> str:
        """Wikidata sitelink key, e.g. ``"ukwiki"``. Hyphens become underscores per Wikidata."""
        return f"{self.language.replace('-', '_')}wiki"


class ArticleRole(StrEnum):
    """Why an article is part of a topic bundle."""

    MAIN = "main"
    RELATED = "related"
    MANUAL = "manual"


class ResolutionSource(StrEnum):
    """How an article title was obtained; lower-confidence sources lower reliability."""

    SITELINK = "sitelink"
    WIKIDATA_RELATION = "wikidata_relation"
    LEAD_LINK = "lead_link"
    SEARCH_FALLBACK = "search_fallback"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class ArticleRef:
    """One Wikipedia article that contributes to a topic in one project.

    Attributes:
        project: The language edition the article lives in.
        title: Canonical page title with spaces (adapters convert to underscores for URLs).
        role: Why the article is in the bundle.
        source: How the title was found.
        weight: Relevance weight used when summing the bundle series; the main article is 1.0.
        qid: Wikidata item id (``"Q333"``) when known.
        redirects: Titles that redirect to this article; their views are added to the
            article's own because the Pageviews API counts them separately.
    """

    project: WikiProject
    title: str
    role: ArticleRole
    source: ResolutionSource
    weight: float = 1.0
    qid: str | None = None
    redirects: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip():
            msg = "Article title must not be empty"
            raise ValueError(msg)
        if not 0.0 < self.weight <= 1.0:
            msg = f"Article weight must be in (0, 1], got {self.weight}"
            raise ValueError(msg)


class BundleStatus(StrEnum):
    """Outcome of resolving a topic in one project."""

    FOUND = "found"
    FOUND_VIA_SEARCH = "found_via_search"
    NOT_FOUND = "not_found"


@dataclass(frozen=True, slots=True)
class TopicBundle:
    """The set of articles that represent a topic in one project.

    A bundle with status ``NOT_FOUND`` has no articles and is reported honestly as "no article
    in this edition" rather than as zero interest.
    """

    topic_id: str
    project: WikiProject
    status: BundleStatus
    articles: tuple[ArticleRef, ...] = ()

    def __post_init__(self) -> None:
        mains = [a for a in self.articles if a.role is ArticleRole.MAIN]
        if len(mains) > 1:
            msg = f"A bundle may have at most one main article, got {len(mains)}"
            raise ValueError(msg)
        if self.status is BundleStatus.NOT_FOUND and self.articles:
            msg = "A NOT_FOUND bundle cannot contain articles"
            raise ValueError(msg)
        if self.status is not BundleStatus.NOT_FOUND and not self.articles:
            msg = f"A {self.status.value} bundle must contain at least one article"
            raise ValueError(msg)

    @property
    def main(self) -> ArticleRef | None:
        """The main article, if the bundle has one."""
        return next((a for a in self.articles if a.role is ArticleRole.MAIN), None)


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    """A Wikidata entity that may be what the user meant by a topic query.

    ``exact_label_match`` is true when the query equals the entity's label or one of its
    aliases, ignoring case; the resolver treats such candidates as naming the topic exactly.
    """

    qid: str
    label: str
    description: str | None = None
    exact_label_match: bool = False


# ---------------------------------------------------------------------------
# Time series
# ---------------------------------------------------------------------------


class SeriesUnit(StrEnum):
    """What the values of a series measure."""

    VIEWS = "views"
    PER_MILLION = "per_million"


@dataclass(frozen=True, slots=True)
class Point:
    """One observation. ``value`` is ``None`` when the source had no data for the period."""

    period: date
    value: float | None


@dataclass(frozen=True, slots=True)
class Series:
    """A regularly spaced time series with explicit gaps.

    Points are sorted by period and periods are unique; a missing bucket is represented by a
    point whose value is ``None`` rather than by an absent point, so completeness is always
    computable and series of the same window align by index.
    """

    granularity: Granularity
    unit: SeriesUnit
    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        periods = [p.period for p in self.points]
        if periods != sorted(periods):
            msg = "Series points must be sorted by period"
            raise ValueError(msg)
        if len(set(periods)) != len(periods):
            msg = "Series periods must be unique"
            raise ValueError(msg)
        if self.granularity is Granularity.MONTHLY and any(d.day != 1 for d in periods):
            msg = "Monthly series periods must be the first day of the month"
            raise ValueError(msg)

    def __len__(self) -> int:
        return len(self.points)

    def __iter__(self) -> Iterator[Point]:
        return iter(self.points)

    @property
    def periods(self) -> tuple[date, ...]:
        """All periods in order."""
        return tuple(p.period for p in self.points)

    @property
    def values(self) -> tuple[float | None, ...]:
        """All values in order, gaps as ``None``."""
        return tuple(p.value for p in self.points)

    @property
    def observed(self) -> tuple[float, ...]:
        """Only the non-missing values, in order."""
        return tuple(p.value for p in self.points if p.value is not None)

    @property
    def completeness(self) -> float:
        """Share of periods that have data; 0.0 for an empty series."""
        if not self.points:
            return 0.0
        return len(self.observed) / len(self.points)

    @property
    def start(self) -> date | None:
        """First period, or ``None`` for an empty series."""
        return self.points[0].period if self.points else None

    @property
    def end(self) -> date | None:
        """Last period, or ``None`` for an empty series."""
        return self.points[-1].period if self.points else None


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TrendDirection(StrEnum):
    """Qualitative reading of a trend test."""

    RISING = "rising"
    FALLING = "falling"
    FLAT = "flat"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class TrendMetrics:
    """Everything the report says about one series.

    Values that cannot be computed (too few points, no daily data, no aggregate for
    normalisation) are ``None`` and are explained by the reliability checks.

    Attributes:
        periods: Number of monthly buckets in the analysis window.
        completeness: Share of those buckets with data.
        views_total: Sum of observed views.
        views_avg: Mean monthly views over observed buckets.
        per_million_avg: Mean of the per-million normalised series, if available.
        growth_yoy: Matched-month sums in the last 12 months over the preceding 12, minus one.
            Needs 24 buckets and at least 75 % observed pairs.
        growth_halves: Matched-month sums in equal-length second and first halves, minus one.
            Needs 4 buckets and 75 % observed pairs; excludes an odd window's central month.
        slope_per_year: Robust (Theil-Sen) slope of ``log(value)`` expressed as relative change
            per year, e.g. ``0.15`` means +15 % per year.
        trend_p_value: Mann-Kendall p-value for a monotonic trend.
        trend_direction: Direction implied by the slope when the test is significant.
        seasonality_strength: Share of variance explained by month-of-year, in [0, 1].
        spike_share: Share of total views that fell on spike days (daily data).
        volatility_cv: Coefficient of variation of the detrended series.
        automated_share: Automated traffic over automated + user traffic for matching titles.
            The pipeline uses the canonical main article for both main and bundle diagnostics.
    """

    periods: int
    completeness: float
    views_total: float
    views_avg: float
    per_million_avg: float | None
    growth_yoy: float | None
    growth_halves: float | None
    slope_per_year: float | None
    trend_p_value: float | None
    trend_direction: TrendDirection
    seasonality_strength: float | None
    spike_share: float | None
    volatility_cv: float | None
    automated_share: float | None


# ---------------------------------------------------------------------------
# Reliability
# ---------------------------------------------------------------------------


class CheckStatus(StrEnum):
    """Outcome of one reliability rule."""

    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class Check:
    """Result of one named reliability rule.

    The human-readable explanation is produced later from ``reason_key`` and ``params`` in the
    report language; the domain deliberately does not contain prose.
    """

    name: str
    status: CheckStatus
    reason_key: str
    params: Mapping[str, float | int | str] = field(default_factory=dict)


class ReliabilityLevel(StrEnum):
    """How much the conclusions about a series can be trusted."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class Reliability:
    """Aggregate reliability verdict with the checks that produced it."""

    level: ReliabilityLevel
    checks: tuple[Check, ...]


@dataclass(frozen=True, slots=True)
class ReliabilityThresholds:
    """Tunable thresholds for the reliability rules; documented in ``references/methodology.md``.

    Attributes:
        min_periods_ok: Window length (months) considered sufficient.
        min_periods_warn: Window length below which the verdict fails outright.
        completeness_ok: Share of buckets with data considered sufficient.
        completeness_warn: Share below which the verdict fails outright.
        spike_share_warn: Spike share above which growth is suspect.
        spike_share_fail: Spike share above which growth is explained by spikes.
        trend_p_value: Significance level for the Mann-Kendall test.
        automated_share_warn: Automated traffic share above which bots are suspected.
        min_views_avg: Mean monthly views below which the signal is too noisy.
        search_fallback_warns: Whether a search-fallback main article warns.
    """

    min_periods_ok: int = 24
    min_periods_warn: int = 12
    completeness_ok: float = 0.95
    completeness_warn: float = 0.80
    spike_share_warn: float = 0.20
    spike_share_fail: float = 0.40
    trend_p_value: float = 0.05
    automated_share_warn: float = 0.30
    min_views_avg: float = 300.0
    search_fallback_warns: bool = True


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RankingWeights:
    """Relative importance of the ranking components; any positive weights, normalised on use."""

    growth: float = 0.4
    volume: float = 0.3
    stability: float = 0.2
    reliability: float = 0.1

    def __post_init__(self) -> None:
        values = (self.growth, self.volume, self.stability, self.reliability)
        if any(v < 0 for v in values) or sum(values) <= 0:
            msg = "Ranking weights must be non-negative and not all zero"
            raise ValueError(msg)

    def normalised(self) -> RankingWeights:
        """Return the same weights scaled to sum to one."""
        total = self.growth + self.volume + self.stability + self.reliability
        return RankingWeights(
            growth=self.growth / total,
            volume=self.volume / total,
            stability=self.stability / total,
            reliability=self.reliability / total,
        )


class AudienceProfile(StrEnum):
    """Interpretive label for an audience, derived from growth and volume together."""

    EARLY_NICHE = "early_niche"
    GROWTH_MARKET = "growth_market"
    MATURE_MARKET = "mature_market"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class RankedAudience:
    """One (topic, project) pair scored against the others in the same request."""

    topic_id: str
    project: WikiProject
    score: float
    components: Mapping[str, float]
    profile: AudienceProfile
    reliability: ReliabilityLevel


def sorted_by_score(items: Sequence[RankedAudience]) -> tuple[RankedAudience, ...]:
    """Order ranked audiences best first, ties broken by project code for determinism."""
    return tuple(sorted(items, key=lambda r: (-r.score, r.project.language, r.topic_id)))
