"""Markdown implementation of :class:`~wiki_interest.ports.renderers.ReportRenderer`.

``report.md`` is the user-facing document: the same content as the PDF, but without the
one-page constraint, so every section of the summary is present in full. All prose comes
from the summary (already localised); this module only adds section titles, table headers
and number formatting through the :class:`Translator`. Empty sections are skipped rather than
rendered as empty headings.

The table and label helpers are public because ``agent_summary`` builds its condensed view
from the same blocks; one implementation keeps the two documents consistent.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from wiki_interest.contracts.summary import (
    AnalysisSummary,
    ArticleOut,
    BundleOut,
    CheckOut,
    ReliabilityOut,
)
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

__all__ = [
    "MarkdownReportRenderer",
    "bundle_lines",
    "comparison_table",
    "markdown_table",
    "period_text",
    "question_line",
    "ranking_table",
    "relative_chart_path",
    "report_title",
    "row_label",
    "sorted_checks",
]

PERCENT_DECIMALS = 0
PER_MILLION_DECIMALS = 1
SCORE_DECIMALS = 2
WEIGHT_DECIMALS = 2
SEPARATOR = " · "
RANGE_DASH = " – "  # noqa: RUF001 -- an en dash is the typographic range separator
GENERATED_AT_FORMAT = "%Y-%m-%d %H:%M UTC"

_STATUS_SEVERITY = {"fail": 0, "warn": 1, "info": 2, "pass": 3}
"""Order in which reasons are shown: what lowers trust comes first."""


class MarkdownReportRenderer:
    """Writes the full report as Markdown with charts embedded by relative path."""

    def __init__(self, translator: Translator) -> None:
        self._t = translator

    def render(self, summary: AnalysisSummary, charts: Sequence[Path], output_path: Path) -> Path:
        """Write ``report.md``; chart image links are relative to the report's directory.

        Raises:
            RenderError: If the file cannot be written.
        """
        text = self.build(summary, charts, output_path.parent)
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(text, encoding="utf-8", newline="\n")
        except OSError as exc:
            msg = f"Cannot write Markdown report to {output_path}: {exc}"
            raise RenderError(msg, hint="Check that the run directory is writable") from exc
        return output_path

    def build(self, summary: AnalysisSummary, charts: Sequence[Path], base_dir: Path) -> str:
        """Return the document text without touching the file system."""
        blocks = [
            self._header(summary),
            self._key_numbers(summary),
            self._charts(summary, charts, base_dir),
            self._verdict(summary),
            self._reliability(summary),
            self._bundles(summary),
            self._ranking(summary),
            self._list_section("report.limitations", summary.limitations),
            self._list_section("report.next_steps", summary.next_steps),
            self._footer(summary),
        ]
        return "\n\n".join("\n".join(block) for block in blocks if block) + "\n"

    # -- sections ----------------------------------------------------------------------------

    def _header(self, summary: AnalysisSummary) -> list[str]:
        t = self._t
        lines = [f"# {report_title(summary, t)}", ""]
        lines.append(f"**{t.t('report.question')}:** {question_line(summary, t)}")
        note = summary.request.report.audience_note
        if note:
            lines.append(f"**{t.t('report.audience')}:** {note}")
        lines.append(
            f"**{t.t('report.period')}:** {period_text(summary)}{SEPARATOR}"
            f"**{t.t('report.projects')}:** {', '.join(summary.request.projects)}"
        )
        return lines

    def _key_numbers(self, summary: AnalysisSummary) -> list[str]:
        if not summary.comparison:
            return []
        lines = [f"## {self._t.t('report.key_numbers')}", "", *comparison_table(summary, self._t)]
        notes = [
            f"- {row.label} ({row.project}): {row.note}" for row in summary.comparison if row.note
        ]
        if notes:
            lines += ["", f"*{self._t.t('report.notes')}:*", *notes]
        return lines

    def _charts(
        self, summary: AnalysisSummary, charts: Sequence[Path], base_dir: Path
    ) -> list[str]:
        images = [c for c in charts if c.suffix.lower() == ".png"] or list(charts)
        if not images:
            return []
        titles = {spec.id: spec.title for spec in summary.charts}
        key = "report.charts" if len(images) > 1 else "report.chart"
        lines = [f"## {self._t.t(key)}", ""]
        for image in images:
            title = titles.get(image.stem, image.stem)
            lines += [f"![{title}]({relative_chart_path(image, base_dir)})", ""]
        return lines[:-1]

    def _verdict(self, summary: AnalysisSummary) -> list[str]:
        lines = [f"## {self._t.t('report.verdict')}", "", f"**{summary.verdict.headline}**"]
        if summary.verdict.bullets:
            lines += ["", *[f"- {bullet}" for bullet in summary.verdict.bullets]]
        return lines

    def _reliability(self, summary: AnalysisSummary) -> list[str]:
        if not summary.reliability:
            return []
        lines = [f"## {self._t.t('report.reliability')}"]
        for item in summary.reliability:
            lines += ["", self._reliability_heading(summary, item)]
            lines += [f"- {self._check_line(check)}" for check in sorted_checks(item.checks)]
        return lines

    def _reliability_heading(self, summary: AnalysisSummary, item: ReliabilityOut) -> str:
        label = row_label(summary, item.topic_id, item.project)
        level = self._t.label("level", item.level)
        return f"### {label} — {item.project}: {level}"

    def _check_line(self, check: CheckOut) -> str:
        return f"{self._t.label('status', check.status)}: {check.message}"

    def _bundles(self, summary: AnalysisSummary) -> list[str]:
        if not summary.resolution:
            return []
        lines = [f"## {self._t.t('report.bundle_composition')}"]
        for topic in summary.resolution:
            heading = topic.label or topic.query
            if topic.qid:
                heading = f"{heading} ({topic.qid})"
            lines += ["", f"### {heading}"]
            for bundle in topic.bundles:
                lines += ["", *bundle_lines(bundle, self._t)]
        return lines

    def _ranking(self, summary: AnalysisSummary) -> list[str]:
        if not summary.ranking:
            return []
        return [f"## {self._t.t('report.ranking_table')}", "", *ranking_table(summary, self._t)]

    def _list_section(self, key: str, items: Sequence[str]) -> list[str]:
        if not items:
            return []
        return [f"## {self._t.t(key)}", "", *[f"- {item}" for item in items]]

    def _footer(self, summary: AnalysisSummary) -> list[str]:
        t = self._t
        provenance = summary.provenance
        parts = [
            f"{t.t('report.sources')}: {', '.join(provenance.sources)}",
            f"{t.t('report.data_through')}: {provenance.data_through}",
            f"{t.t('report.generated')}: {provenance.generated_at.strftime(GENERATED_AT_FORMAT)}",
            f"{t.t('report.version')}: {provenance.code_version}",
        ]
        return ["---", "", SEPARATOR.join(parts)]


# -- shared building blocks -------------------------------------------------------------------


def report_title(summary: AnalysisSummary, t: Translator) -> str:
    """The user's title if given, otherwise the localised default."""
    return summary.request.report.title or t.t("report.title_default")


