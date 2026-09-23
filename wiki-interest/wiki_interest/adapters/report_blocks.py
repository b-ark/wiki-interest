"""Blocks of the answer that every document shows the same way.

``report.pdf``, ``report.md`` and ``summary.md`` all lead with the same answer: three cards
(size of interest, its change, whether recent months confirm it), the topic against its
edition, what it means for the decision and the next step, and how robust the conclusion
is. The wording comes from the summary; this module only arranges it, so the three documents
cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from wiki_interest.contracts.summary import AnalysisSummary, AssessmentOut
from wiki_interest.i18n import Translator

__all__ = [
    "Card",
    "cards",
    "coverage_line",
    "decision_lines",
    "edition_basis",
    "edition_lines",
    "kpi_table",
    "momentum_text",
    "ordered_assessments",
    "per_million_text",
    "robustness_lines",
    "robustness_value",
    "short_label",
]

PER_MILLION_DECIMALS = 1
PERCENT_DECIMALS = 0
ARROWS = {"growing": "↑", "declining": "↓", "flat": "→"}
"""Direction marks next to a change; ``→`` is "no clear trend", whatever the sign."""
MAX_CARD_ROWS = 3
SHORT_LABEL_MAX_CHARS = 14
ELLIPSIS = "…"


@dataclass(frozen=True, slots=True)
class Card:
    """One key-number card: a label, one line per audience, and an optional small note."""

    label: str
    rows: list[str]
    note: str | None = None


def ordered_assessments(summary: AnalysisSummary) -> list[AssessmentOut]:
    """Audiences in reading order: by rank for a ranking, else as requested."""
    items = list(summary.assessments)
    if summary.ranking:
        rank = {(r.topic_id, r.project): r.rank for r in summary.ranking}
        items.sort(key=lambda a: rank.get((a.topic_id, a.project), len(rank) + 1))
    return items


def short_label(summary: AnalysisSummary, item: AssessmentOut) -> str:
    """``ru`` for ``ru.wikipedia``; with several topics ``ru Yoga``; substitutes keep their title.

    The assessment label already names a substitute (``pl.wikipedia (Post)``), so the short
    form is derived from it rather than from the bare edition.
    """
    code = item.label.split(" · ")[-1].replace(".wikipedia", "")
    topics = {a.topic_id for a in summary.assessments}
    if len(topics) <= 1:
        return code
    topic = next(
        (t.label or t.query for t in summary.resolution if t.topic_id == item.topic_id),
        item.topic_id,
    )
    return f"{code} {_shorten(topic)}"


def per_million_text(value: float | None, t: Translator) -> str:
    """``39.3 per million``: views of the topic per million views of the whole edition."""
    if value is None:
        return t.t("value.na")
    return t.t("value.per_million", value=t.number(value, PER_MILLION_DECIMALS))


def momentum_text(item: AssessmentOut, t: Translator) -> str:
    """The change with its direction mark: ``-17 % ↓``; ``→`` marks no clear trend."""
    if item.change is None:
        return t.t("value.na")
    arrow = ARROWS.get(str(item.momentum), "")
    change = t.percent(item.change, PERCENT_DECIMALS, signed=True)
    return f"{change} {arrow}".strip()


def cards(summary: AnalysisSummary, t: Translator) -> list[Card]:
    """Size of interest, its change and whether recent months confirm it, for up to three."""
    items = ordered_assessments(summary)[:MAX_CARD_ROWS]
    if not items:
        return []
    normalised = summary.request.normalization == "per_million"
    keys = [short_label(summary, item) for item in items]
    measured = [(k, a) for k, a in zip(keys, items, strict=True) if a.measured]
    no_article = t.t("card.no_article")

    def row(key: str, item: AssessmentOut, value: str) -> str:
        return f"{key}: {value if item.measured else no_article}"

    if normalised:
        size = Card(
            t.t("card.size"),
            [
                row(k, a, per_million_text(a.per_million, t))
                for k, a in zip(keys, items, strict=True)
            ],
            t.t(
                "card.views_note",
                items="; ".join(f"{k} {t.number(a.views_avg)}" for k, a in measured),
            )
            if measured
            else None,
        )
    else:
        size = Card(
            t.t("card.size_absolute"),
            [row(k, a, t.number(a.views_avg)) for k, a in zip(keys, items, strict=True)],
        )
    bases = {a.basis for _, a in measured if a.basis}
    change = Card(
        t.t("card.momentum" if normalised else "card.momentum_absolute"),
        [row(k, a, momentum_text(a, t)) for k, a in zip(keys, items, strict=True)],
        t.t(f"basis.{bases.pop()}") if len(bases) == 1 else None,
    )
    windows = {a.recent_months for _, a in measured if a.recent_months}
    recent = Card(
        t.t("card.robustness"),
        [row(k, a, robustness_value(a, t)) for k, a in zip(keys, items, strict=True)],
        t.t("report.recent_basis", months=windows.pop()) if len(windows) == 1 else None,
    )
    return [size, change, recent]


def robustness_value(item: AssessmentOut, t: Translator) -> str:
    """``yes`` / ``no, the share is steady`` / ``no, the direction changed`` / ...

    A mixed signal reads differently with and without a long-term trend: a decline that
    stalled leaves the share steady, while a flat series that recently moved did not.
    """
    key = str(item.robustness)
    if key == "mixed" and str(item.momentum) == "flat":
        key = "mixed_flat"
    return t.t(f"robustness.value.{key}")


def kpi_table(summary: AnalysisSummary, t: Translator) -> tuple[list[str], list[list[str]]]:
    """Key numbers as rows of metrics and one column per audience, each row naming its metric.

    Article views per month, attention share, its change over the headline window and whether
    the last months confirm it: the four numbers a reader needs to follow the answer.
    """
    items = ordered_assessments(summary)
    if not items:
        return [], []
    normalised = summary.request.normalization == "per_million"
    no_article = t.t("card.no_article")

    def cells(value: Callable[[AssessmentOut], str]) -> list[str]:
        return [value(a) if a.measured else no_article for a in items]

    measured = [a for a in items if a.measured]
    bases = {a.basis for a in measured if a.basis}
    basis = t.t(f"basis.{bases.pop()}") if len(bases) == 1 else t.t("basis.mixed")
    months = {a.recent_months for a in measured if a.recent_months}
    metric = t.t("metric.attention_share" if normalised else "metric.article_views")
    rows = [[t.t("kpi.views"), *cells(lambda a: t.number(a.views_avg))]]
    if normalised:
        rows.append([t.t("kpi.share"), *cells(lambda a: t.number(a.per_million, 1))])
    rows.append(
        [
            t.t("kpi.change", metric=metric, basis=basis),
            *cells(lambda a: t.percent(a.change, PERCENT_DECIMALS, signed=True)),
        ]
    )
    rows.append(
        [
            t.t("kpi.recent", months=months.pop() if len(months) == 1 else 3),
            *cells(lambda a: robustness_value(a, t)),
        ]
    )
    return [t.t("kpi.metric"), *(a.label for a in items)], rows


def robustness_lines(summary: AnalysisSummary) -> list[str]:
    """How robust the conclusion is, one line per measured audience, reading order."""
    return [a.robustness_line for a in ordered_assessments(summary) if a.robustness_line]


def edition_lines(summary: AnalysisSummary) -> list[str]:
    """``ru.wikipedia: article -36 %, whole edition -22 % → the topic loses share``."""
    return [a.edition_line for a in ordered_assessments(summary) if a.edition_line]


def edition_basis(summary: AnalysisSummary, t: Translator) -> str | None:
    """Which months the edition comparison covers, stated once under its heading."""
    bases = {a.relation_basis for a in summary.assessments if a.relation_basis}
    if len(bases) != 1:
        return None
    return t.t("report.vs_edition_basis", basis=t.t(f"basis.{bases.pop()}"))


def decision_lines(summary: AnalysisSummary) -> list[str]:
    """The conclusion, one line per outcome when there is a choice to make, the next step."""
    decision = summary.decision
    if decision is None:
        return []
    first = [decision.summary] if decision.summary else []
    return [*first, *decision.lines, decision.next_step]


def coverage_line(summary: AnalysisSummary, t: Translator) -> str | None:
    """How many related articles were found and that they are not in the metric."""
    counts = [
        (bundle.project.replace(".wikipedia", ""), bundle.related_count)
        for topic in summary.resolution
        for bundle in topic.bundles
        if bundle.related_count
    ]
    if not counts:
        return None
    items = ", ".join(
        t.t("report.coverage_item", count=count, project=code) for code, count in counts
    )
    return t.t("report.coverage", items=items)


def _shorten(text: str) -> str:
    if len(text) <= SHORT_LABEL_MAX_CHARS:
        return text
    return text[: SHORT_LABEL_MAX_CHARS - 1].rstrip() + ELLIPSIS
