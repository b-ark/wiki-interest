"""The full run: resolve, check coverage, load, analyse, summarise, render, write.

One call produces a self-contained run directory the agent can point the user to. The
pipeline owns the order of operations and the file layout; every step is a collaborator it
receives from the composition root, so the whole thing runs against in-memory fakes in tests.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Protocol

from wiki_interest.application.analysis import AnalysisSettings, analyse
from wiki_interest.application.chart_plan import (
    AUDIENCE_CHART_ID,
    SHARE_CHART_ID,
    audience_years_spec,
    share_years_spec,
)
from wiki_interest.application.coverage import CoverageAdvisor
from wiki_interest.application.facts import (
    apply_narrative,
    build_facts,
    compose_chat,
    template_limits,
    template_narrative,
)
from wiki_interest.application.loading import SeriesLoader
from wiki_interest.application.narrative_check import check_narrative
from wiki_interest.application.observations import (
    observation_start,
    pair_histories,
    run_observations,
)
from wiki_interest.application.question import compose_question, label_problems
from wiki_interest.application.resolution import TopicResolver
from wiki_interest.application.runs import ATTEMPTS_FILENAME, CHAT_BRIEF_FILENAME, previous_run
from wiki_interest.application.summary_builder import (
    ProvenanceInput,
    RunContext,
    SummaryBuilder,
)
from wiki_interest.application.window import context_range, headline, read_trends, verdict_line
from wiki_interest.contracts.charts import ChartSpec
from wiki_interest.contracts.narrative import Facts, Narrative, NarrativeProblem
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.contracts.summary import AnalysisSummary, Artifacts, TrendOut
from wiki_interest.domain.assessment import AssessmentSettings
from wiki_interest.domain.trust import TrustSettings
from wiki_interest.errors import (
    ClarificationNeededError,
    RequestValidationError,
    TopicNotFoundError,
)
from wiki_interest.i18n import Translator
from wiki_interest.ports import ChartRenderer, Clock, ReportRenderer

__all__ = [
    "NarrationOutcome",
    "Pipeline",
    "PipelineOutcome",
    "Renderers",
    "RunServices",
    "ServiceFactory",
    "load_run_summary",
]

CHARTS_DIRNAME = "charts"
SUMMARY_JSON = "summary.json"
_SEASON_CHART = "season"
_SEASON_OBSERVATIONS = ("season:", "decision:timing:", "decision:audience:")
"""What the text cites when it speaks of a season: the season chart is drawn then."""
SUMMARY_MD = "summary.md"
REPORT_PDF = "report.pdf"
METHOD_MD = "method.md"
FACTS_JSON = "facts.json"
CHAT_BRIEF_MD = CHAT_BRIEF_FILENAME
ATTEMPTS_FILE = ATTEMPTS_FILENAME
MAX_NARRATIVE_ATTEMPTS = 2
"""The agent's text is rejected once with the reasons; a second failure keeps the template."""
EXIT_OK = 0
EXIT_INVALID = 2
EXIT_CLARIFICATION = 3


@dataclass(frozen=True, slots=True)
class Renderers:
    """Renderers for one report language."""

    charts: ChartRenderer
    agent_summary: ReportRenderer
    report_pdf: ReportRenderer
    method: ReportRenderer | None = None
    """Writes ``method.md``: how the run's numbers were computed."""


@dataclass(frozen=True, slots=True)
class RunServices:
    """Collaborators the pipeline needs for one request."""

    resolver: TopicResolver
    coverage: CoverageAdvisor
    loader: SeriesLoader
    analysis_settings: AnalysisSettings
    translator: Translator
    renderers: Renderers
    provenance: ProvenanceInput
    assessment: AssessmentSettings | None = None
    """Cut-offs of the conclusions; the domain defaults when ``None``."""
    trust: TrustSettings | None = None
    """Thresholds of the window's verdict and of the trust in it; defaults when ``None``."""
    stop_after_resolve: bool = False
    """End the run after the topic stage (see ``Settings.stop_after``)."""