def question_line(summary: AnalysisSummary, t: Translator) -> str:
    """One sentence restating the request, so the reader knows what was asked."""
    topics = ", ".join(topic.query for topic in summary.request.topics)
    projects = ", ".join(summary.request.projects)
    return t.t(f"question.{summary.request.question_type}", topics=topics, projects=projects)


def period_text(summary: AnalysisSummary) -> str:
    """The period as ``start – end`` (en dash), e.g. ``2024-09`` to ``2026-08``."""  # noqa: RUF002
    return f"{summary.period.start:%Y-%m}{RANGE_DASH}{summary.period.end:%Y-%m}"


def relative_chart_path(chart: Path, base_dir: Path) -> str:
    """POSIX-style path of ``chart`` relative to ``base_dir``; absolute when no relation exists.

    ``os.path.relpath`` raises on Windows when the two paths sit on different drives, and a
    report must still link to the image in that case.
    """
    try:
        return Path(os.path.relpath(chart, base_dir)).as_posix()
    except ValueError:
        return chart.as_posix()


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Render a GitHub-flavoured Markdown table; pipes inside cells are escaped."""
    escaped = [[cell.replace("|", "\\|") for cell in row] for row in rows]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(" --- " for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in escaped]
    return lines


def comparison_table(summary: AnalysisSummary, t: Translator) -> list[str]:
    """Key-numbers table with one row per (topic, project)."""
    headers = [
        t.t("col.topic"),
        t.t("col.project"),
        t.t("col.views_avg"),
        t.t("col.per_million_avg"),
        t.t("col.growth_yoy"),
        t.t("col.growth_halves"),
        t.t("col.trend"),
        t.t("col.reliability"),
    ]
    rows = [
        [
            row.label,
            row.project,
            t.number(row.views_avg),
            t.number(row.per_million_avg, PER_MILLION_DECIMALS),
            t.percent(row.growth_yoy, PERCENT_DECIMALS, signed=True),
            t.percent(row.growth_halves, PERCENT_DECIMALS, signed=True),
            t.label("direction", row.trend_direction),
            t.label("level", row.reliability),
        ]
        for row in summary.comparison
    ]
    return markdown_table(headers, rows)


def ranking_table(summary: AnalysisSummary, t: Translator) -> list[str]:
    """Ranking table, best first, with the localised profile and the rationale."""
    headers = [
        t.t("col.rank"),
        t.t("col.topic"),
        t.t("col.project"),
        t.t("col.score"),
        t.t("col.profile"),
        t.t("col.reliability"),
        t.t("col.rationale"),
    ]
    rows = [
        [
            str(row.rank),
            row.label,
            row.project,
            t.number(row.score, SCORE_DECIMALS),
            t.label("profile", row.profile),
            t.label("level", row.reliability),
            row.rationale,
        ]
        for row in sorted(summary.ranking, key=lambda r: r.rank)
    ]
    return markdown_table(headers, rows)


def bundle_lines(bundle: BundleOut, t: Translator) -> list[str]:
    """Status line for one bundle followed by its article table (if any)."""
    lines = [f"**{bundle.project}** — {t.label('bundle_status', bundle.status)}"]
    if bundle.articles:
        headers = [t.t("col.article"), t.t("col.role"), t.t("col.weight"), t.t("col.source")]
        rows = [
            [
                _article_cell(article),
                t.label("role", article.role),
                t.number(article.weight, WEIGHT_DECIMALS),
                t.label("source", article.source),
            ]
            for article in bundle.articles
        ]
        lines += ["", *markdown_table(headers, rows)]
    return lines


def row_label(summary: AnalysisSummary, topic_id: str, project: str) -> str:
    """Human label for a (topic, project): the comparison/ranking label, else the topic id."""
    for comparison_row in summary.comparison:
        if comparison_row.topic_id == topic_id and comparison_row.project == project:
            return comparison_row.label
    for ranked_row in summary.ranking:
        if ranked_row.topic_id == topic_id and ranked_row.project == project:
            return ranked_row.label
    return topic_id


def sorted_checks(checks: Sequence[CheckOut]) -> list[CheckOut]:
    """Checks ordered fail, warn, info, pass; original order within a status (stable sort)."""
    return sorted(checks, key=lambda c: _STATUS_SEVERITY.get(str(c.status), len(_STATUS_SEVERITY)))


def _article_cell(article: ArticleOut) -> str:
    if not article.redirects:
        return article.title
    return f"{article.title} (← {', '.join(article.redirects)})"
