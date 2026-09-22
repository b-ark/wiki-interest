"""Use-case: turn loaded series into metrics, reliability verdicts and a ranking.

This is the numeric heart of a run. It is deliberately free of prose and rendering: the
result is a set of domain values that a later step turns into localised text, tables and
charts. Every (topic, edition) pair is analysed twice, as the weighted bundle and as the main
article alone, so a conclusion never silently depends on the bundle composition.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from wiki_interest.application.loading import LoadedSeries
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.domain.metrics import MetricsSettings, compute_metrics
from wiki_interest.domain.models import (
    ArticleRole,
    BundleStatus,
    RankedAudience,
    RankingWeights,
    Reliability,
    ReliabilityThresholds,
    Series,
    TopicBundle,
    TrendMetrics,
    WikiProject,
)
from wiki_interest.domain.ranking import ProfileThresholds, RankingInput, rank_audiences
from wiki_interest.domain.reliability import assess_reliability
from wiki_interest.domain.series import per_million

__all__ = ["AnalysisResult", "AnalysisSettings", "PairAnalysis", "analyse"]


@dataclass(frozen=True, slots=True)
class AnalysisSettings:
    """Thresholds and switches for the analysis step.

    Use :meth:`from_thresholds` so the significance level used by the metrics and by the
    reliability rule are the same number.

    Attributes:
        thresholds: Reliability rule thresholds.
        metrics: Metric computation settings (significance level, minimum observations).
        profiles: Growth cut-offs for audience profiles in the ranking.
        normalise: Whether to compute per-million series; ``False`` analyses raw views.
    """

    thresholds: ReliabilityThresholds = field(default_factory=ReliabilityThresholds)
    metrics: MetricsSettings = field(default_factory=MetricsSettings)
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
class PairAnalysis:
    """Everything computed for one (topic, edition) pair.

    Series and metrics are ``None`` when the bundle has no articles; ``reliability`` is then a
    single failing ``resolution`` check.
    """

    topic_id: str
    project: WikiProject
    bundle: TopicBundle
    bundle_views: Series | None
    bundle_per_million: Series | None
    main_views: Series | None
    main_per_million: Series | None
    metrics: TrendMetrics | None
    main_metrics: TrendMetrics | None
    reliability: Reliability

    @property
    def has_related_articles(self) -> bool:
        """Whether the bundle contains anything beyond the main article."""
        return any(a.role is not ArticleRole.MAIN for a in self.bundle.articles)


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
    """Compute metrics, reliability and ranking for every loaded (topic, edition) pair.

    Args:
        resolved: Topics as resolved; supplies the bundles (composition, status, sources).
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
    inputs = [RankingInput(p.topic_id, p.project, p.metrics, p.reliability.level) for p in pairs]
    ranking = rank_audiences(inputs, weights, profiles=settings.profiles)
    return AnalysisResult(pairs=pairs, ranking=ranking)


def _analyse_pair(
    bundle: TopicBundle, item: LoadedSeries, settings: AnalysisSettings
) -> PairAnalysis:
    if item.bundle_views is None or bundle.status is BundleStatus.NOT_FOUND:
        reliability = assess_reliability(
            None,
            bundle_status=BundleStatus.NOT_FOUND,
            main_source=None,
            thresholds=settings.thresholds,
        )
        return PairAnalysis(
            item.topic_id, item.project, bundle, None, None, None, None, None, None, reliability
        )

    bundle_pm = per_million(item.bundle_views, item.project_total) if settings.normalise else None
    metrics = compute_metrics(
        item.bundle_views,
        per_million=bundle_pm,
        daily_views=item.main_daily,
        automated_views=item.main_automated,
        settings=settings.metrics,
    )

    main_pm: Series | None = None
    main_metrics: TrendMetrics | None = None
    has_related = any(a.role is not ArticleRole.MAIN for a in bundle.articles)
    if item.main_views is not None:
        if settings.normalise:
            main_pm = per_million(item.main_views, item.project_total)
        if has_related:
            main_metrics = compute_metrics(
                item.main_views,
                per_million=main_pm,
                daily_views=item.main_daily,
                automated_views=item.main_automated,
                settings=settings.metrics,
            )

    main = bundle.main
    reliability = assess_reliability(
        metrics,
        bundle_status=bundle.status,
        main_source=main.source if main is not None else None,
        main_metrics=main_metrics,
        thresholds=settings.thresholds,
    )
    return PairAnalysis(
        topic_id=item.topic_id,
        project=item.project,
        bundle=bundle,
        bundle_views=item.bundle_views,
        bundle_per_million=bundle_pm,
        main_views=item.main_views,
        main_per_million=main_pm,
        metrics=metrics,
        main_metrics=main_metrics,
        reliability=reliability,
    )