class ServiceFactory(Protocol):
    """Builds request-specific services; implemented by the composition root."""

    def services_for(self, request: AnalysisRequest) -> RunServices:
        """Return the collaborators configured for ``request``."""
        ...

    def renderers_for(self, language: str) -> tuple[Translator, Renderers]:
        """Return a translator and renderers for a report language (used by re-rendering)."""
        ...


@dataclass(frozen=True, slots=True)
class PipelineOutcome:
    """What a run produced, ready to be printed for the agent."""

    summary: AnalysisSummary
    exit_code: int

    def to_dict(self) -> dict[str, object]:
        """Compact JSON for stdout: status, paths and the headline."""
        artifacts = self.summary.artifacts
        payload: dict[str, object] = {
            "status": self.summary.status,
            "exit_code": self.exit_code,
            "run_id": self.summary.run_id,
            "run_dir": artifacts.run_dir,
            "summary_md": artifacts.summary_md,
            "summary_json": artifacts.summary_json,
            "report_pdf": artifacts.report_pdf,
            "charts": list(artifacts.charts),
            "headline": self.summary.verdict.headline,
        }
        if self.summary.status == "ok":
            payload["facts_json"] = str(Path(artifacts.run_dir) / FACTS_JSON)
        if self.summary.resolution:
            # What each topic resolved to, so the agent can check it against what the user
            # meant before relaying anything, and switch by qid if it is the wrong entity.
            payload["topics"] = [
                {
                    "id": topic.topic_id,
                    "qid": topic.qid,
                    "label": topic.label,
                    "description": topic.description,
                    "other_meanings": [c.model_dump() for c in topic.alternatives],
                }
                for topic in self.summary.resolution
            ]
        if self.summary.clarification is not None:
            clarification = self.summary.clarification
            details: dict[str, object] = {
                "kind": clarification.kind,
                "topic_id": clarification.topic_id,
                "query": clarification.query,
                "question": clarification.question,
            }
            if clarification.candidates:
                details["candidates"] = [c.model_dump() for c in clarification.candidates]
            if clarification.from_search:
                details["from_search"] = True
            if clarification.gaps:
                details["gaps"] = [
                    {
                        "project": gap.project,
                        "question": gap.question,
                        "options": [
                            {
                                "number": o.number,
                                "description": o.description,
                                "choose": {
                                    k: v if isinstance(v, str) else v.model_dump()
                                    for k, v in o.choose.items()
                                },
                            }
                            for o in gap.options
                        ],
                    }
                    for gap in clarification.gaps
                ]
            if clarification.ask_user is not None:
                details["ask_user"] = clarification.ask_user
            if clarification.ui:
                details["ui"] = clarification.ui
            payload["clarification"] = details
            payload["hint"] = clarification.question
        if self.summary.status == "topic_resolved":
            payload["hint"] = self.summary.verdict.headline
        return payload


@dataclass(frozen=True, slots=True)
class NarrationOutcome:
    """What became of the agent's text.

    Attributes:
        summary: The summary as rendered, with the agent's text when it was accepted.
        status: ``accepted``; ``rejected`` (fix the problems and render again); or
            ``fallback`` (rejected a second time: the report keeps the template text).
        problems: Why the text was rejected.
    """

    summary: AnalysisSummary
    status: Literal["accepted", "rejected", "fallback"]
    problems: tuple[NarrativeProblem, ...] = ()

    @property
    def exit_code(self) -> int:
        """2 while the agent has to fix its text, else 0."""
        return EXIT_INVALID if self.status == "rejected" else EXIT_OK

    def to_dict(self) -> dict[str, object]:
        """JSON for stdout: status, paths, and the answer or the problems."""
        artifacts = self.summary.artifacts
        payload: dict[str, object] = {
            "status": self.status,
            "exit_code": self.exit_code,
            "run_dir": artifacts.run_dir,
            "report_pdf": artifacts.report_pdf,
            "summary_md": artifacts.summary_md,
        }
        if self.problems:
            payload["problems"] = [p.model_dump(exclude_none=True) for p in self.problems]
        if self.status == "accepted":
            payload["chat_brief"] = str(Path(artifacts.run_dir) / CHAT_BRIEF_MD)
            payload["chat_answer"] = self.summary.chat_answer
        elif self.status == "rejected":
            payload["hint"] = (
                "Fix every problem in narrative.json and render again; a second rejection "
                "keeps the template text."
            )
        else:
            payload["hint"] = "The report keeps the template text: relay summary_md."
        return payload


