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
from wiki_interest.contracts.request import AnalysisRequest, Period, SubstituteChoice
from wiki_interest.domain.assessment import EditionRelation, Momentum, RelativeSize, Robustness
from wiki_interest.domain.models import (
    ArticleRole,
    AudienceProfile,
    BundleStatus,
    CheckStatus,
    Granularity,
    ReliabilityLevel,
    ResolutionSource,
    SubstituteKind,
    TrendDirection,
)

__all__ = [
    "AnalysisSummary",
    "ArticleOut",
    "Artifacts",
    "AssessmentOut",
    "BundleOut",
    "CandidateOut",
    "CheckOut",
    "Clarification",
    "ComparisonRow",
    "CoverageGapOut",
    "CoverageOptionOut",
    "DataQualityOut",
    "DecisionOut",
    "EvidenceOut",
    "FindingOut",
    "MetricsOut",
    "MonthOut",
    "PointOut",
    "Provenance",
    "RankedRow",
    "ReliabilityOut",
    "SeasonOut",
    "SeriesOut",
    "TopicResolutionOut",
    "Verdict",
]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", use_enum_values=True)


class ArticleOut(_Model):
    """The measured article of a topic in an edition."""

    title: str
    role: ArticleRole
    source: ResolutionSource
    qid: str | None = None
    redirects: list[str] = Field(default_factory=list)


class BundleOut(_Model):
    """Resolution result for one topic in one project.

    ``article_count`` and ``redirect_count`` are stated explicitly (rather than left for the
    reader to count) because agents that counted the list themselves were the most common
    source of numbers not backed by the summary in the first Haiku evaluation.
    """

    topic_id: str
    project: str
    status: BundleStatus
    articles: list[ArticleOut] = Field(default_factory=list)
    article_count: int = 0
    redirect_count: int = 0
    """Redirects whose views were added to the measured (main) article."""
    substitute_kind: SubstituteKind | None = None


class TopicResolutionOut(_Model):
    """What the pipeline understood a topic to be.

    ``description`` and ``alternatives`` let the agent check the entity against what the
    user meant and switch to another one by ``qid`` without a new search.
    """

    topic_id: str
    query: str
    label: str | None
    qid: str | None
    bundles: list[BundleOut]
    description: str | None = None
    matched_in_english: bool = False
    alternatives: list[CandidateOut] = Field(default_factory=list)
    method: Literal["pinned", "link", "unique", "auto", "default", "title", "none"] = "none"
    """How the item was chosen; ``auto``: among homonyms, by the meaning the agent stated."""
    confidence: float | None = None
    """For ``auto``: the leader's share of the two best candidate scores."""
    runner_up: str | None = None
    """For ``auto``: the second-best candidate's item id."""


class PointOut(_Model):
    """One monthly observation of the main article.

    ``per_million`` is present when normalisation was possible; ``edition_views`` is the
    whole edition's views that month, so a change in share can be traced to its cause.
    """

    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    views: float | None
    per_million: float | None = None
    edition_views: float | None = None


class SeriesOut(_Model):
    """The measured series of one (topic, edition): main article plus its redirects."""

    topic_id: str
    project: str
    granularity: Granularity
    points: list[PointOut]


class MetricsOut(_Model):
    """Metrics of one series; mirrors :class:`~wiki_interest.domain.models.TrendMetrics`."""

    topic_id: str
    project: str
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
    """One row of the comparison table shown in the report.

    Attributes:
        views_avg: Mean monthly views of the main article.
        per_million_avg: Mean share of the edition's views, per million.
        index: ``per_million_avg`` against the highest in the table (= 100).
        growth_yoy: Growth of the analysed series (share, or views without normalisation),
            last 12 months over the 12 before.
        growth_halves: The same, second half of the period over the first.
        views_growth: Growth of the article's raw views, same rule as the headline.
        edition_growth: Growth of the whole edition's views over the same months.
    """

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
    index: float | None = None
    views_growth: float | None = None
    edition_growth: float | None = None


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
    """The answer, ready to be relayed, and the further findings as bullets.

    ``headline`` is the answer in one sentence without numbers, built from the states of the
    audiences; the numbers are in :attr:`AnalysisSummary.happening`. ``bullets`` holds the
    text of :attr:`AnalysisSummary.findings`, strongest first.
    """

    headline: str
    bullets: list[str] = Field(default_factory=list)


