"""Blocks of the answer that every document shows the same way.

``report.pdf`` and ``summary.md`` both lead with the same answer: three cards
(size of interest, its change, whether recent months confirm it), the topic against its
edition, what it means for the decision and the next step, and how robust the conclusion
is. The wording comes from the summary; this module only arranges it, so the documents
cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from wiki_interest.contracts.summary import AnalysisSummary, AssessmentOut
from wiki_interest.i18n import Translator

__all__ = [
    "GENERATED_AT_FORMAT",
    "decision_lines",
    "edition_basis",
    "edition_lines",
    "kpi_table",
    "markdown_table",
    "ordered_assessments",
    "period_text",
    "project_label",
    "question_line",
    "ranking_table",
    "report_title",
    "robustness_lines",
    "robustness_value",
    "window_line",
]

PERCENT_DECIMALS = 0
SCORE_DECIMALS = 2
RANGE_DASH = " – "
GENERATED_AT_FORMAT = "%Y-%m-%d %H:%M UTC"
MAX_TITLE_DESCRIPTION = 60
"""Longer Wikidata descriptions stay in the "Topic:" line and out of the title."""


def ordered_assessments(summary: AnalysisSummary) -> list[AssessmentOut]:
    """Audiences in reading order: by rank for a ranking, else as requested."""
    items = list(summary.assessments)
    if summary.ranking:
        rank = {(r.topic_id, r.project): r.rank for r in summary.ranking}
        items.sort(key=lambda a: rank.get((a.topic_id, a.project), len(rank) + 1))
    return items


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
    """The code's recommendation, the text that explains it, and the next check.

    The recommendation comes first so a page tightened to one line keeps it.
    """
    decision = summary.decision
    if decision is None:
        return []
    meaning = [decision.summary] if decision.summary else []
    return [*decision.lines, *meaning, decision.next_step]


# -- labels and tables shared by summary.md and the PDF ------------------------------


def report_title(summary: AnalysisSummary, t: Translator) -> str:
    """The user's title if given, else the topic's name, else the localised default.

    A single topic with a short Wikidata description carries it in the title ("Python — general-
    purpose programming language"), so the meaning analysed is stated where nobody skips it.
    """
    if summary.request.report.title:
        return summary.request.report.title
    names = [topic.label or topic.query for topic in summary.resolution]
    if not names:
        return t.t("report.title_default")
    if len(summary.resolution) == 1:
        description = summary.resolution[0].description
        if description and len(description) <= MAX_TITLE_DESCRIPTION:
            names = [f"{names[0]} — {description}"]
    title = t.t("report.title_topic", topic=", ".join(names))
    # Wikidata labels are lower case in many languages ("шахматы"); a title is not.
    return title[:1].upper() + title[1:]


def question_line(summary: AnalysisSummary, t: Translator) -> str:
    """One sentence restating the request, so the reader knows what was asked."""
    topics = ", ".join(topic.query for topic in summary.request.topics)
    projects = ", ".join(summary.request.projects)
    return t.t(f"question.{summary.request.question_type}", topics=topics, projects=projects)


def period_text(summary: AnalysisSummary) -> str:
    """The period as ``start – end`` (en dash), e.g. ``2024-09`` to ``2026-08``."""
    return f"{summary.period.start:%Y-%m}{RANGE_DASH}{summary.period.end:%Y-%m}"


def window_line(summary: AnalysisSummary, t: Translator) -> str:
    """``Analysis period: 2024-09 – 2026-08 · Context on the charts: from 2021``.

    The context part only when the charts show history before the window.
    """
    window = summary.analysis_window or summary.period
    line = t.t("report.analysis_window", start=f"{window.start:%Y-%m}", end=f"{window.end:%Y-%m}")
    context = summary.context_range
    if context is not None and context.start < window.start:
        line += " · " + t.t("report.context", year=context.start.year)
    return line


def markdown_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Render a GitHub-flavoured Markdown table; pipes inside cells are escaped."""
    escaped = [[cell.replace("|", "\\|") for cell in row] for row in rows]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(" --- " for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(row) + " |" for row in escaped]
    return lines


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
            project_label(summary, row.topic_id, row.project),
            t.number(row.score, SCORE_DECIMALS),
            t.label("profile", row.profile),
            t.label("level", row.reliability),
            row.rationale,
        ]
        for row in sorted(summary.ranking, key=lambda r: r.rank)
    ]
    return markdown_table(headers, rows)


def project_label(summary: AnalysisSummary, topic_id: str, project: str) -> str:
    """Edition as shown to readers: ``pl.wikipedia (Post)`` when a substitute was measured.

    The edition code alone would present the substitute's numbers as the topic's own.
    """
    for topic in summary.resolution:
        if topic.topic_id != topic_id:
            continue
        for bundle in topic.bundles:
            if bundle.project == project and bundle.substitute_kind and bundle.articles:
                return f"{project} ({bundle.articles[0].title})"
    return project