@dataclass(frozen=True, slots=True)
class QuestionOutcome:
    """The question to the user after the agent translated its labels.

    Attributes:
        summary: The run's summary; ``clarification.ask_user`` holds the question once
            ``status`` is ``accepted``.
        status: ``accepted``, or ``rejected`` (fix the labels named in ``problems``).
        problems: Labels missing or with lost placeholders.
    """

    summary: AnalysisSummary
    status: Literal["accepted", "rejected"]
    problems: tuple[str, ...] = ()

    @property
    def exit_code(self) -> int:
        """2 while the agent has to fix its labels, else 0."""
        return EXIT_INVALID if self.status == "rejected" else EXIT_OK

    def to_dict(self) -> dict[str, object]:
        """JSON for stdout: the question to send, or the problems."""
        clarification = self.summary.clarification
        payload: dict[str, object] = {"status": self.status, "exit_code": self.exit_code}
        if self.problems:
            payload["problems"] = list(self.problems)
            payload["hint"] = "Fix every label named in problems and run render.py --ui again."
        elif clarification is not None and clarification.ask_user is not None:
            payload["ask_user"] = clarification.ask_user
            payload["hint"] = (
                "Send ask_user to the user word for word as your whole message, and stop."
            )
        return payload


class Pipeline:
    """Runs analyses end to end and re-renders saved ones."""

    def __init__(self, factory: ServiceFactory, clock: Clock) -> None:
        self._factory = factory
        self._clock = clock

    def run(self, request: AnalysisRequest, context: RunContext) -> PipelineOutcome:
        """Execute a request and write the run directory.

        Returns:
            The outcome with exit code 0, or 3 when the user has to decide something first: which
            entity an ambiguous topic means, or what to measure in an edition without an article
            (the run directory then holds a ``summary.md`` that states the question). The
            coverage question is asked before any pageview series is fetched.

        Raises:
            UpstreamError, DataUnavailableError, RenderError: propagated for the CLI to map.
        """
        services = self._factory.services_for(request)
        period = _period(request, self._clock.today())
        builder = SummaryBuilder(
            services.translator,
            context,
            services.provenance,
            assessment_settings=services.assessment,
        )
        try:
            resolved = services.resolver.resolve_request(request)
        except ClarificationNeededError as error:
            summary = builder.build_clarification(request=request, period=period, error=error)
            self._write_clarification(summary, context.run_dir, services.renderers)
            return PipelineOutcome(summary, EXIT_CLARIFICATION)
        except TopicNotFoundError as error:
            summary = builder.build_not_found(request=request, period=period, error=error)
            self._write_clarification(summary, context.run_dir, services.renderers)
            return PipelineOutcome(summary, EXIT_CLARIFICATION)
        gaps = services.coverage.gaps(request, resolved, self._clock.today())
        if gaps:
            summary = builder.build_coverage_question(request=request, period=period, gaps=gaps)
            summary = _with_question(summary, context.run_dir, services.translator)
            self._write_clarification(summary, context.run_dir, services.renderers)
            return PipelineOutcome(summary, EXIT_CLARIFICATION)
        if services.stop_after_resolve:
            summary = builder.build_topic_only(request=request, period=period, resolved=resolved)
            self._write_clarification(summary, context.run_dir, services.renderers)
            return PipelineOutcome(summary, EXIT_OK)
        observe_from = observation_start(request, period)
        loaded = services.loader.load(resolved, period, observe_from=observe_from)
        analysis = analyse(
            resolved,
            loaded,
            weights=request.ranking_weights.to_domain(),
            settings=services.analysis_settings,
        )
        histories = pair_histories(loaded, resolved)
        trends = read_trends(histories, period.start, settings=services.trust)
        summary = builder.build(
            request=request,
            period=period,
            resolved=resolved,
            analysis=analysis,
            observations=run_observations(histories, request, period, trends),
            histories=histories,
            trends=trends,
            history_range=context_range(period, observe_from),
        )
        # The report shows the code's own text until the agent's is accepted: the same
        # blocks, so the PDF has one layout whoever wrote it.
        template = template_narrative(summary, services.translator)
        summary = apply_narrative(summary, template, source="template")
        rendered = self._render(summary, context.run_dir, services.renderers, services.translator)
        return PipelineOutcome(rendered, EXIT_OK)

    def render(self, summary: AnalysisSummary, run_dir: Path) -> AnalysisSummary:
        """Re-render charts and reports of a saved summary into ``run_dir``."""
        translator, renderers = self._factory.renderers_for(summary.request.report.language)
        if summary.status != "ok":
            self._write_clarification(summary, run_dir, renderers)
            return summary
        return self._render(summary, run_dir, renderers, translator)

    def ask(self, run_dir: Path, ui: Mapping[str, str]) -> QuestionOutcome:
        """Compose the missing-article question with the agent's translation of its labels.

        The translations are kept for the session, as the report text's are.

        Raises:
            FileNotFoundError: If the run has no ``summary.json``.
            RequestValidationError: If the run did not stop on a missing article.
        """
        summary = load_run_summary(run_dir)
        clarification = summary.clarification
        if clarification is None or clarification.kind != "missing_article":
            msg = f"{run_dir} did not stop on a missing article: there is no question to compose"
            raise RequestValidationError(msg, hint="Use --ui only after run.py asked for it.")
        problems = label_problems(clarification.ui, ui)
        if problems:
            return QuestionOutcome(summary, "rejected", tuple(problems))
        language = summary.request.report.language
        cache = _ui_cache_path(run_dir, language)
        _write_json(cache, {**_read_ui(cache), **{k: v for k, v in ui.items() if v.strip()}})
        translator, renderers = self._factory.renderers_for(language)
        final = _with_question(summary, run_dir, translator)
        self._write_clarification(final, run_dir, renderers)
        return QuestionOutcome(final, "accepted")

    def narrate(self, run_dir: Path, narrative: Narrative) -> NarrationOutcome:
        """Check the agent's text against the run's facts and, if it holds, render with it.

        A rejected text leaves the report as it was and returns the problems; the second
        rejection of the same run is final and the template text stays (see
        :data:`MAX_NARRATIVE_ATTEMPTS`).

        Raises:
            FileNotFoundError: If the run has no ``summary.json`` or ``facts.json``.
        """
        summary = load_run_summary(run_dir)
        facts = Facts.model_validate_json((run_dir / FACTS_JSON).read_text(encoding="utf-8"))
        cache = _ui_cache_path(run_dir, summary.request.report.language)
        cached = _read_ui(cache)
        problems = check_narrative(facts, narrative)
        if problems:
            attempts = _bump_attempts(run_dir)
            status: Literal["rejected", "fallback"] = (
                "fallback" if attempts >= MAX_NARRATIVE_ATTEMPTS else "rejected"
            )
            return NarrationOutcome(summary, status, tuple(problems))
        if narrative.ui:
            _write_json(cache, {**cached, **narrative.ui})
        translator, renderers = self._factory.renderers_for(summary.request.report.language)
        final = self._render(
            apply_narrative(summary, narrative),
            run_dir,
            renderers,
            translator,
            limits=narrative.limits,
        )
        (run_dir / CHAT_BRIEF_MD).write_text(f"{final.chat_answer}\n", encoding="utf-8")
        return NarrationOutcome(final, "accepted")

    # -- writing --------------------------------------------------------------------------

    def _render(
        self,
        summary: AnalysisSummary,
        run_dir: Path,
        renderers: Renderers,
        translator: Translator,
        *,
        limits: str | None = None,
    ) -> AnalysisSummary:
        """Write charts, reports, the chat answer and ``summary.json``.

        The keys the user-facing renderers and the chat answer look up are recorded: for a
        report language without a catalog they are the interface labels the agent translates.

        Args:
            summary: What to render.
            run_dir: Where to write it.
            renderers: The renderers of the report language.
            translator: The report-language translator.
            limits: The agent's limits line when its text was accepted; ``None`` for the
                analysis itself, which also writes the agent's inputs (``facts.json``) and
                composes the chat answer with the template's limits.
        """
        run_dir.mkdir(parents=True, exist_ok=True)
        if not translator.has_catalog:
            translator.override(_read_ui(_ui_cache_path(run_dir, translator.requested)))
        charts_dir = run_dir / CHARTS_DIRNAME
        artifacts = Artifacts(
            run_dir=str(run_dir),
            summary_json=str(run_dir / SUMMARY_JSON),
            summary_md=str(run_dir / SUMMARY_MD),
            report_pdf=str(run_dir / REPORT_PDF),
            method_md=str(run_dir / METHOD_MD) if renderers.method is not None else None,
        )
        png_files: list[Path] = []
        with translator.recording() as used:
            summary = _with_verdict_text(_with_main_charts(summary, translator), translator)
            for spec in summary.charts:
                written = renderers.charts.render(spec, charts_dir)
                png_files.extend(p for p in written if p.suffix == ".png")
            artifacts = artifacts.model_copy(update={"charts": [str(p) for p in png_files]})
            final = summary.model_copy(update={"artifacts": artifacts})
            renderers.report_pdf.render(final, png_files, run_dir / REPORT_PDF)
            line = template_limits(translator) if limits is None else limits
            chat = compose_chat(final, line, translator, previous_run(run_dir))
            final = final.model_copy(update={"chat_answer": chat})
        renderers.agent_summary.render(final, png_files, run_dir / SUMMARY_MD)
        if renderers.method is not None:
            renderers.method.render(final, png_files, run_dir / METHOD_MD)
        _write_summary_json(final, run_dir)
        if limits is None:
            _write_facts(final, run_dir, translator, used)
        return final

    @staticmethod
    def _write_clarification(summary: AnalysisSummary, run_dir: Path, renderers: Renderers) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        renderers.agent_summary.render(summary, [], run_dir / SUMMARY_MD)
        _write_summary_json(summary, run_dir)