class EvidenceOut(_Model):
    """One reason behind a trust level: ``36 months of data``, ``no missing months``..."""

    text: str
    concern: bool = False
    """Whether it lowers trust rather than supports it."""


class MonthOut(_Model):
    """A month that stands out in one of the pair's series.

    Attributes:
        month: ``YYYY-MM``.
        multiples: ``metric: value / usual level`` for every series it stands out in
            (``article_views``, ``attention_share``, ``edition_traffic``); below one for a drop.
        nature: ``event`` (readers through every access method, or a burst of daily views),
            ``possible_bot`` (one access method, or automated traffic), ``edition`` (the
            edition moved, not the article) or ``unknown``.
        in_change: Whether it lies in the 24 months behind the headline change.
        in_recent: Whether it lies in the recent window or the same months a year earlier.
        change_without: The headline change without this month and its twin a year off.
    """

    month: str = Field(pattern=r"^\d{4}-\d{2}$")
    multiples: dict[str, float]
    nature: str
    in_change: bool
    in_recent: bool
    change_without: float | None = None


class SeasonOut(_Model):
    """The seasonal pattern of the article's whole history, and whether it is shown.

    Attributes:
        shown: Whether the report states it.
        reason: ``solid``, ``short_history``, ``inconsistent``, ``weak`` or ``no_data``.
        years: Full calendar years of history.
        consistency: Share of those years whose peak and trough agree with the pattern.
        strength: Share of the detrended variation the calendar explains.
        start: First month of the history used (``YYYY-MM``).
        end: Last month used.
        peak_month: Calendar month (1-12) with the highest level.
        trough_month: Calendar month with the lowest level.
        peak: Effect of the peak month against the usual level (``0.3`` = 30 % above).
        trough: Effect of the trough month.
    """

    shown: bool
    reason: str
    years: int
    consistency: float | None = None
    strength: float | None = None
    start: str | None = None
    end: str | None = None
    peak_month: int | None = None
    trough_month: int | None = None
    peak: float | None = None
    trough: float | None = None


class DataQualityOut(_Model):
    """How good the data are, apart from what they show.

    ``level`` is the worst of the data checks (months, gaps, bursts, automated traffic,
    audience size, how the article was found); the trend test is an inference, not a data
    check, and stays in ``reliability``. ``reasons`` are the checks that lowered it.
    """

    level: ReliabilityLevel
    reasons: list[str] = Field(default_factory=list)


