"""``summary.json``: everything the pipeline concluded, in one machine-readable document.

The summary is the single source for every other artifact: ``summary.md`` for the agent, the
PDF for the user, and the assertions in the evaluation harness. All prose fields are already
localised in the report language, so consumers never compose sentences themselves.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from wiki_interest.contracts.charts import ChartSpec
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.domain.models import (
    ArticleRole,
    AudienceProfile,
    BundleStatus,
    CheckStatus,
    Granularity,
    ReliabilityLevel,
    ResolutionSource,
    TrendDirection,
)

__all__ = [
    "AnalysisSummary",
    "ArticleOut",
    "Artifacts",
    "BundleOut",
    "CandidateOut",
    "CheckOut",
    "Clarification",
    "ComparisonRow",
    "MetricsOut",
    "PointOut",
    "Provenance",
    "RankedRow",
    "ReliabilityOut",
    "SeriesKind",
    "SeriesOut",
    "TopicResolutionOut",
    "Verdict",
]

SeriesKind = Literal["bundle", "main"]
"""``bundle``: weighted sum of all articles of the topic; ``main``: the main article alone.
Both are reported so a conclusion never silently depends on the bundle composition."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class ArticleOut(_Model):
    """One article of a bundle as reported to the user."""

    title: str
    role: ArticleRole
    source: ResolutionSource
    weight: float
    qid: str | None = None
    redirects: list[str] = Field(default_factory=list)


class BundleOut(_Model):
    """Resolution result for one topic in one project.

    ``article_count`` and ``related_count`` are stated explicitly (rather than left for the
    reader to count) because agents that counted the list themselves were the most common
    source of numbers not backed by the summary in the first Haiku evaluation.
    """

    topic_id: str
    project: str
    status: BundleStatus
    articles: list[ArticleOut] = Field(default_factory=list)
    article_count: int = 0
    related_count: int = 0


class TopicResolutionOut(_Model):
    """What the pipeline understood a topic to be."""

    topic_id: str
    query: str
    label: str | None
    qid: str | None
    bundles: list[BundleOut]


class PointOut(_Model):
    """One monthly observation; ``per_million`` is present when normalisation was possible."""

    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    views: float | None
    per_million: float | None = None


class SeriesOut(_Model):
    """A series as plotted and analysed."""

    topic_id: str
    project: str
    kind: SeriesKind
    granularity: Granularity
    points: list[PointOut]


class MetricsOut(_Model):
    """Metrics of one series; mirrors :class:`~wiki_interest.domain.models.TrendMetrics`."""

    topic_id: str
    project: str
    kind: SeriesKind
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


class CheckOut(_Model):
    """One reliability rule with its localised explanation."""

    name: str
    status: CheckStatus
    message: str
    reason_key: str
    params: dict[str, float | int | str] = Field(default_factory=dict)


class ReliabilityOut(_Model):
    """Reliability verdict for one (topic, project)."""

    topic_id: str
    project: str
    level: ReliabilityLevel
    checks: list[CheckOut]


class ComparisonRow(_Model):
    """One row of the comparison table shown in the report."""

    topic_id: str
    project: str
    label: str
    views_avg: float | None
    per_million_avg: float | None
    growth_yoy: float | None
    growth_halves: float | None
    trend_direction: TrendDirection
    reliability: ReliabilityLevel
    note: str | None = None


class RankedRow(_Model):
    """One row of the ranking, best first."""

    rank: int
    topic_id: str
    project: str
    label: str
    score: float
    components: dict[str, float]
    profile: AudienceProfile
    reliability: ReliabilityLevel
    rationale: str


class Verdict(_Model):
    """The answer, ready to be relayed: one headline and a few supporting bullets."""

    headline: str
    bullets: list[str] = Field(default_factory=list)


class CandidateOut(_Model):
    """A Wikidata entity the user may have meant."""

    qid: str
    label: str
    description: str | None = None


class Clarification(_Model):
    """Why the pipeline stopped and what to ask the user."""

    topic_id: str
    query: str
    question: str
    candidates: list[CandidateOut]


class Artifacts(_Model):
    """Absolute paths of the files written for this run."""

    run_dir: str
    summary_json: str
    summary_md: str
    report_md: str | None = None
    report_pdf: str | None = None
    charts: list[str] = Field(default_factory=list)


class Provenance(_Model):
    """Where the numbers came from, so a result can be audited or reproduced."""

    code_version: str
    generated_at: datetime
    data_through: str = Field(pattern=r"^\d{4}-\d{2}$")
    user_agent: str
    sources: list[str]
    request_count: int = 0
    cache_hits: int = 0


class AnalysisSummary(_Model):
    """Complete result of one pipeline run."""

    schema_version: Literal["1"] = "1"
    status: Literal["ok", "needs_clarification"]
    run_id: str
    session: str | None
    request: AnalysisRequest
    period: Period
    resolution: list[TopicResolutionOut] = Field(default_factory=list)
    series: list[SeriesOut] = Field(default_factory=list)
    metrics: list[MetricsOut] = Field(default_factory=list)
    reliability: list[ReliabilityOut] = Field(default_factory=list)
    comparison: list[ComparisonRow] = Field(default_factory=list)
    ranking: list[RankedRow] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    verdict: Verdict
    limitations: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    artifacts: Artifacts
    provenance: Provenance
    clarification: Clarification | None = None