def _with_main_charts(summary: AnalysisSummary, translator: Translator) -> AnalysisSummary:
    """The summary with the main chart and the views by year first, built now.

    They are built in the report's language, with the labels the agent translated, and the
    main chart marks only the steps and bursts the report text cites; specs of an earlier
    rendering are replaced.
    """
    # A season takes its chart when the user asked about timing or the text speaks of it:
    # a pattern found but not part of the answer is not worth a third of the page.
    seasons = summary.request.report.seasonality == "show" or any(
        oid.startswith(_SEASON_OBSERVATIONS) for oid in summary.cited
    )
    others = [
        c
        for c in summary.charts
        if c.id not in (SHARE_CHART_ID, AUDIENCE_CHART_ID)
        and (seasons or not c.id.startswith(_SEASON_CHART))
    ]
    first: list[ChartSpec] = []
    if summary.share_chart is not None:
        first.append(share_years_spec(summary.share_chart, translator, set(summary.cited)))
    if summary.audience_chart is not None:
        first.append(audience_years_spec(summary.audience_chart, translator))
    return summary.model_copy(update={"charts": [*first, *others]})


def _with_verdict_text(summary: AnalysisSummary, translator: Translator) -> AnalysisSummary:
    """The headline and the verdict lines, composed now in the report's language.

    Composed at render time, as the charts' labels are, so a language without written labels
    gets the agent's translations of them (``facts.ui`` asks for them).
    """
    if not summary.verdicts:
        return summary
    verdicts = [
        v.model_copy(update={"line": verdict_line(v, translator)}) for v in summary.verdicts
    ]
    labels = {r.topic_id: r.label or r.query for r in summary.resolution}
    by_topic: dict[str, list[TrendOut]] = {}
    for item in verdicts:
        by_topic.setdefault(item.topic_id, []).append(item)
    lines = [
        text
        for topic_id, items in by_topic.items()
        if (text := headline(labels.get(topic_id, topic_id), items, translator))
    ]
    verdict = summary.verdict
    if lines:
        verdict = verdict.model_copy(update={"headline": " ".join(lines)})
    return summary.model_copy(update={"verdicts": verdicts, "verdict": verdict})


