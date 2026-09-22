"""``summary.md``: the short, structured text the agent relays almost verbatim.

This is the anti-hallucination layer of the skill (plan §6.3): the answer, the key numbers,
the trust level with its reasons, the caveats and the follow-up hints are all written by code
so a cheap model has nothing to compute or remember. The document is kept scannable (one
screen for a two-edition comparison) and, when the pipeline stopped for clarification, it
shows only the question and the candidates so the agent asks instead of guessing.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from wiki_interest.adapters.markdown_report import (
    comparison_table,
    period_text,
    question_line,
    ranking_table,
    report_title,
    row_label,
    sorted_checks,
)
from wiki_interest.contracts.summary import AnalysisSummary, BundleOut, ReliabilityOut
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

__all__ = ["AgentSummaryRenderer"]

MAX_REASONS = 3
"""Reasons per (topic, project): enough to justify the level without becoming a checklist."""
WEIGHT_DECIMALS = 2


class AgentSummaryRenderer:
    """Writes the condensed agent-facing summary in the report language."""

    def __init__(self, translator: Translator) -> None:
        self._t = translator

    def render(self, summary: AnalysisSummary, charts: Sequence[Path], output_path: Path) -> Path:
        """Write ``summary.md``. ``charts`` is unused: artifact paths come from the summary.

        Raises:
            RenderError: If the file cannot be written.
        """
        del charts
        text = self.build(summary)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8", newline="\n")
        except OSError as exc:
            msg = f"Cannot write agent summary to {output_path}: {exc}"
            raise RenderError(msg, hint="Check that the run directory is writable") from exc
        return output_path

    def build(self, summary: AnalysisSummary) -> str:
        """Return the document text without touching the file system."""
        if summary.status == "needs_clarification":
            blocks = [self._clarification(summary)]
        else:
            blocks = [
                self._answer(summary),
                self._key_numbers(summary),
                self._trust(summary),
                self._list_section("summary.caveats", summary.limitations),
                self._list_section("summary.refine", summary.next_steps),
                self._bundles(summary),
                self._artifacts(summary),
            ]
        return "\n\n".join("\n".join(block) for block in blocks if block) + "\n"

    # -- sections ----------------------------------------------------------------------------

    def _clarification(self, summary: AnalysisSummary) -> list[str]:
        t = self._t
        lines = [f"# {report_title(summary, t)}", "", f"## {t.t('summary.clarification_needed')}"]
        clarification = summary.clarification
        if clarification is None:
            return [*lines, "", summary.verdict.headline]
        lines += ["", f"**{clarification.question}**", "", f"{t.t('summary.candidates')}:"]
        for index, candidate in enumerate(clarification.candidates, start=1):
            description = f" — {candidate.description}" if candidate.description else ""
            lines.append(f"{index}. **{candidate.label}** ({candidate.qid}){description}")
        lines += ["", f"_{t.t('summary.clarification_hint')}_"]
        return lines

    def _answer(self, summary: AnalysisSummary) -> list[str]:
        t = self._t
        return [
            f"# {report_title(summary, t)}",
            "",
            f"**{t.t('summary.answer')}:** {summary.verdict.headline}",
            "",
            f"{question_line(summary, t)}{' · ' if summary.request.projects else ''}"
            f"{period_text(summary)}",
        ]

    def _key_numbers(self, summary: AnalysisSummary) -> list[str]:
        lines = [f"## {self._t.t('summary.key_numbers')}", ""]
        if summary.comparison:
            lines += comparison_table(summary, self._t)
        if summary.ranking:
            if summary.comparison:
                lines.append("")
            lines += ranking_table(summary, self._t)
        if summary.verdict.bullets:
            lines += ["", *[f"- {bullet}" for bullet in summary.verdict.bullets]]
        return lines if len(lines) > 2 else []  # noqa: PLR2004 -- heading + blank line only

    def _trust(self, summary: AnalysisSummary) -> list[str]:
        if not summary.reliability:
            return []
        lines = [f"## {self._t.t('summary.trust')}", ""]
        lines += [f"- {self._trust_line(summary, item)}" for item in summary.reliability]
        return lines

    def _trust_line(self, summary: AnalysisSummary, item: ReliabilityOut) -> str:
        label = row_label(summary, item.topic_id, item.project)
        level = self._t.label("level", item.level)
        reasons = "; ".join(c.message for c in sorted_checks(item.checks)[:MAX_REASONS])
        return f"**{label} — {item.project}: {level}.** {reasons}"

    def _list_section(self, key: str, items: Sequence[str]) -> list[str]:
        if not items:
            return []
        return [f"## {self._t.t(key)}", "", *[f"- {item}" for item in items]]

    def _bundles(self, summary: AnalysisSummary) -> list[str]:
        bundles = [bundle for topic in summary.resolution for bundle in topic.bundles]
        if not bundles:
            return []
        lines = [f"## {self._t.t('summary.bundles')}", ""]
        lines += [f"- {self._bundle_line(bundle)}" for bundle in bundles]
        return lines

    def _bundle_line(self, bundle: BundleOut) -> str:
        t = self._t
        status = t.label("bundle_status", bundle.status)
        if not bundle.articles:
            return f"**{bundle.project}**: {status}"
        parts = [
            f"{a.title} ({t.label('role', a.role)}, {t.number(a.weight, WEIGHT_DECIMALS)})"
            for a in bundle.articles
        ]
        return f"**{bundle.project}**: {status} — {'; '.join(parts)}"

    def _artifacts(self, summary: AnalysisSummary) -> list[str]:
        artifacts = summary.artifacts
        named = [
            ("report.pdf", artifacts.report_pdf),
            ("report.md", artifacts.report_md),
            ("summary.md", artifacts.summary_md),
            ("summary.json", artifacts.summary_json),
        ]
        lines = [f"## {self._t.t('summary.artifacts')}", ""]
        lines += [f"- {name}: `{path}`" for name, path in named if path]
        lines += [f"- {Path(chart).name}: `{chart}`" for chart in artifacts.charts]
        return lines