class AssessmentOut(_Model):
    """The decision view of one (topic, edition): size, momentum, the edition, trust.

    Attributes:
        label: The pair as shown to readers (``ru.wikipedia``, ``Yoga · uk.wikipedia``).
        measured: Whether the edition had an article to measure.
        per_million: Mean views of the topic per million views of the whole edition: the
            size of interest, comparable across editions of different size.
        views_avg: Mean monthly views of the article.
        size: Against the largest pair of the report; ``None`` with nothing to compare.
        momentum: Where the share (or views without normalisation) is heading; ``flat``
            means no clear trend.
        change: The change behind ``momentum``, as a fraction; ``basis`` names the months.
        article_change: The article's views over the months in ``relation_basis``.
        edition_change: The whole edition's views over the same months.
        share_change: The topic's share of the edition over the same months.
        relation: Whether the topic gained or lost ground inside its edition.
        recent_months: Length of the recent window: the last months against the same months a
            year earlier. ``recent_article``, ``recent_edition`` and ``recent_shift`` (the
            share) are the changes over it.
        robustness: Whether the recent months confirm the long-term direction.
        robustness_line: That in words, with the numbers behind it.
        confidence: The reliability level; the report shows ``robustness`` instead.
        evidence: The state of the data (months, gaps, bursts), concerns first.
        outcome: Decision outcome key: ``<large|small|single>_<growing|flat|declining>``,
            ``low_trust``, ``unknown``, ``substitute`` or ``no_article``.
        decision: What the outcome means, as one sentence.
        edition_line: The article against its edition in words, ``None`` when not computable.
        data_quality: The data's quality apart from the trend.
        months: Months that stand out.
        season: The seasonal pattern of the whole history.
        divergence: ``views_up_share_down`` (more readers, but the edition grew faster) or
            ``views_down_share_up`` (fewer readers, but the edition fell faster).
    """

    topic_id: str
    project: str
    label: str
    measured: bool
    per_million: float | None = None
    views_avg: float | None = None
    size: RelativeSize | None = None
    momentum: Momentum
    change: float | None = None
    basis: str | None = None
    article_change: float | None = None
    edition_change: float | None = None
    share_change: float | None = None
    relation: EditionRelation | None = None
    relation_basis: str | None = None
    recent_months: int | None = None
    recent_article: float | None = None
    recent_edition: float | None = None
    recent_shift: float | None = None
    robustness: Robustness = Robustness.UNKNOWN
    robustness_line: str | None = None
    confidence: ReliabilityLevel
    evidence: list[EvidenceOut] = Field(default_factory=list)
    outcome: str
    decision: str
    edition_line: str | None = None
    data_quality: DataQualityOut | None = None
    months: list[MonthOut] = Field(default_factory=list)
    season: SeasonOut | None = None
    divergence: str | None = None


class DecisionOut(_Model):
    """What the report concludes for a decision, and the next step.

    Attributes:
        conclusion: Conclusion key (``strong``, ``emerging``, ``no_growth_stable``,
            ``all_declining``, ``single_<momentum>``, ``unknown``, ``low_trust``, ``none``).
        candidate: Label of the audience worth the next check, when there is one.
        lines: What each outcome means, one line per outcome with the audiences it applies
            to (``uk.wikipedia, pl.wikipedia: smaller audience...``); empty for one audience.
        next_step: The next step in one sentence, with examples of independent sources.
    """

    conclusion: str
    candidate: str | None = None
    summary: str | None = None
    """The conclusion in one sentence, shown first."""
    lines: list[str] = Field(default_factory=list)
    next_step: str


class FindingOut(_Model):
    """One fact the analysis found, in words and as data.

    Attributes:
        kind: What was found (``level_shift``, ``burst``, ``recent``, ``season``,
            ``edition.*``, ``share_ratio``, ``divergence``...).
        topic_id: Topic it is about; ``None`` for a statement across topics.
        project: Edition it is about; ``None`` for a statement across editions.
        importance: Ranking score in ``[0, 1]``; findings are listed strongest first.
        text: The finding as a sentence in the report language.
        params: The numbers and dates behind ``text``.
    """

    kind: str
    topic_id: str | None = None
    project: str | None = None
    importance: float
    text: str
    params: dict[str, float | int | str] = Field(default_factory=dict)


class CandidateOut(_Model):
    """A Wikidata entity the user may have meant."""

    qid: str
    label: str
    description: str | None = None
    article_projects: list[str] = Field(default_factory=list)
    """Requested editions with an article about this entity (shown, never used to choose)."""


class CoverageOptionOut(_Model):
    """One choice for an edition without an article, ready to show and to apply.

    Attributes:
        number: Position in the list shown to the user, from 1.
        kind: ``redirect``, ``broader``, ``mention`` or ``skip``.
        title: Page that would be measured; ``None`` for ``skip``.
        target: Article a redirect leads to.
        section: Section of ``target`` a redirect points into.
        snippet: Passage that mentions the topic, for ``mention``.
        views_avg: Mean monthly views of ``title`` over the last 12 complete months.
        description: The option in one localised sentence, views and the link included.
        url: The article to open to see what would be measured; ``None`` for ``skip``.
        choose: The exact value to merge into ``topics[].substitutes`` when the user picks
            this option; the agent copies it instead of composing it.
    """

    number: int
    kind: Literal["redirect", "broader", "mention", "skip"]
    title: str | None = None
    target: str | None = None
    section: str | None = None
    snippet: str | None = None
    views_avg: float | None = None
    description: str
    url: str | None = None
    choose: dict[str, SubstituteChoice]


