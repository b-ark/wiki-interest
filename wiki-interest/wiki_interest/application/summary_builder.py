"""Turn an analysis into the ``summary.json`` document, prose included.

This is where numbers become sentences. Everything the agent or the user reads (the answer,
the per-audience assessments, reliability reasons, limitations, next steps, chart titles) is
composed here from message templates in the report language, so no downstream renderer ever
has to invent wording and no agent has to do arithmetic.

The answer is built from the decision layer (:mod:`wiki_interest.application.assessment`):
one sentence on the size of interest against the alternatives, one on where it is heading,
one on what that means. The same categories give each audience its decision line and the
report its next step, so the answer, the cards and the recommendations cannot disagree.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from wiki_interest.application.analysis import AnalysisResult, MonthFinding, PairAnalysis
from wiki_interest.application.assessment import (
    Conclusion,
    Evidence,
    PairAssessment,
    assess,
    conclude,
    headline_growth,
)
from wiki_interest.application.chart_plan import (
    AUDIENCE_CHART_ID,
    SHARE_CHART_ID,
    ChartPlanner,
    audience_years_data,
    share_years_data,
)
from wiki_interest.application.coverage import CoverageGap, CoverageOption
from wiki_interest.application.insights import (
    Insight,
    InsightSettings,
    ParamValue,
    SeasonVisibility,
    season_visibility,
    select_insights,
)
from wiki_interest.application.observations import outcome_cautions, to_out, trend_start
from wiki_interest.application.question import option_text
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.contracts.charts import ChartSpec
from wiki_interest.contracts.request import (
    AnalysisRequest,
    Period,
    SubstituteChoice,
    SubstituteSpec,
)
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    ArticleOut,
    Artifacts,
    AssessmentOut,
    BundleOut,
    CandidateOut,
    CheckOut,
    Clarification,
    ComparisonRow,
    CoverageGapOut,
    CoverageOptionOut,
    DataQualityOut,
    DecisionOut,
    EvidenceOut,
    FindingOut,
    MetricsOut,
    MonthOut,
    PointOut,
    Provenance,
    RankedRow,
    ReliabilityOut,
    SeasonOut,
    SeriesOut,
    TopicResolutionOut,
    Verdict,
)
from wiki_interest.domain.assessment import (
    AssessmentSettings,
    Momentum,
    Robustness,
    divergence,
)
from wiki_interest.domain.models import (
    AudienceProfile,
    BundleStatus,
    CheckStatus,
    RankedAudience,
    ReliabilityLevel,
    TopicBundle,
    TrendDirection,
    TrendMetrics,
    WikiProject,
)
from wiki_interest.domain.observations import Observation, PairHistory
from wiki_interest.errors import ClarificationNeededError, TopicNotFoundError
from wiki_interest.i18n import Translator

__all__ = ["ProvenanceInput", "RunContext", "SummaryBuilder", "period_notes"]

_CHARTS_DIR = "charts"
_MAX_RANK_BULLETS = 3
_MAX_ALTERNATIVES = 4
_SMALL_SHARE = 0.1
"""Shares below this are shown with one decimal (``0.8 %``), larger ones as whole percent."""
_SMALL_VALUE = 100.0
"""Numbers below this get one decimal (per-million shares), larger ones none (views)."""
_MONTH_PARAMS = frozenset({"peak_month", "trough_month"})
_SIGNED_PERCENT_PARAMS = frozenset({"change", "edition_change", "peak", "trough"})
_MULTIPLE_PARAMS = frozenset({"multiple"})
_COUNT_PARAMS = frozenset({"peak_views", "baseline"})
"""Views are whole numbers whatever their size; a baseline of "83,0" views reads oddly."""
_MAX_ANSWER_ITEMS = 5
_INFERENCE_CHECKS = frozenset({"trend"})
"""Reliability checks that judge the conclusion, not the data."""
"""Audiences named in one answer sentence; the table lists all of them."""
_SENTENCE_END = (".", "!", "?", "…")
_GROWTH_CONCLUSIONS = frozenset({"strong", "emerging", "single_growing"})
_DEMAND_CONCLUSIONS = frozenset(
    {"no_growth", "no_growth_ranked", "no_growth_split", "single_flat", "single_declining"}
)


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
    thresholds: Mapping[str, float | int | bool] | None = None


class SummaryBuilder:
    """Builds :class:`AnalysisSummary` documents in one report language."""

    def __init__(
        self,
        translator: Translator,
        context: RunContext,
        provenance: ProvenanceInput,
        insight_settings: InsightSettings | None = None,
        assessment_settings: AssessmentSettings | None = None,
    ) -> None:
        self._t = translator
        self._context = context
        self._provenance_input = provenance
        self._insight_settings = insight_settings or InsightSettings()
        self._assessment_settings = assessment_settings or AssessmentSettings()

    # -- entry points ---------------------------------------------------------------------

    def build(  # noqa: PLR0913 -- a run's every result goes into its summary
        self,
        *,
        request: AnalysisRequest,
        period: Period,
        resolved: Sequence[ResolvedTopic],
        analysis: AnalysisResult,
        observations: Sequence[Observation] = (),
        histories: Sequence[PairHistory] = (),
    ) -> AnalysisSummary:
        """Compose the full summary of a successful run.

        Args:
            request: The request.
            period: The analysed period.
            resolved: The resolved topics.
            analysis: The measured pairs.
            observations: What the detectors found (:func:`run_observations`); editions
                without an article or with a substitute add their cautions here.
            histories: The pairs' long series (:func:`pair_histories`), for the main chart.
        """
        context = self._context
        labels = _TopicLabels(resolved)
        normalised = request.normalization == "per_million"
        season_requested = request.report.seasonality == "show"
        charts = self._charts(request, analysis, labels)
        start = trend_start(request, period)
        topic_labels = {t.topic_id: labels.topic(t.topic_id) for t in resolved}
        share_chart = share_years_data(
            histories,
            observations,
            trend_start=start,
            absolute=not normalised,
            topic_labels=topic_labels,
        )
        # With raw views asked for, the main chart shows the views already.
        audience_chart = (
            audience_years_data(histories, trend_start=start, topic_labels=topic_labels)
            if normalised
            else None
        )
        insights = select_insights(
            analysis, self._insight_settings, season_requested=season_requested
        )
        findings = self._findings_out(insights, labels)
        assessments = assess(analysis, normalised=normalised, settings=self._assessment_settings)
        ranked = (
            [(r.topic_id, r.project) for r in analysis.ranking]
            if request.question_type == "rank"
            else []
        )
        conclusion = conclude(assessments, ranked)
        assessment_outs = [
            self._assessment_out(pair, item, labels, season_requested=season_requested)
            for pair, item in zip(analysis.pairs, assessments, strict=True)
        ]
        topics = {t.topic_id: labels.topic(t.topic_id) for t in resolved}
        cautions = outcome_cautions(assessment_outs, topics)
        return AnalysisSummary(
            status="ok",
            run_id=context.run_id,
            session=context.session,
            request=request,
            period=period,
            resolution=[self._resolution_out(topic) for topic in resolved],
            series=self._series_out(analysis),
            metrics=self._metrics_out(analysis),
            reliability=[self._reliability_out(pair) for pair in analysis.pairs],
            comparison=self._comparison_rows(analysis, labels),
            ranking=self._ranking_rows(request, analysis, labels),
            charts=charts,
            share_chart=share_chart,
            audience_chart=audience_chart,
            verdict=self._verdict(
                request,
                analysis,
                labels,
                findings=findings,
                assessments=assessments,
            ),
            happening=self._happening(assessments, labels, normalised=normalised),
            assessments=assessment_outs,
            decision=self._decision_out(conclusion, assessments, labels),
            data_note=self._data_note(analysis, assessments, labels),
            findings=findings,
            observations=to_out([*cautions, *observations]),
            limitations=self._limitations(request, period, resolved, labels),
            general_limitations=self._general_limitations(),
            next_steps=self._next_steps(request, period, resolved, analysis, labels),
            artifacts=_artifacts(
                context,
                [
                    *([SHARE_CHART_ID] if share_chart else []),
                    *([AUDIENCE_CHART_ID] if audience_chart else []),
                    *(c.id for c in charts),
                ],
            ),
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
            artifacts=_question_artifacts(context),
            provenance=self._provenance(period),
            clarification=Clarification(
                topic_id=error.topic_id,
                query=topic.query,
                question=self._which(topic.query, from_search=error.from_search),
                from_search=error.from_search,
                candidates=[
                    CandidateOut(
                        qid=c.qid,
                        label=c.label,
                        description=c.description,
                        article_projects=list(error.coverage.get(c.qid, ())),
                    )
                    for c in error.candidates
                ],
            ),
        )

    def _which(self, query: str, *, from_search: bool) -> str:
        """The meaning question; for the guesses of a text search, with what to do if none fits.

        The agent reads this line in the run's output (``hint``), not only in ``summary.md``.
        """
        if not from_search:
            return self._t.t("summary.which_meaning", query=query)
        which = self._t.t("summary.which_article", query=query)
        return f"{which} {self._t.t('summary.search_hint')}"

    def build_topic_only(
        self,
        *,
        request: AnalysisRequest,
        period: Period,
        resolved: Sequence[ResolvedTopic],
    ) -> AnalysisSummary:
        """Compose the summary of a run stopped after the topic stage (evaluation mode)."""
        context = self._context
        return AnalysisSummary(
            status="topic_resolved",
            run_id=context.run_id,
            session=context.session,
            request=request,
            period=period,
            resolution=[self._resolution_out(topic) for topic in resolved],
            verdict=Verdict(headline=self._t.t("summary.topic_only")),
            artifacts=_question_artifacts(context),
            provenance=self._provenance(period),
        )

    def build_not_found(
        self, *, request: AnalysisRequest, period: Period, error: TopicNotFoundError
    ) -> AnalysisSummary:
        """Compose the summary of a run that found nothing for a topic and asks for a link."""
        context = self._context
        return AnalysisSummary(
            status="needs_clarification",
            run_id=context.run_id,
            session=context.session,
            request=request,
            period=period,
            verdict=Verdict(headline=self._t.t("notfound.headline", query=error.query)),
            artifacts=_question_artifacts(context),
            provenance=self._provenance(period),
            clarification=Clarification(
                kind="topic_not_found",
                topic_id=error.topic_id,
                query=error.query,
                question=self._t.t("summary.not_found_hint", language=request.report.language),
            ),
        )

    def build_coverage_question(
        self,
        *,
        request: AnalysisRequest,
        period: Period,
        gaps: Sequence[CoverageGap],
    ) -> AnalysisSummary:
        """Compose the summary of a run that stopped because editions have no article.

        Nothing has been measured yet: the summary holds only the question, the options with
        their views, and for each option the exact ``choose`` value to put into the request.
        """
        context = self._context
        projects = list(dict.fromkeys(gap.project.domain for gap in gaps))
        return AnalysisSummary(
            status="needs_clarification",
            run_id=context.run_id,
            session=context.session,
            request=request,
            period=period,
            verdict=Verdict(headline=self._t.t("gap.headline", projects=", ".join(projects))),
            artifacts=_question_artifacts(context),
            provenance=self._provenance(period),
            clarification=Clarification(
                kind="missing_article",
                topic_id=gaps[0].topic_id,
                query=gaps[0].query,
                question=self._t.t("summary.missing_hint", language=request.report.language),
                gaps=[self._gap_out(gap, request.projects) for gap in gaps],
            ),
        )

    def _gap_out(self, gap: CoverageGap, requested: Sequence[str]) -> CoverageGapOut:
        t = self._t
        domain = gap.project.domain
        question = t.t("gap.question", topic=gap.query, project=domain)
        if gap.terms:
            searched = ", ".join(t.t("gap.term", term=term) for term in gap.terms)
            question += " " + t.t("gap.searched", terms=searched)
        else:
            question += " " + t.t("gap.no_terms")
        kinds = {option.kind for option in gap.options}
        if kinds & {"redirect", "broader"}:
            question += " " + t.t("gap.broader_intro")
        elif "mention" in kinds:
            question += " " + t.t("gap.mention_intro")
        entity = gap.entity
        return CoverageGapOut(
            topic_id=gap.topic_id,
            query=gap.query,
            project=domain,
            qid=entity.qid if entity else None,
            label=entity.label if entity else None,
            description=entity.description if entity else None,
            article_languages=list(entity.languages) if entity else [],
            matched_in_english=gap.matched_in_english,
            topic_note=self._topic_note(gap, requested),
            terms=list(gap.terms),
            question=question,
            options=[
                self._option_out(number, domain, option)
                for number, option in enumerate(gap.options, start=1)
            ],
        )

    def _topic_note(self, gap: CoverageGap, requested: Sequence[str]) -> str:
        """Which entity the topic is and where it has articles, in one or two sentences."""
        t = self._t
        entity = gap.entity
        if entity is None:
            return t.t("gap.no_entity")
        description = (
            t.t("gap.entity_description", description=entity.description)
            if entity.description
            else ""
        )
        params = {"label": entity.label or gap.query, "description": description, "qid": entity.qid}
        if entity.languages:
            note = t.t(
                "gap.entity",
                **params,
                count=len(entity.languages),
                languages=", ".join(_language_sample(entity.languages, requested)),
            )
        else:
            note = t.t("gap.entity_nowhere", **params)
        if gap.matched_in_english:
            note += " " + t.t("gap.matched_en")
        return note

    def _option_out(self, number: int, domain: str, option: CoverageOption) -> CoverageOptionOut:
        choose: dict[str, SubstituteChoice]
        url: str | None = None
        if option.kind == "skip" or option.title is None:
            choose = {domain: "skip"}
        else:
            # The article a reader would open: a redirect's target, at its section.
            article = option.target or option.title
            url = WikiProject.parse(domain).article_url(article, option.section)
            choose = {domain: SubstituteSpec(title=option.title, kind=option.kind)}
        out = CoverageOptionOut(
            number=number,
            kind=option.kind,
            title=option.title,
            target=option.target,
            section=option.section,
            snippet=option.snippet,
            views_avg=option.views_avg,
            description="",
            url=url,
            choose=choose,
        )
        return out.model_copy(update={"description": option_text(out, domain, self._t)})

    # -- resolution -----------------------------------------------------------------------

    @staticmethod
    def _resolution_out(topic: ResolvedTopic) -> TopicResolutionOut:
        return TopicResolutionOut(
            topic_id=topic.topic_id,
            query=topic.query,
            label=topic.label,
            qid=topic.qid,
            description=topic.description,
            matched_in_english=topic.matched_in_english,
            method=topic.method,  # type: ignore[arg-type]  # validated by the contract
            confidence=topic.confidence,
            runner_up=topic.runner_up,
            alternatives=[
                CandidateOut(qid=c.qid, label=c.label, description=c.description)
                for c in topic.alternatives[:_MAX_ALTERNATIVES]
            ],
            bundles=[
                BundleOut(
                    topic_id=bundle.topic_id,
                    project=bundle.project.domain,
                    status=bundle.status,
                    article_count=len(bundle.articles),
                    redirect_count=len(bundle.main.redirects) if bundle.main else 0,
                    substitute_kind=bundle.substitute_kind,
                    articles=[
                        ArticleOut(
                            title=a.title,
                            role=a.role,
                            source=a.source,
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
        return [_series_out(pair) for pair in analysis.pairs if pair.views is not None]

    @staticmethod
    def _metrics_out(analysis: AnalysisResult) -> list[MetricsOut]:
        return [_metrics_out(pair, pair.metrics) for pair in analysis.pairs if pair.metrics]

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

    def _comparison_rows(
        self, analysis: AnalysisResult, labels: _TopicLabels
    ) -> list[ComparisonRow]:
        leaders: dict[str, float] = {}
        for pair in analysis.pairs:
            share = pair.metrics.per_million_avg if pair.metrics else None
            if share and pair.measures_topic:
                leaders[pair.topic_id] = max(leaders.get(pair.topic_id, 0.0), share)
        return [self._comparison_row(pair, labels, leaders) for pair in analysis.pairs]

    def _comparison_row(
        self, pair: PairAnalysis, labels: _TopicLabels, leaders: dict[str, float]
    ) -> ComparisonRow:
        metrics = pair.metrics
        note: str | None = None
        if pair.bundle.status is BundleStatus.NOT_FOUND:
            note = self._t.t("note.not_found")
        elif pair.bundle.status is BundleStatus.FOUND_VIA_SEARCH:
            note = self._t.t("note.search_fallback")
        elif pair.bundle.status is BundleStatus.SUBSTITUTE:
            note = self._t.t("note.substitute", what=self._substitute_text(pair.bundle))
        share = metrics.per_million_avg if metrics else None
        leader = leaders.get(pair.topic_id)
        edition = pair.findings.edition
        return ComparisonRow(
            topic_id=pair.topic_id,
            project=pair.project.domain,
            label=labels.topic(pair.topic_id),
            views_avg=metrics.views_avg if metrics else None,
            per_million_avg=share,
            growth_yoy=metrics.growth_yoy if metrics else None,
            growth_halves=metrics.growth_halves if metrics else None,
            trend_direction=metrics.trend_direction if metrics else TrendDirection.UNKNOWN,
            reliability=pair.reliability.level,
            note=note,
            index=(
                round(share / leader * 100, 1) if share and leader and pair.measures_topic else None
            ),
            views_growth=edition.article_change if edition else None,
            edition_growth=edition.edition_change if edition else None,
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
                    rationale=(
                        self._rationale(item, pair.metrics)
                        if pair.measures_topic
                        else self._t.t("rank.rationale.substitute")
                    ),
                )
            )
        return rows

    def _rationale(self, item: RankedAudience, metrics: TrendMetrics | None) -> str:
        growth = headline_growth(metrics)[0] if metrics is not None else None
        if metrics is None or growth is None:
            return self._t.t("rank.rationale.insufficient")
        return self._t.t(
            "rank.rationale",
            profile=self._t.label("profile", item.profile),
            growth=self._t.percent(growth, signed=True),
            views=self._t.number(metrics.views_avg),
            level=self._t.label("level", item.reliability),
        )

    # -- charts ---------------------------------------------------------------------------

    def _charts(
        self, request: AnalysisRequest, analysis: AnalysisResult, labels: _TopicLabels
    ) -> list[ChartSpec]:
        """The charts besides the main one: the scatter for many audiences, the seasons.

        See :class:`~wiki_interest.application.chart_plan.ChartPlanner` for what each shows.
        """
        with_data = [p for p in analysis.pairs if p.views is not None]
        if not with_data:
            return []
        settings = self._insight_settings
        normalised = request.normalization == "per_million"
        season_requested = request.report.seasonality == "show"

        def charted(pair: PairAnalysis) -> bool:
            visibility = season_visibility(pair, settings, requested=season_requested)
            return visibility is SeasonVisibility.CHART

        plots = ChartPlanner(self._t, labels.pair, labels.short, show_season=charted)
        return plots.plan(with_data, normalised=normalised)

    # -- prose ----------------------------------------------------------------------------

    def _verdict(
        self,
        request: AnalysisRequest,
        analysis: AnalysisResult,
        labels: _TopicLabels,
        *,
        findings: Sequence[FindingOut],
        assessments: Sequence[PairAssessment],
    ) -> Verdict:
        """The answer in one sentence, built from the states of the audiences.

        Direction, which audience moves fastest and whether recent months confirm it: no
        numbers, so the sentence reads on its own; every number is in :meth:`_happening`
        with its metric and window.
        """
        t = self._t
        normalised = request.normalization == "per_million"
        bullets = [f.text for f in findings]
        if not any(a.measured for a in assessments):
            headline = t.t(
                "verdict.none.headline",
                topics=", ".join(labels.topic(t_id) for t_id in labels.topic_ids),
                projects=", ".join(request.projects),
            )
            return Verdict(headline=headline, bullets=bullets)
        shown = _shown(assessments)
        if request.question_type == "rank" and analysis.ranking:
            return Verdict(headline=self._rank_headline(analysis, labels), bullets=bullets)
        subject = self._subject(shown, labels, normalised)
        known = [a for a in shown if a.momentum is not Momentum.UNKNOWN]
        if not known:
            return Verdict(headline=t.t("headline.unknown", subject=subject), bullets=bullets)
        if len(shown) == 1:
            only = known[0]
            headline = t.t(
                f"headline.one.{only.momentum.value}",
                subject=subject,
                project=labels.project(only.topic_id, only.project),
                recent=self._recent(only),
            )
            return Verdict(headline=_sentence(headline), bullets=bullets)
        directions = {a.momentum for a in known}
        if len(directions) == 1 and len(known) == len(shown):
            direction = known[0].momentum
            scope = self._scope(shown)
            if direction is Momentum.FLAT:
                headline = t.t("headline.all.flat", subject=subject, scope=scope)
            else:
                fastest = max(known, key=lambda a: abs(a.change or 0.0))
                steadier = fastest.robustness is Robustness.CONFIRMED and any(
                    a.robustness is not Robustness.CONFIRMED for a in known if a is not fastest
                )
                headline = t.t(
                    f"headline.all.{direction.value}",
                    subject=subject,
                    scope=scope,
                    fastest=t.t(
                        "headline.fastest_steadier" if steadier else "headline.fastest",
                        label=self._label(fastest, labels),
                    ),
                )
            return Verdict(headline=_sentence(headline), bullets=bullets)
        parts = []
        for direction in (Momentum.GROWING, Momentum.DECLINING, Momentum.FLAT, Momentum.UNKNOWN):
            members = [self._label(a, labels) for a in shown if a.momentum is direction]
            if members:
                parts.append(t.t(f"headline.part.{direction.value}", items=", ".join(members)))
        headline = t.t("headline.mixed", subject=subject, parts="; ".join(parts))
        return Verdict(headline=_sentence(headline), bullets=bullets)

    def _subject(
        self, shown: Sequence[PairAssessment], labels: _TopicLabels, normalised: bool
    ) -> str:
        """``The attention share of «chess»``: the metric the headline is about, and the topic."""
        topics = list(dict.fromkeys(labels.topic(a.topic_id) for a in shown))
        quoted = ", ".join(f"«{topic}»" for topic in topics)
        metric = "share" if normalised else "views"
        count = "one" if len(topics) == 1 else "many"
        return self._t.t(f"headline.subject.{metric}_{count}", topics=quoted)

    def _scope(self, shown: Sequence[PairAssessment]) -> str:
        """``in both editions``, ``in every edition`` or ``everywhere`` (several topics)."""
        topics = {a.topic_id for a in shown}
        if len(topics) > 1:
            return self._t.t("headline.scope.everywhere")
        return self._t.t("headline.scope.both" if len(shown) == 2 else "headline.scope.all")  # noqa: PLR2004

    def _happening(
        self,
        assessments: Sequence[PairAssessment],
        labels: _TopicLabels,
        *,
        normalised: bool,
    ) -> list[str]:
        """What happened, as two or three sentences, each naming its metric and its window."""
        t = self._t
        shown = _shown(assessments)
        out: list[str] = []
        share = t.t("metric.attention_share")
        views = t.t("metric.article_views")
        edition = t.t("metric.edition_views")

        def items(pairs: Sequence[tuple[PairAssessment, str]]) -> str:
            return "; ".join(f"{self._label(a, labels)} {text}" for a, text in pairs)

        if normalised:
            sized = [(a, t.number(a.per_million, 1)) for a in shown if a.per_million is not None]
            if sized:
                out.append(
                    t.t(
                        "happening.size_share",
                        metric=share,
                        unit=t.t("metric.attention_share_unit"),
                        items=items(sized),
                    )
                )
        else:
            sized = [(a, t.number(a.views_avg)) for a in shown if a.views_avg is not None]
            if sized:
                out.append(t.t("happening.size_views", metric=views, items=items(sized)))
        changed = [(a, t.percent(a.change, signed=True)) for a in shown if a.change is not None]
        if changed:
            out.append(
                t.t(
                    "happening.change",
                    metric=share if normalised else views,
                    basis=t.t(f"basis.{changed[0][0].basis}"),
                    items=items(changed),
                )
            )
        split = [
            (
                a,
                t.t(
                    "happening.pair",
                    article=t.percent(a.article_change, signed=True),
                    edition=t.percent(a.edition_change, signed=True),
                ),
            )
            for a in shown
            if a.article_change is not None and a.edition_change is not None
        ]
        if split and normalised:
            out.append(
                t.t(
                    "happening.vs_edition",
                    article=views,
                    edition=edition[:1].lower() + edition[1:],  # mid-sentence
                    basis=t.t(f"basis.{split[0][0].relation_basis}"),
                    items=items(split),
                )
            )
        missing = [labels.pair(a.topic_id, a.project) for a in assessments if not a.measured]
        if missing:
            out.append(t.t("answer.no_article", projects=", ".join(missing)))
        return [_sentence(line) for line in out]

    @staticmethod
    def _label(item: PairAssessment | None, labels: _TopicLabels) -> str:
        return labels.pair(item.topic_id, item.project) if item is not None else ""

    def _assessment_out(
        self,
        pair: PairAnalysis,
        item: PairAssessment,
        labels: _TopicLabels,
        *,
        season_requested: bool = False,
    ) -> AssessmentOut:
        t = self._t
        label = labels.pair(item.topic_id, item.project)
        title = pair.bundle.main.title if pair.bundle.main is not None else ""
        edition_line = None
        if (
            item.relation is not None
            and item.article_change is not None
            and item.edition_change is not None
        ):
            edition_line = t.t(
                f"edition.{item.relation.value}",
                label=label,
                article=t.percent(item.article_change, signed=True),
                edition=t.percent(item.edition_change, signed=True),
            )
        return AssessmentOut(
            recent_months=item.recent_months,
            recent_article=item.recent_article,
            recent_edition=item.recent_edition,
            recent_shift=item.recent_shift,
            robustness=item.robustness,
            robustness_line=self._robustness_line(item, label) if item.measured else None,
            topic_id=item.topic_id,
            project=item.project.domain,
            label=label,
            measured=item.measured,
            per_million=item.per_million,
            views_avg=item.views_avg,
            size=item.size,
            momentum=item.momentum,
            change=item.change,
            basis=item.basis,
            article_change=item.article_change,
            edition_change=item.edition_change,
            share_change=item.share_change,
            relation=item.relation,
            relation_basis=item.relation_basis,
            confidence=item.confidence,
            evidence=[
                EvidenceOut(text=self._evidence_text(e, title), concern=e.concern)
                for e in item.evidence
            ],
            outcome=item.outcome,
            decision=t.t(f"outcome.{item.outcome}", label=label, recent=self._recent(item)),
            edition_line=edition_line,
            data_quality=self._data_quality(pair) if item.measured else None,
            months=[_month_out(m) for m in pair.findings.months],
            season=self._season_out(pair, requested=season_requested),
            divergence=divergence(
                item.article_change, item.share_change, self._assessment_settings
            ),
        )

    def _data_quality(self, pair: PairAnalysis) -> DataQualityOut:
        """The worst data check, the trend test left out: that is an inference."""
        checks = [c for c in pair.reliability.checks if c.name not in _INFERENCE_CHECKS]
        statuses = {c.status for c in checks}
        if CheckStatus.FAIL in statuses:
            level = ReliabilityLevel.LOW
        elif CheckStatus.WARN in statuses:
            level = ReliabilityLevel.MEDIUM
        else:
            level = ReliabilityLevel.HIGH
        context = {"title": pair.bundle.main.title} if pair.bundle.main is not None else {}
        reasons = [
            self._t.t(c.reason_key, **{**context, **c.params})
            for c in checks
            if c.status in (CheckStatus.WARN, CheckStatus.FAIL)
        ]
        return DataQualityOut(level=level, reasons=reasons)

    def _season_out(self, pair: PairAnalysis, *, requested: bool) -> SeasonOut | None:
        season = pair.findings.season
        if season is None:
            return None
        visibility = season_visibility(pair, self._insight_settings, requested=requested)
        profile = season.profile
        return SeasonOut(
            shown=visibility is not SeasonVisibility.HIDDEN,
            reason=season.reason.value,
            years=season.years,
            consistency=season.consistency,
            strength=season.strength,
            start=f"{season.start:%Y-%m}" if season.start else None,
            end=f"{season.end:%Y-%m}" if season.end else None,
            peak_month=profile.peak_month if profile else None,
            trough_month=profile.trough_month if profile else None,
            peak=profile.peak if profile else None,
            trough=profile.trough if profile else None,
        )

    def _recent(self, item: PairAssessment) -> str:
        """The clause an outcome gets from the recent months (empty when not judged)."""
        if item.robustness is Robustness.UNKNOWN:
            return ""
        return self._t.t(f"outcome.recent.{item.robustness.value}")

    def _robustness_line(self, item: PairAssessment, label: str) -> str:
        """Whether the last months confirm the long-term direction, with the numbers."""
        t = self._t
        if item.robustness is Robustness.UNKNOWN:
            reason = t.t(f"robustness.reason.{item.robustness_reason or 'no_recent'}")
            return t.t("robustness.unknown", label=label, reason=reason)
        return t.t(
            f"robustness.{item.robustness.value}.{item.momentum.value}",
            label=label,
            change=t.percent(item.change, signed=True),
            basis=t.t(f"basis.{item.basis}"),
            months=t.number(item.recent_months),
            article=t.percent(item.recent_article, signed=True),
            edition=t.percent(item.recent_edition, signed=True),
        )

    def _data_note(
        self,
        analysis: AnalysisResult,
        assessments: Sequence[PairAssessment],
        labels: _TopicLabels,
    ) -> list[str]:
        """The data in one line when all audiences share it; concerns per audience after it."""
        t = self._t
        titles = {
            (p.topic_id, p.project): p.bundle.main.title if p.bundle.main else ""
            for p in analysis.pairs
        }
        measured = [a for a in assessments if a.measured and a.evidence]
        if not measured:
            return []

        def text(item: PairAssessment, evidence: Evidence) -> str:
            return self._evidence_text(evidence, titles[(item.topic_id, item.project)])

        shared = [text(measured[0], e) for e in measured[0].evidence if not e.concern]
        for item in measured[1:]:
            own = {text(item, e) for e in item.evidence if not e.concern}
            shared = [s for s in shared if s in own]
        lines = [t.t("report.data_line", items="; ".join(shared))] if shared else []
        for item in measured:
            concerns = [text(item, e) for e in item.evidence if e.concern]
            if concerns:
                label = labels.pair(item.topic_id, item.project)
                lines.append(t.t("report.data_concerns", label=label, items="; ".join(concerns)))
        return lines

    def _evidence_text(self, evidence: Evidence, title: str) -> str:
        """Short evidence is formatted here; a concern reuses its full reliability message."""
        if evidence.key.startswith("evidence."):
            shown = {name: self._format_param(name, v) for name, v in evidence.params.items()}
            return self._t.t(evidence.key, **shown)
        return self._t.t(evidence.key, title=title, **evidence.params)

    def _decision_out(
        self,
        conclusion: Conclusion,
        assessments: Sequence[PairAssessment],
        labels: _TopicLabels,
    ) -> DecisionOut:
        """The next step follows the conclusion: confirm growth, or test existing demand."""
        candidate = conclusion.candidate
        compared = sum(1 for a in assessments if a.measured and a.measures_topic) > 1
        if conclusion.key in _GROWTH_CONCLUSIONS:
            key = "next_step.confirm"
        elif conclusion.key in _DEMAND_CONCLUSIONS:
            key = "next_step.check_demand"
        else:
            key = "next_step.low_trust"
        named = [c for c in (candidate, conclusion.largest) if c is not None]
        label = ", ".join(self._label(c, labels) for c in named) or None
        if label and compared and key != "next_step.low_trust":
            key += "_for"
        # Audiences with the same outcome share a line: the reader compares outcomes, and
        # three identical sentences differing only in the edition read as noise.
        by_outcome: dict[tuple[str, Robustness], list[PairAssessment]] = {}
        for item in assessments:
            by_outcome.setdefault((item.outcome, item.robustness), []).append(item)
        lines = (
            [
                self._t.t(
                    f"outcome.{outcome_key}",
                    label=", ".join(self._label(i, labels) for i in items),
                    recent=self._recent(items[0]),
                )
                for (outcome_key, _), items in by_outcome.items()
            ]
            if len(assessments) > 1
            else []
        )
        summary = None
        if conclusion.key != "none":
            summary = _sentence(
                self._t.t(
                    f"answer.conclusion.{conclusion.key}",
                    label=self._label(conclusion.candidate, labels),
                    largest=self._label(conclusion.largest, labels),
                )
            )
        return DecisionOut(
            conclusion=conclusion.key,
            candidate=label,
            summary=summary,
            lines=lines,
            next_step=self._t.t(key, label=label or ""),
        )

    def _rank_headline(self, analysis: AnalysisResult, labels: _TopicLabels) -> str:
        best = analysis.ranking[0]
        measured = [
            r for r in analysis.ranking if r.profile is not AudienceProfile.INSUFFICIENT_DATA
        ]
        # Calling a shrinking audience "most promising" without context would mislead.
        all_declining = bool(measured) and all(
            r.profile is AudienceProfile.DECLINING for r in measured
        )
        key = "verdict.rank.headline_declining" if all_declining else "verdict.rank.headline"
        return self._t.t(
            key,
            label=labels.pair(best.topic_id, best.project),
            profile=self._t.label("profile", best.profile),
        )

    def _findings_out(self, insights: Sequence[Insight], labels: _TopicLabels) -> list[FindingOut]:
        out: list[FindingOut] = []
        for insight in insights:
            params = self._display(insight, labels)
            json_params = _json_params(insight.params)
            if insight.members:
                params["items"] = "; ".join(
                    self._t.t(f"finding.item.{m.kind}", **self._display(m, labels))
                    for m in insight.members
                )
                for member in insight.members:
                    prefix = member.project.domain if member.project else ""
                    json_params.update(
                        {f"{prefix}.{k}": v for k, v in _json_params(member.params).items()}
                    )
            out.append(
                FindingOut(
                    kind=insight.kind,
                    topic_id=insight.topic_id,
                    project=insight.project.domain if insight.project else None,
                    importance=round(min(1.0, insight.importance), 3),
                    text=self._t.t(f"finding.{insight.kind}", **params),
                    params=json_params,
                )
            )
        return out

    def _display(self, insight: Insight, labels: _TopicLabels) -> dict[str, str]:
        """Template values for an insight, formatted for the report language."""
        t = self._t
        shown: dict[str, str] = {}
        if insight.topic_id is not None:
            shown["topic"] = labels.topic(insight.topic_id)
            shown["label"] = (
                labels.pair(insight.topic_id, insight.project)
                if insight.project is not None
                else labels.topic(insight.topic_id)
            )
        for name, value in insight.params.items():
            shown[name] = self._format_param(name, value)
        if "unit" in insight.params:
            unit = insight.params["unit"]
            shown["unit"] = t.t(f"finding.unit.{unit}")
            metric = "attention_share" if unit == "per_million" else "article_views"
            shown["metric"] = t.t(f"metric.{metric}")
            if unit == "views":
                for name in ("before", "after"):
                    amount = insight.params.get(name)
                    if isinstance(amount, float):
                        shown[name] = t.number(amount)
        if "basis" in insight.params:
            shown["basis"] = t.t(f"basis.{insight.params['basis']}")
        if insight.params.get("substitute"):
            shown["what"] = t.t(
                f"substitute.{insight.params['substitute']}", title=insight.params["title"]
            )
        return shown

    def _format_param(self, name: str, value: ParamValue) -> str:  # noqa: PLR0911 -- a lookup
        t = self._t
        if isinstance(value, date):
            return t.month_year(value) if name.endswith("_month") else t.date(value)
        if isinstance(value, str):
            return value
        if name in _MONTH_PARAMS:
            return t.month_name(int(value))
        if name in _SIGNED_PERCENT_PARAMS:
            return t.percent(value, signed=True)
        if name == "share":
            return t.percent(value, 1 if value < _SMALL_SHARE else 0)
        if name in _MULTIPLE_PARAMS:
            return t.number(value, 1)
        if name in _COUNT_PARAMS or isinstance(value, int):
            return t.number(value)
        return t.number(value, 1 if abs(value) < _SMALL_VALUE else 0)

    def _limitations(
        self,
        request: AnalysisRequest,
        period: Period,
        resolved: Sequence[ResolvedTopic],
        labels: _TopicLabels,
    ) -> list[str]:
        """Limitations specific to this run; the method's general ones are listed apart."""
        out = [note for _, note in period_notes(request.period, period, self._t)]
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
            out.extend(
                self._t.t(
                    "limitation.substitute",
                    topic=labels.topic(topic.topic_id),
                    project=b.project.domain,
                    what=self._substitute_text(b),
                )
                for b in topic.bundles
                if b.status is BundleStatus.SUBSTITUTE
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

    def _general_limitations(self) -> list[str]:
        return [
            self._t.t("limitation.scope"),
            self._t.t("limitation.coverage"),
            self._t.t("limitation.language"),
            self._t.t("limitation.bots"),
        ]

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

    def _substitute_text(self, bundle: TopicBundle) -> str:
        """What stands in for the missing article, in words (``broader article "Post"``)."""
        main = bundle.main
        assert bundle.substitute_kind is not None
        assert main is not None
        return self._t.t(f"substitute.{bundle.substitute_kind.value}", title=main.title)

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
            thresholds=dict(provenance.thresholds or {}),
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
        # A substitute is named wherever its edition is, so no chart, table or sentence can
        # present the broader article "fasting" as "intermittent fasting".
        self._substitutes = {
            (t.topic_id, b.project): b.main.title
            for t in resolved
            for b in t.bundles
            if b.status is BundleStatus.SUBSTITUTE and b.main is not None
        }

    def topic(self, topic_id: str) -> str:
        return self._labels.get(topic_id, topic_id)

    def project(self, topic_id: str, project: WikiProject) -> str:
        substitute = self._substitutes.get((topic_id, project))
        return project.domain if substitute is None else f"{project.domain} ({substitute})"

    def pair(self, topic_id: str, project: WikiProject) -> str:
        if len(self._labels) == 1:
            return self.project(topic_id, project)
        return f"{self.topic(topic_id)} · {self.project(topic_id, project)}"

    def short(self, topic_id: str, project: WikiProject) -> str:
        """Compact label for chart categories: ``uk``, ``pl (Post)``, ``Yoga · uk``."""
        substitute = self._substitutes.get((topic_id, project))
        code = project.language if substitute is None else f"{project.language} ({substitute})"
        if len(self._labels) == 1:
            return code
        return f"{self.topic(topic_id)} · {code}"


_LARGE_EDITIONS = ("en", "de", "fr", "es", "ja", "ru", "it", "zh", "pt", "pl", "uk", "nl")
"""Editions most readers know, shown first after the requested ones."""
_LANGUAGE_SAMPLE = 8


def period_notes(requested: Period | None, period: Period, t: Translator) -> list[tuple[str, str]]:
    """How the analysed period differs from the one asked for, as ``(key, text)`` pairs.

    The pipeline measures only months with complete data (:meth:`Period.within_data`); a
    user who asked for "since 2010" must read why the report starts in 2015.
    """
    if requested is None:
        return []
    notes: list[tuple[str, str]] = []
    if requested.start < period.start:
        key = "limitation.period_start"
        notes.append(
            (key, t.t(key, start=f"{period.start:%Y-%m}", requested=f"{requested.start:%Y-%m}"))
        )
    if requested.end > period.end:
        key = "limitation.period_end"
        notes.append((key, t.t(key, end=f"{period.end:%Y-%m}", requested=f"{requested.end:%Y-%m}")))
    return notes


def _language_sample(languages: Sequence[str], requested: Sequence[str]) -> list[str]:
    """A short, recognisable subset: requested editions that have the article, then big ones."""
    present = set(languages)
    wanted = [WikiProject.parse(p).language for p in requested]
    ordered = [*wanted, *_LARGE_EDITIONS, *languages]
    return [code for code in dict.fromkeys(ordered) if code in present][:_LANGUAGE_SAMPLE]


def _shown(assessments: Sequence[PairAssessment]) -> list[PairAssessment]:
    """Audiences an answer speaks about: those measuring the topic itself, else any measured."""
    on_topic = [a for a in assessments if a.measured and a.measures_topic]
    return on_topic or [a for a in assessments if a.measured]


def _month_out(month: MonthFinding) -> MonthOut:
    return MonthOut(
        month=f"{month.month:%Y-%m}",
        multiples=dict(month.multiples),
        nature=month.nature,
        in_change=month.in_change,
        in_recent=month.in_recent,
        change_without=month.change_without,
    )


def _sentence(text: str) -> str:
    """``text`` as a sentence (capitalised, ending with a full stop), so templates join cleanly."""
    text = text.strip()
    # A lower-case topic label may open the sentence ("астрономія: ..."); an edition's domain
    # ("uk.wikipedia ...") keeps its conventional lower case.
    first_word = text.split(" ", 1)[0]
    if "." not in first_word.rstrip(".:,;"):
        text = text[:1].upper() + text[1:]
    return text if text.endswith(_SENTENCE_END) else f"{text}."


def _json_params(params: Mapping[str, ParamValue]) -> dict[str, float | int | str]:
    """Insight parameters for ``summary.json``: dates as ISO strings, floats rounded."""
    out: dict[str, float | int | str] = {}
    for name, value in params.items():
        if isinstance(value, date):
            out[name] = value.isoformat()
        elif isinstance(value, float):
            out[name] = round(value, 6)
        else:
            out[name] = value
    return out


def _series_out(pair: PairAnalysis) -> SeriesOut:
    views = pair.views
    assert views is not None
    shares = pair.per_million.values if pair.per_million is not None else (None,) * len(views)
    totals = pair.edition_total.values
    return SeriesOut(
        topic_id=pair.topic_id,
        project=pair.project.domain,
        granularity=views.granularity,
        points=[
            PointOut(
                period=p.period.strftime("%Y-%m"), views=p.value, per_million=pm, edition_views=e
            )
            for p, pm, e in zip(views.points, shares, totals, strict=True)
        ],
    )


def _metrics_out(pair: PairAnalysis, metrics: TrendMetrics) -> MetricsOut:
    return MetricsOut(
        topic_id=pair.topic_id,
        project=pair.project.domain,
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


def _question_artifacts(context: RunContext) -> Artifacts:
    """Files of a run that stopped to ask: only the summaries, no report or charts exist."""
    run_dir = context.run_dir
    return Artifacts(
        run_dir=str(run_dir),
        summary_json=str(run_dir / "summary.json"),
        summary_md=str(run_dir / "summary.md"),
    )


def _artifacts(context: RunContext, chart_ids: Sequence[str]) -> Artifacts:
    run_dir = context.run_dir
    return Artifacts(
        run_dir=str(run_dir),
        summary_json=str(run_dir / "summary.json"),
        summary_md=str(run_dir / "summary.md"),
        report_pdf=str(run_dir / "report.pdf"),
        charts=[str(run_dir / _CHARTS_DIR / f"{chart_id}.png") for chart_id in chart_ids],
    )
