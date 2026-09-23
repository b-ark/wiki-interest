"""Use-case: turn loaded series into metrics, findings, reliability verdicts and a ranking.

This is the numeric heart of a run. It is deliberately free of prose and rendering: the
result is a set of domain values that a later step turns into localised text, tables and
charts.

What is measured is the topic's main article (with the redirects that lead to it), the same
Wikidata item in every edition, so editions are compared on the same thing. Related articles
are measured one by one as context and never summed into the topic: a weighted sum of
different article sets per edition would compare compositions, not interest.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from wiki_interest.application.loading import ContextSeries, LoadedSeries
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.domain.findings import (
    Anomaly,
    EditionComparison,
    FindingsSettings,
    LevelShift,
    RecentChange,
    SeasonalProfile,
    compare_with_edition,
    detect_level_shift,
    find_anomalies,
    recent_change,
    seasonal_profile,
)
from wiki_interest.domain.metrics import (
    MetricsSettings,
    comparable_growth,
    compute_automated_share,
    compute_metrics,
)
from wiki_interest.domain.models import (
    ArticleRole,
    BundleStatus,
    RankedAudience,
    RankingWeights,
    Reliability,
    ReliabilityThresholds,
    ResolutionSource,
    Series,
    SubstituteKind,
    TopicBundle,
    TrendMetrics,
    WikiProject,
)
from wiki_interest.domain.ranking import ProfileThresholds, RankingInput, rank_audiences
from wiki_interest.domain.reliability import assess_reliability
from wiki_interest.domain.series import per_million
from wiki_interest.domain.trend_tests import seasonal_strength

__all__ = [
    "AnalysisResult",
    "AnalysisSettings",
    "ContextArticle",
    "PairAnalysis",
    "PairFindings",
    "analyse",
]

_OTHER_SUBJECT = frozenset({SubstituteKind.BROADER, SubstituteKind.MENTION})
"""Substitutes whose views belong mostly to another subject than the topic."""


@dataclass(frozen=True, slots=True)
class AnalysisSettings:
    """Thresholds and switches for the analysis step.

    Use :meth:`from_thresholds` so the significance level used by the metrics and by the
    reliability rule are the same number.

    Attributes:
        thresholds: Reliability rule thresholds.
        metrics: Metric computation settings (significance level, minimum observations).
        findings: Detector thresholds (level shifts, bursts, seasons).
        profiles: Growth cut-offs for audience profiles in the ranking.
        normalise: Whether to compute per-million series; ``False`` analyses raw views.
    """

    thresholds: ReliabilityThresholds = field(default_factory=ReliabilityThresholds)
    metrics: MetricsSettings = field(default_factory=MetricsSettings)
    findings: FindingsSettings = field(default_factory=FindingsSettings)
    profiles: ProfileThresholds = field(default_factory=ProfileThresholds)
    normalise: bool = True

    @classmethod
    def from_thresholds(
        cls, thresholds: ReliabilityThresholds, *, normalise: bool = True
    ) -> AnalysisSettings:
        """Build settings whose trend significance level matches ``thresholds``."""
        return cls(
            thresholds=thresholds,
            metrics=MetricsSettings(alpha=thresholds.trend_p_value),
            normalise=normalise,
        )


_DEFAULT_SETTINGS = AnalysisSettings()


@dataclass(frozen=True, slots=True)
class ContextArticle:
    """A related article reported next to the topic, with its own numbers.

    Attributes:
        title: Article title in the edition.
        role: ``related`` (found automatically) or ``manual`` (added by the user).
        source: Which signal linked it to the topic.
        views_avg: Mean monthly views over the period, ``None`` without data.
        growth: Growth of its views by the headline rule, ``None`` when not computable.
    """

    title: str
    role: ArticleRole
    source: ResolutionSource
    views_avg: float | None
    growth: float | None


@dataclass(frozen=True, slots=True)
class PairFindings:
    """What the detectors found for one pair; see :mod:`wiki_interest.domain.findings`.

    Attributes:
        level_shift: A step in the analysed series (share, or views without normalisation).
        anomalies: Dated bursts of daily views, largest first.
        recent: Last months of views against the same months a year earlier.
        recent_edition: The same comparison for the whole edition.
        seasonality: Calendar-month profile of views.
        seasonality_strength: How much of the views' variation the calendar explains.
        edition: The article's growth against the edition's over the same months.
    """

    level_shift: LevelShift | None = None
    anomalies: tuple[Anomaly, ...] = ()
    recent: RecentChange | None = None
    recent_edition: RecentChange | None = None
    seasonality: SeasonalProfile | None = None
    seasonality_strength: float | None = None
    edition: EditionComparison | None = None


@dataclass(frozen=True, slots=True)
class PairAnalysis:
    """Everything computed for one (topic, edition) pair.

    Series and metrics are ``None`` when the edition has no article to measure;
    ``reliability`` is then a single failing ``resolution`` check.

    Attributes:
        views: Monthly views of the main article and its redirects.
        per_million: ``views`` per million views of the edition, when normalising.
        edition_total: Monthly views of the whole edition.
        daily: Daily views of the main article, when fetched.
    """

    topic_id: str
    project: WikiProject
    bundle: TopicBundle
    views: Series | None
    per_million: Series | None
    edition_total: Series
    daily: Series | None
    metrics: TrendMetrics | None
    reliability: Reliability
    findings: PairFindings = field(default_factory=PairFindings)
    context: tuple[ContextArticle, ...] = ()

    @property
    def measures_topic(self) -> bool:
        """Whether the numbers describe the topic itself.

        False for a broader or mentioning article chosen in place of a missing one: such a
        pair is shown with its own numbers but never wins a headline or a ranking, because
        its views belong mostly to another subject. A redirect under the topic's name does
        measure the topic, if narrowly.
        """
        return self.bundle.substitute_kind not in _OTHER_SUBJECT

    @property
    def analysis_series(self) -> Series | None:
        """The series growth and trend are computed on: the share, else raw views."""
        return self.per_million if self.per_million is not None else self.views


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Per-pair analyses in request order plus the ranking across all pairs."""

    pairs: tuple[PairAnalysis, ...]
    ranking: tuple[RankedAudience, ...]

    def pair(self, topic_id: str, project: WikiProject) -> PairAnalysis:
        """Return the analysis of one pair.

        Raises:
            KeyError: If the pair is not part of the result.
        """
        for item in self.pairs:
            if item.topic_id == topic_id and item.project == project:
                return item
        msg = f"No analysis for topic {topic_id!r} in {project.domain}"
        raise KeyError(msg)