class CoverageGapOut(_Model):
    """An edition without an article on a topic, with the choices the user has.

    ``topic_note`` says once per topic which entity the topic resolved to and in how many
    languages it has an article, so the user can catch a wrong entity before choosing.
    """

    topic_id: str
    query: str
    project: str
    qid: str | None = None
    label: str | None = None
    """The item's name in the report language, if Wikidata has one."""
    description: str | None = None
    """The item's Wikidata description, so the user can tell it from its homonyms."""
    article_languages: list[str] = Field(default_factory=list)
    matched_in_english: bool = False
    topic_note: str
    terms: list[str]
    question: str
    options: list[CoverageOptionOut]


class Clarification(_Model):
    """Why the pipeline stopped and what to ask the user.

    ``kind`` tells the questions apart: ``ambiguous_topic`` lists Wikidata ``candidates``
    (answered with ``topics[].qid``); ``missing_article`` lists ``gaps``, editions without an
    article and what could stand in for it (answered with ``topics[].substitutes``);
    ``topic_not_found`` means nothing matched at all (answered with ``topics[].article_url``).
    """

    kind: Literal["ambiguous_topic", "missing_article", "topic_not_found"] = "ambiguous_topic"
    topic_id: str
    query: str
    question: str
    """What the agent does next, in English."""
    candidates: list[CandidateOut] = Field(default_factory=list)
    gaps: list[CoverageGapOut] = Field(default_factory=list)
    ask_user: str | None = None
    """For ``missing_article``: the message to send the user word for word, composed by the
    code; ``None`` while ``ui`` still has labels to translate."""
    ui: dict[str, str] = Field(default_factory=dict)
    """Labels of ``ask_user`` still in English (``key: template``), for the agent to translate
    with ``render.py <run_dir> --ui``."""


class Artifacts(_Model):
    """Absolute paths of the files written for this run."""

    run_dir: str
    summary_json: str
    summary_md: str
    report_pdf: str | None = None
    method_md: str | None = None
    """How every number was computed for this run, the data checks and the thresholds."""
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
    thresholds: dict[str, float | int | bool] = Field(default_factory=dict)
    """The configured thresholds this run used (``WIKI_INTEREST_*``), for ``method.md``."""


class AnalysisSummary(_Model):
    """Complete result of one pipeline run."""

    schema_version: Literal["1"] = "1"
    status: Literal["ok", "needs_clarification", "topic_resolved"]
    """``topic_resolved``: the run stopped after the topic stage on purpose (evaluation mode);
    ``resolution`` is filled, nothing was measured."""
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
    assessments: list[AssessmentOut] = Field(default_factory=list)
    """One per (topic, edition), in the order of ``comparison``."""
    decision: DecisionOut | None = None
    happening: list[str] = Field(default_factory=list)
    """What happened: two or three sentences, each naming its metric and window."""
    data_note: list[str] = Field(default_factory=list)
    """The state of the data in one line when every audience is clean, else a line per
    audience with its concerns."""
    findings: list[FindingOut] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    """Limitations specific to this run (missing articles, substitutes, short period...)."""
    general_limitations: list[str] = Field(default_factory=list)
    """Limitations of the method that hold for every run (views measure curiosity...)."""
    next_steps: list[str] = Field(default_factory=list)
    narrative_source: Literal["template", "agent"] = "template"
    """Who wrote the headline, happening, robustness and decision text: the code's templates,
    or the agent (``narrative.json``, checked against ``facts.json``)."""
    topic_line: str | None = None
    """Which item was analysed, in the report language, when the agent wrote it."""
    chat_answer: str | None = None
    """The reply the agent sends to the chat as it is, composed from the report text."""
    artifacts: Artifacts
    provenance: Provenance
    clarification: Clarification | None = None
