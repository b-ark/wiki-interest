"""``summary.md``: the short, structured text the agent relays almost verbatim.

This is the anti-hallucination layer of the skill (plan §6.3): the answer, the key numbers,
the topic against its edition, what it means for the decision, the next step, the trust level
with its reasons, the caveats and the follow-up hints are all written by code so a cheap model
has nothing to compute or remember. The document is kept scannable (one
screen for a two-edition comparison) and, when the pipeline stopped for clarification, it
shows only the question and the candidates (or, for editions without an article, the
options that could stand in) so the agent asks instead of guessing.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from wiki_interest.adapters.report_blocks import (
    decision_lines,
    edition_basis,
    edition_lines,
    kpi_table,
    markdown_table,
    period_text,
    question_line,
    ranking_table,
    report_title,
    robustness_lines,
)
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    BundleOut,
    Clarification,
)
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

__all__ = ["AgentSummaryRenderer"]


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
        elif summary.status == "topic_resolved":
            blocks = [
                [f"# {report_title(summary, self._t)}", "", summary.verdict.headline],
                self._topic_lines(summary),
                self._bundles(summary),
            ]
        else:
            blocks = [
                self._answer(summary),
                self._cards(summary),
                self._vs_edition(summary),
                self._robustness(summary),
                self._list_section("summary.decision", decision_lines(summary)),
                self._list_section("summary.findings", summary.verdict.bullets),
                self._key_numbers(summary),
                self._list_section(
                    "summary.caveats", [*summary.limitations, *summary.general_limitations]
                ),
                self._list_section("summary.refine", summary.next_steps),
                self._bundles(summary),
                self._artifacts(summary),
            ]
        return "\n\n".join("\n".join(block) for block in blocks if block) + "\n"

    # -- sections ----------------------------------------------------------------------------

    def _clarification(self, summary: AnalysisSummary) -> list[str]:
        t = self._t
        clarification = summary.clarification
        if clarification is not None and clarification.kind == "missing_article":
            return self._coverage_question(summary, clarification)
        if clarification is not None and clarification.kind == "topic_not_found":
            return [
                f"# {report_title(summary, t)}",
                "",
                f"## {t.t('summary.not_found_needed')}",
                "",
                summary.verdict.headline,
                "",
                f"_{clarification.question}_",
            ]
        lines = [f"# {report_title(summary, t)}", "", f"## {t.t('summary.clarification_needed')}"]
        if clarification is None:
            return [*lines, "", summary.verdict.headline]
        lines += ["", f"**{clarification.question}**", "", f"{t.t('summary.candidates')}:"]
        for index, candidate in enumerate(clarification.candidates, start=1):
            description = f" — {candidate.description}" if candidate.description else ""
            articles = (
                t.t("summary.candidate_articles", projects=", ".join(candidate.article_projects))
                if candidate.article_projects
                else t.t("summary.candidate_no_articles")
            )
            lines.append(
                f"{index}. **{candidate.label}** ({candidate.qid}){description} · {articles}"
            )
        lines += ["", f"_{t.t('summary.clarification_hint')}_"]
        return lines

    def _coverage_question(
        self, summary: AnalysisSummary, clarification: Clarification
    ) -> list[str]:
        """Editions without an article: numbered options for the user, then how to apply one.

        The ``choose`` values sit in a separate block for the agent, so the list the user sees
        stays plain language while the value that goes into the request is copied, not typed.
        """
        t = self._t
        lines = [
            f"# {report_title(summary, t)}",
            "",
            f"## {t.t('summary.missing_needed')}",
            "",
            summary.verdict.headline,
        ]
        if clarification.ask_user:
            lines += ["", f"## {t.t('summary.ask_user')}", "", clarification.ask_user]
        noted: set[str] = set()
        for gap in clarification.gaps:
            if gap.topic_id not in noted:
                noted.add(gap.topic_id)
                lines += ["", gap.topic_note]
            lines += ["", f"**{gap.question}**", ""]
            lines += [f"{option.number}. {option.description}" for option in gap.options]
        lines += ["", f"_{clarification.question}_", "", f"## {t.t('summary.apply_choice')}", ""]
        for gap in clarification.gaps:
            for option in gap.options:
                choose = {
                    project: value if isinstance(value, str) else value.model_dump()
                    for project, value in option.choose.items()
                }
                value = json.dumps(choose, ensure_ascii=False)
                lines.append(f"- {gap.topic_id} · {gap.project} · {option.number}: `{value}`")
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
            *self._topic_lines(summary),
        ]

    def _cards(self, summary: AnalysisSummary) -> list[str]:
        """What happened (each number with its metric and window), then the key numbers."""
        lines = [f"- {item}" for item in summary.happening]
        headers, rows = kpi_table(summary, self._t)
        if rows:
            lines += (
                ["", *markdown_table(headers, rows)] if lines else markdown_table(headers, rows)
            )
        return lines

    def _vs_edition(self, summary: AnalysisSummary) -> list[str]:
        items = edition_lines(summary)
        if not items:
            return []
        lines = [f"## {self._t.t('report.vs_edition')}", ""]
        basis = edition_basis(summary, self._t)
        if basis:
            lines += [f"_{basis}_", ""]
        return lines + [f"- {item}" for item in items]

    def _topic_lines(self, summary: AnalysisSummary) -> list[str]:
        """Which entity each topic is, and what else the name could mean.

        Shown first so the agent checks the entity against the user's meaning before
        relaying numbers about, say, the planet when the user asked about the element.
        """
        t = self._t
        lines: list[str] = []
        for topic in summary.resolution:
            if topic.qid is None:
                continue
            description = (
                t.t("gap.entity_description", description=topic.description)
                if topic.description
                else ""
            )
            line = t.t(
                "summary.topic_line",
                label=topic.label or topic.query,
                description=description,
                qid=topic.qid,
            )
            if topic.method == "auto":
                line += " " + t.t("summary.topic_auto", qid=topic.qid)
            if topic.alternatives:
                items = "; ".join(
                    f"{c.label} ({c.qid})" + (f" — {c.description}" if c.description else "")
                    for c in topic.alternatives
                )
                line += " " + t.t("summary.alternatives", items=items)
            lines += ["", line]
        return lines

    def _key_numbers(self, summary: AnalysisSummary) -> list[str]:
        # The key numbers are the table under the answer; only a ranking adds its own table.
        if not summary.ranking:
            return []
        return [f"## {self._t.t('report.ranking_table')}", "", *ranking_table(summary, self._t)]

    def _robustness(self, summary: AnalysisSummary) -> list[str]:
        items = robustness_lines(summary)
        if not items:
            return []
        lines = [f"## {self._t.t('report.robustness')}", "", *[f"- {i}" for i in items]]
        if summary.data_note:
            lines += ["", *summary.data_note]
        return lines

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
        if bundle.substitute_kind is not None and bundle.articles:
            what = t.t(f"substitute.{bundle.substitute_kind}", title=bundle.articles[0].title)
            status = t.t("note.substitute", what=what)
        if not bundle.articles:
            return f"**{bundle.project}**: {status}"
        main = bundle.articles[0]
        redirects = (
            f" ({t.t('summary.redirects', count=bundle.redirect_count)})"
            if bundle.redirect_count
            else ""
        )
        return f"**{bundle.project}**: {status} — {main.title}{redirects}"

    def _artifacts(self, summary: AnalysisSummary) -> list[str]:
        artifacts = summary.artifacts
        named = [
            ("report.pdf", artifacts.report_pdf),
            ("summary.md", artifacts.summary_md),
            ("summary.json", artifacts.summary_json),
        ]
        lines = [f"## {self._t.t('summary.artifacts')}", ""]
        lines += [f"- {name}: `{path}`" for name, path in named if path]
        lines += [f"- {Path(chart).name}: `{chart}`" for chart in artifacts.charts]
        return lines