def analyse(
    resolved: Sequence[ResolvedTopic],
    loaded: Sequence[LoadedSeries],
    *,
    weights: RankingWeights,
    settings: AnalysisSettings = _DEFAULT_SETTINGS,
) -> AnalysisResult:
    """Compute metrics, findings, reliability and ranking for every loaded pair.

    Args:
        resolved: Topics as resolved; supply the bundles (main article, context, status).
        loaded: Series fetched for those topics, in the same order.
        weights: Ranking weights from the request.
        settings: Thresholds and switches.

    Returns:
        The analysis, with pairs in the order of ``loaded``.
    """
    topics = {topic.topic_id: topic for topic in resolved}
    pairs = tuple(
        _analyse_pair(topics[item.topic_id].bundle_for(item.project), item, settings)
        for item in loaded
    )
    inputs = [
        RankingInput(
            p.topic_id, p.project, p.metrics if p.measures_topic else None, p.reliability.level
        )
        for p in pairs
    ]
    ranking = rank_audiences(inputs, weights, profiles=settings.profiles)
    return AnalysisResult(pairs=pairs, ranking=ranking)


def _analyse_pair(
    bundle: TopicBundle, item: LoadedSeries, settings: AnalysisSettings
) -> PairAnalysis:
    views = item.main_views
    if views is None or bundle.status is BundleStatus.NOT_FOUND:
        reliability = assess_reliability(
            None,
            bundle_status=BundleStatus.NOT_FOUND,
            main_source=None,
            thresholds=settings.thresholds,
        )
        return PairAnalysis(
            topic_id=item.topic_id,
            project=item.project,
            bundle=bundle,
            views=None,
            per_million=None,
            edition_total=item.project_total,
            daily=None,
            metrics=None,
            reliability=reliability,
        )

    share = per_million(views, item.project_total) if settings.normalise else None
    metrics = compute_metrics(
        views, per_million=share, daily_views=item.main_daily, settings=settings.metrics
    )
    # Diagnose the canonical main title alone: redirects have no automated counterpart.
    automated_share = compute_automated_share(item.main_user_for_automated, item.main_automated)
    metrics = replace(metrics, automated_share=automated_share)

    main = bundle.main
    reliability = assess_reliability(
        metrics,
        bundle_status=bundle.status,
        main_source=main.source if main is not None else None,
        thresholds=settings.thresholds,
        substitute_kind=bundle.substitute_kind,
    )
    return PairAnalysis(
        topic_id=item.topic_id,
        project=item.project,
        bundle=bundle,
        views=views,
        per_million=share,
        edition_total=item.project_total,
        daily=item.main_daily,
        metrics=metrics,
        reliability=reliability,
        findings=_findings(views, share, item, settings),
        context=tuple(_context_article(c, settings.metrics) for c in item.context),
    )


def _findings(
    views: Series, share: Series | None, item: LoadedSeries, settings: AnalysisSettings
) -> PairFindings:
    detectors = settings.findings
    return PairFindings(
        level_shift=detect_level_shift(share if share is not None else views, detectors),
        anomalies=find_anomalies(item.main_daily, detectors) if item.main_daily else (),
        recent=recent_change(views, detectors),
        recent_edition=recent_change(item.project_total, detectors),
        # Seasons are about when readers come, so they are read from views, not the share.
        seasonality=seasonal_profile(views, detectors),
        seasonality_strength=seasonal_strength(views.values, settings.metrics.seasonal_period),
        edition=compare_with_edition(views, item.project_total, settings.metrics, share=share),
    )


def _context_article(context: ContextSeries, settings: MetricsSettings) -> ContextArticle:
    observed = context.views.observed
    growth, _ = comparable_growth(context.views.values, settings)
    return ContextArticle(
        title=context.article.title,
        role=context.article.role,
        source=context.article.source,
        views_avg=sum(observed) / len(observed) if observed else None,
        growth=growth,
    )
