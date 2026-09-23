"""Use-case: turn loaded series into metrics, findings, reliability verdicts and a ranking.

This is the numeric heart of a run. It is deliberately free of prose and rendering: the
result is a set of domain values that a later step turns into localised text, tables and
charts.

What is measured is the topic's main article (with the redirects that lead to it), the same
Wikidata item in every edition, so editions are compared on the same thing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import date

from wiki_interest.application.loading import LoadedSeries
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.domain.findings import (
    Anomaly,
    EditionComparison,
    FindingsSettings,
    LevelShift,
    RecentChange,
    compare_with_edition,
    detect_level_shift,
    find_anomalies,
    recent_change,
)
from wiki_interest.domain.metrics import (
    MetricsSettings,
    compute_automated_share,
    compute_metrics,
)
from wiki_interest.domain.models import (
    BundleStatus,
    RankedAudience,
    RankingWeights,
    Reliability,
    ReliabilityThresholds,
    Series,
    SubstituteKind,
    TopicBundle,
    TrendMetrics,
    WikiProject,
)
from wiki_interest.domain.monthly_anomalies import (
    AnomalyNature,
    AnomalySettings,
    MonthlyAnomaly,
    anomaly_nature,
    explained_by_season,
    find_monthly_anomalies,
    yoy_without,
)
from wiki_interest.domain.ranking import ProfileThresholds, RankingInput, rank_audiences
from wiki_interest.domain.reliability import assess_reliability
from wiki_interest.domain.seasonality import SeasonEvidence, SeasonSettings, season_evidence
from wiki_interest.domain.series import per_million

__all__ = [
    "AnalysisResult",
    "AnalysisSettings",
    "MonthFinding",
    "PairAnalysis",
    "PairFindings",
    "analyse",
]

_MONTHS_PER_YEAR = 12
_EDITION = "edition"
"""Nature of a month in which the edition's traffic moved and the article's did not."""
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
        findings: Detector thresholds (level shifts, bursts, recent months).
        season: When a seasonal pattern on the whole history is solid.
        anomalies: Thresholds of the monthly anomaly detector.
        profiles: Growth cut-offs for audience profiles in the ranking.
        normalise: Whether to compute per-million series; ``False`` analyses raw views.
    """

    thresholds: ReliabilityThresholds = field(default_factory=ReliabilityThresholds)
    metrics: MetricsSettings = field(default_factory=MetricsSettings)
    findings: FindingsSettings = field(default_factory=FindingsSettings)
    season: SeasonSettings = field(default_factory=SeasonSettings)
    anomalies: AnomalySettings = field(default_factory=AnomalySettings)
    profiles: ProfileThresholds = field(default_factory=ProfileThresholds)
    normalise: bool = True

    @classmethod
    def from_thresholds(
        cls,
        thresholds: ReliabilityThresholds,
        *,
        normalise: bool = True,
        season: SeasonSettings | None = None,
        anomalies: AnomalySettings | None = None,
    ) -> AnalysisSettings:
        """Build settings whose trend significance level matches ``thresholds``."""
        return cls(
            thresholds=thresholds,
            metrics=MetricsSettings(alpha=thresholds.trend_p_value),
            season=season or SeasonSettings(),
            anomalies=anomalies or AnomalySettings(),
            normalise=normalise,
        )


_DEFAULT_SETTINGS = AnalysisSettings()


@dataclass(frozen=True, slots=True)
class MonthFinding:
    """A month that stands out in one or more of the pair's series.

    Attributes:
        month: The month.
        multiples: ``(metric, value / baseline)`` for every series it stands out in
            (``article_views``, ``attention_share``, ``edition_traffic``).
        nature: The probable cause (``event``, ``possible_bot``, ``unknown``), or
            ``edition`` when the edition's traffic moved and the article did not.
        in_change: Whether it lies in the months behind the headline change (the last 24).
        in_recent: Whether it lies in the recent window or its months a year earlier.
        change_without: The headline change (share, or views without normalisation) with
            this month and its twin a year off left out; ``None`` when not in the change.
    """

    month: date
    multiples: tuple[tuple[str, float], ...]
    nature: str
    in_change: bool
    in_recent: bool
    change_without: float | None


