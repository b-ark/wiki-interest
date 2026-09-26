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
    TrendOut,
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
        *_window(summary),
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


_TRUST_RULES = (
    (
        "Verdict",
        "Theil–Sen trend of the log attention share (seasonal rhythm divided out, "
        "bursts and months one day dominated left out) over the analysis window; after a step "
        "inside the window (six months against six, at least trust_split_step) that leaves at "
        "least trust_min_segment_months (more than one seasonal cycle), from the step on",
        "growing / declining beyond ±trust_stable_pct_per_year % a year, else stable",
    ),
    (
        "No verdict",
        "fewer than trust_min_window_months months, or fewer than trust_volume_floor views a month",
        "insufficient_data, confidence low",
    ),
    (
        "Year on year",
        "months of the window's last twelve on the verdict's side of the same month a year earlier",
        "a signal when at least trust_yoy_strong of 12",
    ),
    (
        "Slope interval",
        "90 % interval of the slope, moving-block bootstrap (blocks of "
        "trust_bootstrap_block months, trust_bootstrap_reps resamples, seed "
        "trust_bootstrap_seed)",
        "a signal when it leaves out zero",
    ),
    (
        "Signal/noise",
        "the trend's change over the segment against the standard deviation of "
        "its month-to-month changes",
        "a signal when at least trust_snr_min",
    ),
    ("growing / declining", "the three signals above", "3 high, 2 medium, 0–1 low"),
    (
        "Year on year against",
        "fewer than half the months compared on the verdict's side",
        "low: the slope contradicts the months",
    ),
    (
        "Control explains",
        "the control articles' median trend over the same months is at least "
        "trust_control_explains of the article's, the same way",
        "low: the edition moved, not the topic",
    ),
    (
        "stable",
        "the whole slope interval within ±trust_stable_pct_per_year % a year",
        "high; an interval past it medium; fewer than trust_min_window_months months fitted low",
    ),
    (
        "Step verdict",
        "the control articles' median change of level the same month is at "
        "least trust_control_explains of the article's, or the article was renamed within "
        "trust_rename_months",
        "artifact; otherwise real; no control data unknown",
    ),
    (
        "Spike month",
        "one day took more than trust_day_spike_share of the month's views",
        "left out of the slope",
    ),
    (
        "Control basket",
        "trust_control_sample articles drawn with seed trust_control_seed "
        "from the first trust_control_top of the reference month's top list, without the main "
        "page, other namespaces, articles younger than two years and bursts (over "
        "trust_control_spike_multiple times their median of the year before); rebuilt after "
        "trust_control_ttl_days days",
        "stored per edition next to the HTTP cache",
    ),
)


def _window(summary: AnalysisSummary) -> list[str]:
    """The analysis window, the verdict rules as a table, and each verdict's trust."""
    window = summary.analysis_window or summary.period
    context = summary.context_range
    lines = [
        "## The analysis window and the trust in its verdicts",
        "",
        f"Analysis window: {window.start:%Y-%m} – {window.end:%Y-%m}; the headline, each "
        "language's verdict, the comparison and the recommendation read it alone."
        + (
            f" The charts show the history from {context.start:%Y-%m} as context."
            if context is not None and context.start < window.start
            else ""
        ),
        "",
        "| Rule | How | Outcome |",
        "| --- | --- | --- |",
        *(f"| {rule} | {how} | {outcome} |" for rule, how, outcome in _TRUST_RULES),
        "",
    ]
    for item in summary.verdicts:
        lines += _verdict(item)
    return lines


def _or_na(value: float | None) -> str:
    return "n/a" if value is None else str(value)


def _verdict(item: TrendOut) -> list[str]:
    head = (
        f"- {item.topic_id} in {item.project}: {item.verdict}, trend read from "
        f"{item.segment_start}"
        + (
            f" (after the step of {item.after_step}, {item.step_change:+.0f} %)"
            if item.after_step
            else ""
        )
    )
    if item.level_start is not None and item.level_end is not None:
        head += (
            f"; trend line {item.level_start} → {item.level_end} per million, "
            f"{item.slope_pct_per_year:+.0f} % a year"
        )
    lines = [head + "."]
    trust = item.trust
    if trust is None:
        return lines
    ci = f"[{trust.ci90[0]:+.0f}; {trust.ci90[1]:+.0f}]" if trust.ci90 else "n/a"
    lines.append(
        f"  - Confidence {trust.confidence}: year on year {trust.yoy_down} down, "
        f"{trust.yoy_up} up of {trust.yoy_months}; 90 % interval {ci} % a year; signal/noise "
        f"{trust.snr if trust.snr is not None else 'n/a'}; control articles "
        + (
            f"{trust.control_change:+.0f} % a year ({trust.control_articles} articles)"
            if trust.control_change is not None
            else "none"
        )
        + f"; largest one-day share of a month {_or_na(trust.max_day_share)}"
        + (
            f"; spike months left out: {', '.join(trust.spike_months)}"
            if trust.spike_months
            else ""
        )
        + "."
    )
    for b in trust.breakpoints:
        control = (
            f"control {b.control_change_same_month:+.0f} %"
            if b.control_change_same_month is not None
            else "no control data"
        )
        lines.append(
            f"  - Step {b.month} ({'in the window' if b.in_window else 'history'}): "
            f"{b.change:+.0f} %, {control}, {'renamed' if b.renamed else 'not renamed'}: "
            f"{b.verdict}; trend before "
            f"{'n/a' if b.slope_before is None else f'{b.slope_before:+.0f} %'}, after "
            f"{'n/a' if b.slope_after is None else f'{b.slope_after:+.0f} %'} a year."
        )
    return lines


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