def load_run_summary(run_dir: Path) -> AnalysisSummary:
    """The saved summary of a run directory."""
    return AnalysisSummary.model_validate_json((run_dir / SUMMARY_JSON).read_text(encoding="utf-8"))


def _write_facts(
    summary: AnalysisSummary, run_dir: Path, translator: Translator, used: set[str]
) -> None:
    """``facts.json`` for the agent that writes the report text.

    One file, read once: the labels to translate sit in the facts, so the agent does not spend
    a turn on a second file.
    """
    # The session's translations were applied before rendering: what still reads in English
    # is what the agent translates.
    ui = {key: translator.english(key) for key in sorted(used) if not translator.translates(key)}
    facts = build_facts(summary, ui=ui)
    _write_json(run_dir / FACTS_JSON, facts.model_dump(mode="json"))
    (run_dir / ATTEMPTS_FILE).unlink(missing_ok=True)


def _ui_cache_path(run_dir: Path, language: str) -> Path:
    """Interface translations live per session: the session directory holds its runs."""
    return run_dir.parent / f"ui-{language}.json"


def _read_ui(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def _with_question(
    summary: AnalysisSummary, run_dir: Path, translator: Translator
) -> AnalysisSummary:
    """``summary`` with the missing-article question composed, or the labels it still needs.

    The question goes to the user word for word, so it is given only when every label reads
    in the user's language: the catalog's, or the session's translations.
    """
    clarification = summary.clarification
    assert clarification is not None
    if not translator.has_catalog:
        translator.override(_read_ui(_ui_cache_path(run_dir, translator.requested)))
    with translator.recording() as used:
        text = compose_question(clarification, translator)
    pending = {k: translator.english(k) for k in sorted(used) if not translator.translates(k)}
    language = summary.request.report.language
    if pending:
        update = {
            "ask_user": None,
            "ui": pending,
            "question": translator.t("summary.missing_translate_hint", language=language),
        }
    else:
        update = {
            "ask_user": text,
            "ui": {},
            "question": translator.t("summary.missing_hint", language=language),
        }
    return summary.model_copy(update={"clarification": clarification.model_copy(update=update)})


def _period(request: AnalysisRequest, today: date) -> Period:
    """The period to analyse: the requested one within the data, or the default.

    The summary keeps the request as asked, so the reports can say how the period changed.

    Raises:
        RequestValidationError: If no month of the requested period has complete data.
    """
    if request.period is None:
        return Period.last_full_months(today)
    try:
        return request.period.within_data(today)
    except ValueError as exc:
        raise RequestValidationError(
            str(exc), hint="Ask the user for a period from 2015-07 to last month."
        ) from exc


def _bump_attempts(run_dir: Path) -> int:
    path = run_dir / ATTEMPTS_FILE
    attempts = (int(path.read_text(encoding="utf-8")) if path.is_file() else 0) + 1
    path.write_text(str(attempts), encoding="utf-8")
    return attempts


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_summary_json(summary: AnalysisSummary, run_dir: Path) -> None:
    payload = summary.model_dump_json(indent=2)
    (run_dir / SUMMARY_JSON).write_text(payload + "\n", encoding="utf-8")