@dataclass(frozen=True, slots=True)
class PairFindings:
    """What the detectors found for one pair; see :mod:`wiki_interest.domain.findings`.

    Attributes:
        level_shift: A step in the analysed series (share, or views without normalisation).
        anomalies: Dated bursts of daily views, largest first.
        recent: Last months of views against the same months a year earlier.
        recent_edition: The same comparison for the whole edition.
        season: Calendar-month profile of the article's whole history, and whether it is
            solid enough to state.
        edition: The article's growth against the edition's over the same months.
        months: Months that stand out, with their probable cause.
    """

    level_shift: LevelShift | None = None
    anomalies: tuple[Anomaly, ...] = ()
    recent: RecentChange | None = None
    recent_edition: RecentChange | None = None
    season: SeasonEvidence | None = None
    edition: EditionComparison | None = None
    months: tuple[MonthFinding, ...] = ()


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

    @property
    def measures_topic(self) -> bool:
        """Whether the numbers describe the topic itself.

        False for a broader or mentioning article chosen in place of a missing one: such a
        pair is shown with its own numbers but never wins a headline or a ranking, because
        its views belong mostly to another subject. A redirect under the topic's name does
        measure the topic, if narrowly.
        """
        return self.bundle.substitute_kind not in _OTHER_SUBJECT


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
        resolved: Topics as resolved; supply the bundles (main article, status).
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
    )


def _findings(
    views: Series, share: Series | None, item: LoadedSeries, settings: AnalysisSettings
) -> PairFindings:
    detectors = settings.findings
    bursts = find_anomalies(item.main_daily, detectors) if item.main_daily else ()
    # Seasons are about when readers come, so they are read from views, not the share,
    # and on the whole history: two years are two observations per calendar month.
    season = season_evidence(item.main_history or views, settings.season)
    return PairFindings(
        level_shift=detect_level_shift(share if share is not None else views, detectors),
        anomalies=bursts,
        recent=recent_change(views, detectors),
        recent_edition=recent_change(item.project_total, detectors),
        season=season,
        edition=compare_with_edition(views, item.project_total, settings.metrics, share=share),
        months=_months(views, share, item, bursts=bursts, season=season, settings=settings),
    )


def _months(  # noqa: PLR0913 -- every series of the pair takes part
    views: Series,
    share: Series | None,
    item: LoadedSeries,
    *,
    bursts: tuple[Anomaly, ...],
    season: SeasonEvidence,
    settings: AnalysisSettings,
) -> tuple[MonthFinding, ...]:
    """Months that stand out in the article's views, its share or the edition's traffic.

    A month the article's usual season explains (a September peak of a school subject) is
    not an anomaly; the edition's own months are not filtered by the article's season. The
    season is trusted for this only on a long history: on two years the month itself makes
    up half of its calendar month's profile and would explain itself away.
    """
    long_enough = season.years >= settings.season.min_years
    profile = season.profile if long_enough else None

    def unusual(series: Series) -> tuple[MonthlyAnomaly, ...]:
        return tuple(
            a
            for a in find_monthly_anomalies(series, settings.anomalies)
            if not explained_by_season(a, profile)
        )

    found: dict[str, tuple[MonthlyAnomaly, ...]] = {
        "article_views": unusual(views),
        "edition_traffic": find_monthly_anomalies(item.project_total, settings.anomalies),
    }
    if share is not None:
        found["attention_share"] = unusual(share)
    by_month: dict[date, dict[str, MonthlyAnomaly]] = {}
    for metric, anomalies in found.items():
        for anomaly in anomalies:
            by_month.setdefault(anomaly.month, {})[metric] = anomaly
    headline = share if share is not None else views
    count = len(views.points)
    recent = settings.findings.recent_months
    by_access = {access.value: series for access, series in item.main_by_access}
    out: list[MonthFinding] = []
    for month, metrics in sorted(by_month.items()):
        index = next(iter(metrics.values())).index
        article = metrics.get("article_views")
        if article is not None:
            burst = any(b.start.replace(day=1) <= month <= b.end.replace(day=1) for b in bursts)
            nature = anomaly_nature(
                article,
                by_access,
                automated=item.main_automated,
                burst=burst,
                settings=settings.anomalies,
            ).value
        elif "edition_traffic" in metrics:
            nature = _EDITION
        else:
            nature = AnomalyNature.UNKNOWN.value
        in_change = index >= count - 2 * _MONTHS_PER_YEAR
        from_end = count - 1 - index
        in_recent = from_end < recent or _MONTHS_PER_YEAR <= from_end < _MONTHS_PER_YEAR + recent
        out.append(
            MonthFinding(
                month=month,
                multiples=tuple((m, a.multiple) for m, a in sorted(metrics.items())),
                nature=nature,
                in_change=in_change,
                in_recent=in_recent,
                change_without=yoy_without(headline.values, index) if in_change else None,
            )
        )
    return tuple(out)
