"""``method.md``: how every number of one run was computed, its data checks and thresholds.

The one-page report states results; this file is where a reader checks them: what was
measured in each edition, the windows, the trend test with its p-value (the only place the
reports speak of statistical significance), whether recent months confirm the trend, the data
checks, the season and the months that stand out, and the thresholds in force. It is written
in English, as technical documentation next to the report, and linked from the PDF footer;
``report.appendix: true`` also prints it as a second PDF page.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from wiki_interest.contracts.summary import (
    AnalysisSummary,
    AssessmentOut,
    MetricsOut,
    ReliabilityOut,
    TopicResolutionOut,
)
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

__all__ = ["MethodReportRenderer", "method_markdown"]

_PERCENT = 100.0
_SIGNED = "+"
_BASES = {
    "yoy": "the last 12 months against the 12 before",
    "halves": "the second half of the period against the first",
    "slope": "the fitted trend per year",
}
_CONFIRMATION = {
    "confirmed": "confirmed: the last months move the same way",
    "mixed": "mixed: the last months no longer follow the trend clearly",
    "reversing": "contradicts: the last months move against the trend",
    "unknown": "insufficient: the data cannot tell",
}
_SEASON_REASONS = {
    "solid": "stated: enough years, repeated, material",
    "short_history": "not stated: fewer full years than needed",
    "inconsistent": "not stated: the peak or trough month moves between years",
    "weak": "not stated: too small against the usual level",
    "no_data": "not computed: not every calendar month observed twice",
}
_NATURES = {
    "event": "an event (readers through every access method, or a burst of daily views)",
    "possible_bot": "possibly automated traffic (one access method, or automated traffic)",
    "edition": "the whole edition moved, not the article",
    "unknown": "cause unknown",
}


class MethodReportRenderer:
    """Writes ``method.md`` (implements :class:`~wiki_interest.ports.ReportRenderer`)."""

    def render(self, summary: AnalysisSummary, charts: Sequence[Path], output_path: Path) -> Path:
        """Write the method note of ``summary`` to ``output_path``.

        Raises:
            RenderError: If the file cannot be written.
        """
        del charts
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(method_markdown(summary), encoding="utf-8")
        except OSError as exc:
            msg = f"Cannot write {output_path}: {exc}"
            raise RenderError(msg, hint="Check that the run directory is writable") from exc
        return output_path


def method_markdown(summary: AnalysisSummary) -> str:
    """The method note as Markdown: headings, paragraphs and bullet lists only."""
    request = summary.request
    lines = [
        "# Method",
        "",
        f"Period: {summary.period.start:%Y-%m} – {summary.period.end:%Y-%m}. Source: Wikimedia "
        f"Pageviews API, agent={request.agent}, access={request.access}; Wikidata and the "
        "MediaWiki API to find the articles.",
        "",
        "## What was measured",
        "",
        "- Article views: monthly views of the topic's main article, with the redirects that "
        "lead to it; the same Wikidata item in every edition.",
        "- Edition traffic: monthly views of the whole language edition.",
        "- Attention share: article views per 1 million views of the edition, comparable "
        "across editions of any size."
        + (" This run analysed raw views." if request.normalization == "absolute" else ""),
        "",
        *_articles(summary.resolution),
        "## Per edition",
        "",
    ]
    for item in summary.assessments:
        lines += _pair(summary, item)
    lines += ["## Thresholds in force", ""]
    lines += [f"- {name}: {value}" for name, value in sorted(summary.provenance.thresholds.items())]
    lines += [
        "",
        "Each can be changed with a `WIKI_INTEREST_<NAME>` environment variable. The rules "
        "themselves are described in `references/methodology.md` of the skill.",
        "",
    ]
    return "\n".join(lines)


def _articles(resolution: Sequence[TopicResolutionOut]) -> list[str]:
    lines: list[str] = []
    for topic in resolution:
        lines.append(
            f"Topic `{topic.topic_id}`: {topic.label or topic.query} ({topic.qid or 'no item'})"
            + (f", {topic.description}" if topic.description else "")
            + "."
        )
        lines.append("")
        for bundle in topic.bundles:
            main = next((a for a in bundle.articles if a.role == "main"), None)
            if main is None:
                lines.append(f"- {bundle.project}: no article.")
                continue
            redirects = f", with {bundle.redirect_count} redirects" if bundle.redirect_count else ""
            kind = bundle.substitute_kind
            substitute = f" (substitute: {kind})" if kind else ""
            lines.append(f"- {bundle.project}: '{main.title}'{redirects}{substitute}.")
        lines.append("")
    return lines


def _pair(summary: AnalysisSummary, item: AssessmentOut) -> list[str]:
    lines = [f"### {item.label}", ""]
    if not item.measured:
        return [*lines, "No article: nothing measured.", ""]
    metrics = _metrics(summary.metrics, item)
    basis = _BASES.get(item.basis or "", "not computable")
    lines += [
        f"- Attention share: {_number(item.per_million, 1)} per million; article views "
        f"{_number(item.views_avg, 0)} a month (means over the period).",
        f"- Change ({basis}): {_percent(item.change)}. Article views "
        f"{_percent(item.article_change)}, edition traffic "
        f"{_percent(item.edition_change)}, attention share {_percent(item.share_change)}.",
    ]
    if metrics is not None and metrics.trend_p_value is not None:
        alpha = summary.provenance.thresholds.get("trend_p_value", 0.05)
        significant = metrics.trend_p_value < float(alpha)
        lines.append(
            f"- Trend test (Mann-Kendall on the {'share' if item.per_million else 'views'}): "
            f"p = {metrics.trend_p_value:.3f}, "
            + ("statistically significant" if significant else "not statistically significant")
            + f" at {alpha}; momentum: {item.momentum}."
        )
    if item.recent_months:
        lines.append(
            f"- Recent months ({item.recent_months} against the same months a year earlier): "
            f"article views {_percent(item.recent_article)}, edition traffic "
            f"{_percent(item.recent_edition)}, share {_percent(item.recent_shift)}; "
            f"{_CONFIRMATION.get(str(item.robustness), str(item.robustness))}."
        )
    reliability = _reliability(summary.reliability, item)
    if item.data_quality is not None:
        concerns = [
            c.name
            for c in (reliability.checks if reliability else [])
            if c.status in ("warn", "fail") and c.name != "trend"
        ]
        reasons = ", ".join(concerns) or "no concerns"
        lines.append(f"- Data quality: {item.data_quality.level} ({reasons}).")
    lines += _checks(reliability)
    season = item.season
    if season is not None:
        detail = _SEASON_REASONS.get(season.reason, season.reason)
        if season.peak_month is not None and season.peak is not None and season.trough is not None:
            detail += (
                f"; month {season.peak_month} {_percent(season.peak)}, month "
                f"{season.trough_month} {_percent(season.trough)} against the usual level"
            )
        lines.append(
            f"- Season ({season.start} – {season.end}, {season.years} full years"
            + (f", consistency {season.consistency:.0%}" if season.consistency is not None else "")
            + (f", strength {season.strength:.2f}" if season.strength is not None else "")
            + f"): {detail}."
        )
    for month in item.months:
        multiples = ", ".join(f"{m} ×{v:.1f}" for m, v in sorted(month.multiples.items()))
        without = (
            f"; the headline change without it: {_percent(month.change_without)}"
            if month.change_without is not None
            else ""
        )
        lines.append(
            f"- {month.month} stands out ({multiples}): {_NATURES.get(month.nature, month.nature)}"
            f"{without}."
        )
    return [*lines, ""]


def _checks(reliability: ReliabilityOut | None) -> list[str]:
    """Every data check with its message in English, whatever the report language."""
    if reliability is None:
        return []
    english = Translator("en")
    out: list[str] = []
    for check in reliability.checks:
        try:
            message = english.t(check.reason_key, **check.params)
        except KeyError:
            message = check.message
        out.append(f"  - check `{check.name}`: {check.status} — {message}")
    return out


def _metrics(rows: Sequence[MetricsOut], item: AssessmentOut) -> MetricsOut | None:
    return next((m for m in rows if (m.topic_id, m.project) == (item.topic_id, item.project)), None)


def _reliability(rows: Sequence[ReliabilityOut], item: AssessmentOut) -> ReliabilityOut | None:
    return next((r for r in rows if (r.topic_id, r.project) == (item.topic_id, item.project)), None)


def _number(value: float | None, decimals: int) -> str:
    return "n/a" if value is None else f"{value:,.{decimals}f}"


def _percent(value: float | None) -> str:
    if value is None:
        return "n/a"
    sign = _SIGNED if value > 0 else ""
    return f"{sign}{value * _PERCENT:.1f}%"
