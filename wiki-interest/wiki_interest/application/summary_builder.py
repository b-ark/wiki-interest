"""Turn an analysis into the ``summary.json`` document, prose included.

This is where numbers become sentences. Everything the agent or the user reads (verdict,
reliability reasons, limitations, next steps, chart titles) is composed here from message
templates in the report language, so no downstream renderer ever has to invent wording and
no agent has to do arithmetic.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from wiki_interest.application.analysis import AnalysisResult, PairAnalysis
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.contracts.charts import ChartSeries, ChartSpec
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    ArticleOut,
    Artifacts,
    BundleOut,
    CandidateOut,
    CheckOut,
    Clarification,
    ComparisonRow,
    MetricsOut,
    PointOut,
    Provenance,
    RankedRow,
    ReliabilityOut,
    SeriesKind,
    SeriesOut,
    TopicResolutionOut,
    Verdict,
)
from wiki_interest.domain.models import (
    AudienceProfile,
    BundleStatus,
    RankedAudience,
    Series,
    TrendDirection,
    TrendMetrics,
    WikiProject,
)
from wiki_interest.domain.trend_tests import detrend
from wiki_interest.errors import ClarificationNeededError
from wiki_interest.i18n import Translator

__all__ = ["ProvenanceInput", "RunContext", "SummaryBuilder"]

_STRONG_SEASONALITY = 0.5
_CHARTS_DIR = "charts"
_MAX_RANK_BULLETS = 3


@dataclass(frozen=True, slots=True)
class RunContext:
    """Identity and location of one run, decided by the caller before the pipeline starts."""

    run_id: str
    session: str | None
    run_dir: Path
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class ProvenanceInput:
    """Facts about where the data came from, supplied by the composition root."""

    code_version: str
    user_agent: str
    sources: tuple[str, ...]
    request_count: int = 0
    cache_hits: int = 0


class SummaryBuilder:
    """Builds :class:`AnalysisSummary` documents in one report language."""

    def __init__(
        self, translator: Translator, context: RunContext, provenance: ProvenanceInput
    ) -> None:
        self._t = translator
        self._context = context
        self._provenance_input = provenance

    # -- entry points ---------------------------------------------------------------------

    def build(
        self,
        *,
        request: AnalysisRequest,
        period: Period,
        resolved: Sequence[ResolvedTopic],
        analysis: AnalysisResult,
    ) -> AnalysisSummary:
        """Compose the full summary of a successful run."""
        context = self._context
        labels = _TopicLabels(resolved)
        normalised = request.normalization == "per_million"
        charts = self._charts(request, period, analysis, labels, normalised)
        return AnalysisSummary(
            status="ok",
            run_id=context.run_id,
            session=context.session,
            request=request,
            period=period,
            resolution=[self._resolution_out(topic) for topic in resolved],
            series=list(self._series_out(analysis)),
            metrics=list(self._metrics_out(analysis)),
            reliability=[self._reliability_out(pair) for pair in analysis.pairs],
            comparison=[self._comparison_row(pair, labels) for pair in analysis.pairs],
            ranking=self._ranking_rows(request, analysis, labels),
            charts=charts,
            verdict=self._verdict(request, analysis, labels, normalised),
            limitations=self._limitations(request, period, resolved, analysis, labels),
            next_steps=self._next_steps(request, period, resolved, analysis, labels),
            artifacts=_artifacts(context, request, [c.id for c in charts]),
            provenance=self._provenance(period),
        )

    def build_clarification(
        self,
        *,
        request: AnalysisRequest,
        period: Period,
        error: ClarificationNeededError,
    ) -> AnalysisSummary:
        """Compose the summary of a run that stopped to ask the user a question."""
        context = self._context
        topic = next((t for t in request.topics if t.id == error.topic_id), request.topics[0])
        question = self._t.t(
            f"question.{request.question_type}",
            topics=", ".join(t.query for t in request.topics),
            projects=", ".join(request.projects),
        )
        return AnalysisSummary(
            status="needs_clarification",
            run_id=context.run_id,
            session=context.session,
            request=request,
            period=period,
            verdict=Verdict(headline=question),
            artifacts=_artifacts(context, request, []),
            provenance=self._provenance(period),
            clarification=Clarification(
                topic_id=error.topic_id,
                query=topic.query,
                question=self._t.t("summary.clarification_hint"),
                candidates=[
                    CandidateOut(qid=c.qid, label=c.label, description=c.description)
                    for c in error.candidates
                ],
            ),
        )

    # -- resolution -----------------------------------------------------------------------

    @staticmethod
    def resolution_out(topic: ResolvedTopic) -> TopicResolutionOut:
        """Contract view of a resolved topic (also used by the ``resolve`` command)."""
        return SummaryBuilder._resolution_out(topic)

    @staticmethod
    def _resolution_out(topic: ResolvedTopic) -> TopicResolutionOut:
        return TopicResolutionOut(
            topic_id=topic.topic_id,
            query=topic.query,
            label=topic.label,
            qid=topic.qid,
            bundles=[
                BundleOut(
                    topic_id=bundle.topic_id,
                    project=bundle.project.domain,
                    status=bundle.status,
                    articles=[
                        ArticleOut(
                            title=a.title,
                            role=a.role,
                            source=a.source,
                            weight=a.weight,
                            qid=a.qid,
                            redirects=list(a.redirects),
                        )
                        for a in bundle.articles
                    ],
                )
                for bundle in topic.bundles
            ],
        )

    # -- series and metrics ---------------------------------------------------------------

    @staticmethod
    def _series_out(analysis: AnalysisResult) -> list[SeriesOut]:
        out: list[SeriesOut] = []
        for pair in analysis.pairs:
            if pair.bundle_views is not None:
                out.append(_series_out(pair, "bundle", pair.bundle_views, pair.bundle_per_million))
            if pair.main_views is not None and pair.has_related_articles:
                out.append(_series_out(pair, "main", pair.main_views, pair.main_per_million))
        return out

    @staticmethod
    def _metrics_out(analysis: AnalysisResult) -> list[MetricsOut]:
        out: list[MetricsOut] = []
        for pair in analysis.pairs:
            if pair.metrics is not None:
                out.append(_metrics_out(pair, "bundle", pair.metrics))
            if pair.main_metrics is not None:
                out.append(_metrics_out(pair, "main", pair.main_metrics))
        return out

    def _reliability_out(self, pair: PairAnalysis) -> ReliabilityOut:
        # The domain rules do not know article titles; the resolution messages name the
        # article the reader should verify, so the title is supplied here.
        context: dict[str, float | int | str] = {}
        if pair.bundle.main is not None:
            context["title"] = pair.bundle.main.title
        checks: list[CheckOut] = []
        for check in pair.reliability.checks:
            params = {**context, **check.params}
            checks.append(
                CheckOut(
                    name=check.name,
                    status=check.status,
                    message=self._t.t(check.reason_key, **params),
                    reason_key=check.reason_key,
                    params=params,
                )
            )
        return ReliabilityOut(
            topic_id=pair.topic_id,
            project=pair.project.domain,
            level=pair.reliability.level,
            checks=checks,
        )

    # -- tables ---------------------------------------------------------------------------

    def _comparison_row(self, pair: PairAnalysis, labels: _TopicLabels) -> ComparisonRow:
        metrics = pair.metrics
        note: str | None = None
        if pair.bundle.status is BundleStatus.NOT_FOUND:
            note = self._t.t("note.not_found")
        elif pair.bundle.status is BundleStatus.FOUND_VIA_SEARCH:
            note = self._t.t("note.search_fallback")
        return ComparisonRow(
            topic_id=pair.topic_id,
            project=pair.project.domain,
            label=labels.topic(pair.topic_id),
            views_avg=metrics.views_avg if metrics else None,
            per_million_avg=metrics.per_million_avg if metrics else None,
            growth_yoy=metrics.growth_yoy if metrics else None,
            growth_halves=metrics.growth_halves if metrics else None,
            trend_direction=metrics.trend_direction if metrics else TrendDirection.UNKNOWN,
            reliability=pair.reliability.level,
            note=note,
        )

    def _ranking_rows(
        self, request: AnalysisRequest, analysis: AnalysisResult, labels: _TopicLabels
    ) -> list[RankedRow]:
        if request.question_type != "rank":
            return []
        rows: list[RankedRow] = []
        for rank, item in enumerate(analysis.ranking, start=1):
            pair = analysis.pair(item.topic_id, item.project)
            rows.append(
                RankedRow(
                    rank=rank,
                    topic_id=item.topic_id,
                    project=item.project.domain,
                    label=labels.topic(item.topic_id),
                    score=round(item.score, 4),
                    components={k: round(v, 4) for k, v in item.components.items()},
                    profile=item.profile,
                    reliability=item.reliability,
                    rationale=self._rationale(item, pair.metrics),
                )
            )
        return rows

    def _rationale(self, item: RankedAudience, metrics: TrendMetrics | None) -> str:
        if metrics is None or _growth(metrics) is None:
            return self._t.t("rank.rationale.insufficient")
        return self._t.t(
            "rank.rationale",
            profile=self._t.label("profile", item.profile),
            growth=self._t.percent(_growth(metrics), signed=True),
            views=self._t.number(metrics.views_avg),
            level=self._t.label("level", item.reliability),
        )

    # -- charts ---------------------------------------------------------------------------

    def _charts(
        self,
        request: AnalysisRequest,
        period: Period,
        analysis: AnalysisResult,
        labels: _TopicLabels,
        normalised: bool,
    ) -> list[ChartSpec]:
        footnote = self._t.t(
            "chart.footnote", source="Wikimedia Pageviews API", period=_period_text(period)
        )
        y_label = self._t.t("chart.axis_per_million" if normalised else "chart.axis_views")
        with_data = [p for p in analysis.pairs if p.bundle_views is not None]
        if not with_data:
            return []
        charts: list[ChartSpec] = []
        if request.question_type == "assess":
            charts.extend(
                self._trend_chart(pair, labels, normalised, y_label, footnote) for pair in with_data
            )
        else:
            charts.append(
                ChartSpec(
                    id="interest-over-time",
                    kind="lines",
                    title=self._t.t("chart.compare_title"),
                    y_label=y_label,
                    series=[
                        ChartSeries(
                            label=labels.pair(pair.topic_id, pair.project),
                            x=_x_labels(_analysis_series(pair, normalised)),
                            y=list(_analysis_series(pair, normalised).values),
                        )
                        for pair in with_data
                    ],
                    footnote=footnote,
                )
            )
        growth_chart = self._growth_chart(with_data, labels, footnote)
        if growth_chart is not None:
            charts.append(growth_chart)
        if request.question_type == "rank" and analysis.ranking:
            charts.append(
                ChartSpec(
                    id="ranking-score",
                    kind="bars",
                    title=self._t.t("chart.score_title"),
                    y_label=self._t.t("chart.axis_score"),
                    series=[
                        ChartSeries(
                            label=self._t.t("chart.score_title"),
                            x=[labels.pair(r.topic_id, r.project) for r in analysis.ranking],
                            y=[round(r.score, 4) for r in analysis.ranking],
                        )
                    ],
                    footnote=footnote,
                )
            )
        return charts

    def _trend_chart(
        self,
        pair: PairAnalysis,
        labels: _TopicLabels,
        normalised: bool,
        y_label: str,
        footnote: str,
    ) -> ChartSpec:
        series = _analysis_series(pair, normalised)
        values = list(series.values)
        residuals = detrend(values)
        trend_y = [
            None if v is None or r is None else v - r
            for v, r in zip(values, residuals, strict=True)
        ]
        return ChartSpec(
            id=f"trend-{pair.topic_id}-{pair.project.language}",
            kind="trend",
            title=f"{self._t.t('chart.trend_title')}: {labels.pair(pair.topic_id, pair.project)}",
            y_label=y_label,
            series=[
                ChartSeries(
                    label=labels.pair(pair.topic_id, pair.project), x=_x_labels(series), y=values
                )
            ],
            trend_y=trend_y,
            footnote=footnote,
        )

    def _growth_chart(
        self, pairs: Sequence[PairAnalysis], labels: _TopicLabels, footnote: str
    ) -> ChartSpec | None:
        use_yoy = all(p.metrics is not None and p.metrics.growth_yoy is not None for p in pairs)
        values: list[float | None] = []
        for pair in pairs:
            metrics = pair.metrics
            growth = None
            if metrics is not None:
                growth = metrics.growth_yoy if use_yoy else metrics.growth_halves
            values.append(None if growth is None else round(growth * 100, 1))
        if all(v is None for v in values):
            return None
        title_key = "chart.growth_title" if use_yoy else "chart.growth_halves_title"
        return ChartSpec(
            id="growth",
            kind="bars",
            title=self._t.t(title_key),
            y_label=self._t.t("chart.axis_growth"),
            series=[
                ChartSeries(
                    label=self._t.t(title_key),
                    x=[labels.pair(p.topic_id, p.project) for p in pairs],
                    y=values,
                )
            ],
            footnote=footnote,
        )

    # -- prose ----------------------------------------------------------------------------

    def _verdict(
        self,
        request: AnalysisRequest,
        analysis: AnalysisResult,
        labels: _TopicLabels,
        normalised: bool,
    ) -> Verdict:
        with_data = [p for p in analysis.pairs if p.metrics is not None]
        if not with_data:
            headline = self._t.t(
                "verdict.none.headline",
                topics=", ".join(labels.topic(t) for t in labels.topic_ids),
                projects=", ".join(request.projects),
            )
            return Verdict(headline=headline)
        if request.question_type == "assess":
            headline = self._assess_headline(with_data[0], labels)
        elif request.question_type == "rank":
            headline = self._rank_headline(analysis, labels)
        else:
            headline = self._compare_headline(with_data, labels, normalised)
        return Verdict(headline=headline, bullets=self._bullets(analysis, labels, normalised))

    def _assess_headline(self, pair: PairAnalysis, labels: _TopicLabels) -> str:
        metrics = pair.metrics
        assert metrics is not None
        return self._t.t(
            "verdict.assess.headline",
            topic=labels.topic(pair.topic_id),
            project=pair.project.domain,
            direction=metrics.trend_direction,
            growth=self._t.percent(_growth(metrics), signed=True),
            level=self._t.label("level", pair.reliability.level),
        )

    def _compare_headline(
        self, pairs: Sequence[PairAnalysis], labels: _TopicLabels, normalised: bool
    ) -> str:
        def share(pair: PairAnalysis) -> float:
            metrics = pair.metrics
            assert metrics is not None
            value = metrics.per_million_avg if normalised else metrics.views_avg
            return value if value is not None else float("-inf")

        def growth(pair: PairAnalysis) -> float:
            metrics = pair.metrics
            assert metrics is not None
            value = _growth(metrics)
            return value if value is not None else float("-inf")

        top_share = max(pairs, key=share)
        top_growth = max(pairs, key=growth)
        top_share_value = share(top_share)
        key = "verdict.compare.headline" if normalised else "verdict.compare.absolute_headline"
        return self._t.t(
            key,
            top_share_label=labels.pair(top_share.topic_id, top_share.project),
            top_share=self._t.number(top_share_value, 1 if normalised else 0),
            top_growth_label=labels.pair(top_growth.topic_id, top_growth.project),
            top_growth=self._t.percent(
                None if growth(top_growth) == float("-inf") else growth(top_growth), signed=True
            ),
        )

    def _rank_headline(self, analysis: AnalysisResult, labels: _TopicLabels) -> str:
        best = analysis.ranking[0]
        return self._t.t(
            "verdict.rank.headline",
            label=labels.pair(best.topic_id, best.project),
            profile=self._t.label("profile", best.profile),
            score=self._t.number(best.score, 2),
        )

    def _bullets(
        self, analysis: AnalysisResult, labels: _TopicLabels, normalised: bool
    ) -> list[str]:
        bullets: list[str] = []
        for pair in analysis.pairs:
            label = labels.pair(pair.topic_id, pair.project)
            metrics = pair.metrics
            if metrics is None:
                bullets.append(self._t.t("verdict.bullet.not_found", label=label))
                continue
            level = self._t.label("level", pair.reliability.level)
            growth = self._t.percent(_growth(metrics), signed=True)
            if normalised:
                bullets.append(
                    self._t.t(
                        "verdict.bullet.pair",
                        label=label,
                        per_million=self._t.number(metrics.per_million_avg, 1),
                        views=self._t.number(metrics.views_avg),
                        growth=growth,
                        level=level,
                    )
                )
            else:
                bullets.append(
                    self._t.t(
                        "verdict.bullet.pair_absolute",
                        label=label,
                        views=self._t.number(metrics.views_avg),
                        growth=growth,
                        level=level,
                    )
                )
            strength = metrics.seasonality_strength
            if strength is not None and strength >= _STRONG_SEASONALITY:
                bullets.append(
                    self._t.t(
                        "verdict.bullet.seasonality",
                        label=label,
                        strength=self._t.percent(strength),
                    )
                )
            main = pair.main_metrics
            if main is not None and main.trend_direction is not metrics.trend_direction:
                bullets.append(
                    self._t.t(
                        "verdict.bullet.main_vs_bundle",
                        label=label,
                        direction=main.trend_direction,
                        growth=self._t.percent(_growth(main), signed=True),
                    )
                )
        return bullets

    def _limitations(
        self,
        request: AnalysisRequest,
        period: Period,
        resolved: Sequence[ResolvedTopic],
        analysis: AnalysisResult,
        labels: _TopicLabels,
    ) -> list[str]:
        out = [
            self._t.t("limitation.proxy"),
            self._t.t("limitation.coverage"),
            self._t.t("limitation.bots"),
        ]
        if any(p.has_related_articles for p in analysis.pairs):
            out.append(self._t.t("limitation.bundle"))
        if request.normalization == "absolute":
            out.append(self._t.t("limitation.absolute"))
        if period.months < _MIN_MONTHS_FOR_YOY:
            out.append(self._t.t("limitation.short_window", months=period.months))
        for topic in resolved:
            not_found = [
                b.project.domain for b in topic.bundles if b.status is BundleStatus.NOT_FOUND
            ]
            if not_found:
                out.append(
                    self._t.t(
                        "limitation.not_found",
                        topic=labels.topic(topic.topic_id),
                        projects=", ".join(not_found),
                    )
                )
            searched = [
                b.project.domain for b in topic.bundles if b.status is BundleStatus.FOUND_VIA_SEARCH
            ]
            if searched:
                out.append(self._t.t("limitation.search_fallback", projects=", ".join(searched)))
            if topic.missing_titles:
                titles = ", ".join(f"{title} ({p.domain})" for p, title in topic.missing_titles)
                out.append(self._t.t("limitation.missing_titles", titles=titles))
        return out

    def _next_steps(
        self,
        request: AnalysisRequest,
        period: Period,
        resolved: Sequence[ResolvedTopic],
        analysis: AnalysisResult,
        labels: _TopicLabels,
    ) -> list[str]:
        out: list[str] = []
        if period.months < _LONG_WINDOW_MONTHS:
            out.append(self._t.t("next.extend_period"))
        not_found = sorted(
            {
                b.project.domain
                for topic in resolved
                for b in topic.bundles
                if b.status is BundleStatus.NOT_FOUND
            }
        )
        if not_found:
            out.append(self._t.t("next.pin_title", projects=", ".join(not_found)))
        if any(p.has_related_articles for p in analysis.pairs):
            out.append(self._t.t("next.prune_bundle"))
        if request.question_type == "rank":
            for item in analysis.ranking[:_MAX_RANK_BULLETS]:
                if item.profile is not AudienceProfile.INSUFFICIENT_DATA:
                    out.append(
                        self._t.t(
                            "next.research",
                            label=labels.pair(item.topic_id, item.project),
                            profile=self._t.label("profile", item.profile),
                        )
                    )
        elif len(request.projects) <= _FEW_PROJECTS:
            out.append(self._t.t("next.add_projects", projects=", ".join(request.projects)))
        if request.normalization == "per_million":
            out.append(self._t.t("next.absolute"))
        else:
            out.append(self._t.t("next.per_million"))
        return out

    def _provenance(self, period: Period) -> Provenance:
        provenance = self._provenance_input
        return Provenance(
            code_version=provenance.code_version,
            generated_at=self._context.generated_at,
            data_through=period.end.strftime("%Y-%m"),
            user_agent=provenance.user_agent,
            sources=list(provenance.sources),
            request_count=provenance.request_count,
            cache_hits=provenance.cache_hits,
        )


_MIN_MONTHS_FOR_YOY = 24
_LONG_WINDOW_MONTHS = 36
_FEW_PROJECTS = 3


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _TopicLabels:
    """Human-readable labels for topics and (topic, project) pairs."""

    def __init__(self, resolved: Sequence[ResolvedTopic]) -> None:
        self._labels = {t.topic_id: (t.label or t.query) for t in resolved}
        self.topic_ids = tuple(self._labels)

    def topic(self, topic_id: str) -> str:
        return self._labels.get(topic_id, topic_id)

    def pair(self, topic_id: str, project: WikiProject) -> str:
        if len(self._labels) == 1:
            return project.domain
        return f"{self.topic(topic_id)} · {project.domain}"


def _growth(metrics: TrendMetrics) -> float | None:
    """Best available growth figure: year over year, else halves, else the fitted slope."""
    if metrics.growth_yoy is not None:
        return metrics.growth_yoy
    if metrics.growth_halves is not None:
        return metrics.growth_halves
    return metrics.slope_per_year


def _analysis_series(pair: PairAnalysis, normalised: bool) -> Series:
    series = pair.bundle_per_million if normalised else pair.bundle_views
    assert series is not None
    return series


def _x_labels(series: Series) -> list[str]:
    return [p.period.strftime("%Y-%m") for p in series.points]


def _period_text(period: Period) -> str:
    return f"{period.start:%Y-%m}..{period.end:%Y-%m}"


def _series_out(
    pair: PairAnalysis, kind: SeriesKind, views: Series, per_million: Series | None
) -> SeriesOut:
    pm_values = per_million.values if per_million is not None else (None,) * len(views)
    return SeriesOut(
        topic_id=pair.topic_id,
        project=pair.project.domain,
        kind=kind,
        granularity=views.granularity,
        points=[
            PointOut(period=p.period.strftime("%Y-%m"), views=p.value, per_million=pm)
            for p, pm in zip(views.points, pm_values, strict=True)
        ],
    )


def _metrics_out(pair: PairAnalysis, kind: SeriesKind, metrics: TrendMetrics) -> MetricsOut:
    return MetricsOut(
        topic_id=pair.topic_id,
        project=pair.project.domain,
        kind=kind,
        periods=metrics.periods,
        completeness=metrics.completeness,
        views_total=metrics.views_total,
        views_avg=metrics.views_avg,
        per_million_avg=metrics.per_million_avg,
        growth_yoy=metrics.growth_yoy,
        growth_halves=metrics.growth_halves,
        slope_per_year=metrics.slope_per_year,
        trend_p_value=metrics.trend_p_value,
        trend_direction=metrics.trend_direction,
        seasonality_strength=metrics.seasonality_strength,
        spike_share=metrics.spike_share,
        volatility_cv=metrics.volatility_cv,
        automated_share=metrics.automated_share,
    )


def _artifacts(
    context: RunContext, request: AnalysisRequest, chart_ids: Sequence[str]
) -> Artifacts:
    run_dir = context.run_dir
    formats = request.report.formats
    return Artifacts(
        run_dir=str(run_dir),
        summary_json=str(run_dir / "summary.json"),
        summary_md=str(run_dir / "summary.md"),
        report_md=str(run_dir / "report.md") if "md" in formats else None,
        report_pdf=str(run_dir / "report.pdf") if "pdf" in formats else None,
        charts=[str(run_dir / _CHARTS_DIR / f"{chart_id}.png") for chart_id in chart_ids],
    )
