"""The full run: resolve, load, analyse, summarise, render, write.

One call produces a self-contained run directory the agent can point the user to. The
pipeline owns the order of operations and the file layout; every step is a collaborator it
receives from the composition root, so the whole thing runs against in-memory fakes in tests.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from wiki_interest.application.analysis import AnalysisSettings, analyse
from wiki_interest.application.loading import SeriesLoader
from wiki_interest.application.resolution import ResolvedTopic, TopicResolver
from wiki_interest.application.summary_builder import (
    ProvenanceInput,
    RunContext,
    SummaryBuilder,
)
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.contracts.summary import AnalysisSummary, Artifacts
from wiki_interest.errors import ClarificationNeededError
from wiki_interest.i18n import Translator
from wiki_interest.ports import ChartRenderer, Clock, ReportRenderer

__all__ = ["Pipeline", "PipelineOutcome", "Renderers", "RunServices", "ServiceFactory"]

CHARTS_DIRNAME = "charts"
SUMMARY_JSON = "summary.json"
SUMMARY_MD = "summary.md"
REPORT_MD = "report.md"
REPORT_PDF = "report.pdf"
EXIT_OK = 0
EXIT_CLARIFICATION = 3


@dataclass(frozen=True, slots=True)
class Renderers:
    """Renderers for one report language."""

    charts: ChartRenderer
    agent_summary: ReportRenderer
    report_markdown: ReportRenderer
    report_pdf: ReportRenderer


@dataclass(frozen=True, slots=True)
class RunServices:
    """Collaborators the pipeline needs for one request."""

    resolver: TopicResolver
    loader: SeriesLoader
    analysis_settings: AnalysisSettings
    translator: Translator
    renderers: Renderers
    provenance: ProvenanceInput


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
            "report_md": artifacts.report_md,
            "report_pdf": artifacts.report_pdf,
            "charts": list(artifacts.charts),
            "headline": self.summary.verdict.headline,
        }
        if self.summary.clarification is not None:
            clarification = self.summary.clarification
            payload["clarification"] = {
                "topic_id": clarification.topic_id,
                "query": clarification.query,
                "question": clarification.question,
                "candidates": [c.model_dump() for c in clarification.candidates],
            }
            payload["hint"] = clarification.question
        return payload


class Pipeline:
    """Runs analyses end to end and re-renders saved ones."""

    def __init__(self, factory: ServiceFactory, clock: Clock) -> None:
        self._factory = factory
        self._clock = clock

    def run(self, request: AnalysisRequest, context: RunContext) -> PipelineOutcome:
        """Execute a request and write the run directory.

        Returns:
            The outcome with exit code 0, or 3 when the user has to disambiguate a topic (the
            run directory then holds a ``summary.md`` that states the question).

        Raises:
            UpstreamError, DataUnavailableError, RenderError: propagated for the CLI to map.
        """
        services = self._factory.services_for(request)
        period = request.period or Period.last_full_months(self._clock.today())
        builder = SummaryBuilder(services.translator, context, services.provenance)
        try:
            resolved = services.resolver.resolve_request(request)
        except ClarificationNeededError as error:
            summary = builder.build_clarification(request=request, period=period, error=error)
            self._write_clarification(summary, context.run_dir, services.renderers)
            return PipelineOutcome(summary, EXIT_CLARIFICATION)
        loaded = services.loader.load(resolved, period)
        analysis = analyse(
            resolved,
            loaded,
            weights=request.ranking_weights.to_domain(),
            settings=services.analysis_settings,
        )
        summary = builder.build(
            request=request, period=period, resolved=resolved, analysis=analysis
        )
        rendered = self._render(summary, context.run_dir, services.renderers)
        return PipelineOutcome(rendered, EXIT_OK)

    def resolve(self, request: AnalysisRequest) -> Sequence[ResolvedTopic]:
        """Only resolve topics (for inspection and clarification loops)."""
        return self._factory.services_for(request).resolver.resolve_request(request)

    def render(self, summary: AnalysisSummary, run_dir: Path) -> AnalysisSummary:
        """Re-render charts and reports of a saved summary into ``run_dir``."""
        _, renderers = self._factory.renderers_for(summary.request.report.language)
        if summary.status == "needs_clarification":
            self._write_clarification(summary, run_dir, renderers)
            return summary
        return self._render(summary, run_dir, renderers)

    # -- writing --------------------------------------------------------------------------

    def _render(
        self, summary: AnalysisSummary, run_dir: Path, renderers: Renderers
    ) -> AnalysisSummary:
        run_dir.mkdir(parents=True, exist_ok=True)
        charts_dir = run_dir / CHARTS_DIRNAME
        png_files: list[Path] = []
        for spec in summary.charts:
            written = renderers.charts.render(spec, charts_dir)
            png_files.extend(p for p in written if p.suffix == ".png")
        formats = summary.request.report.formats
        artifacts = Artifacts(
            run_dir=str(run_dir),
            summary_json=str(run_dir / SUMMARY_JSON),
            summary_md=str(run_dir / SUMMARY_MD),
            report_md=str(run_dir / REPORT_MD) if "md" in formats else None,
            report_pdf=str(run_dir / REPORT_PDF) if "pdf" in formats else None,
            charts=[str(p) for p in png_files],
        )
        final = summary.model_copy(update={"artifacts": artifacts})
        renderers.agent_summary.render(final, png_files, run_dir / SUMMARY_MD)
        if artifacts.report_md is not None:
            renderers.report_markdown.render(final, png_files, Path(artifacts.report_md))
        if artifacts.report_pdf is not None:
            renderers.report_pdf.render(final, png_files, Path(artifacts.report_pdf))
        _write_summary_json(final, run_dir)
        return final

    @staticmethod
    def _write_clarification(summary: AnalysisSummary, run_dir: Path, renderers: Renderers) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        renderers.agent_summary.render(summary, [], run_dir / SUMMARY_MD)
        _write_summary_json(summary, run_dir)


def _write_summary_json(summary: AnalysisSummary, run_dir: Path) -> None:
    payload = summary.model_dump_json(indent=2)
    (run_dir / SUMMARY_JSON).write_text(payload + "\n", encoding="utf-8")
