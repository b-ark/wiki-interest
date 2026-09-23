"""From a summary to ``facts.json``, the template text, and back with the agent's text.

The summary already holds every number and state; this module lays them out for the agent
(each number with its metric, window and display form), writes the code's own text as a
``narrative.template.json`` the agent can reuse (and the report falls back to), and puts an
accepted narrative into the summary so the renderers print it.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from wiki_interest.contracts.narrative import (
    AnomalyFact,
    BlockRule,
    CaveatFact,
    Facts,
    FindingFact,
    FollowUpFact,
    MetricFact,
    MetricId,
    Narrative,
    NumberFact,
    PairFacts,
    PairText,
    SeasonFact,
)
from wiki_interest.contracts.summary import AnalysisSummary, AssessmentOut, DecisionOut
from wiki_interest.i18n import Translator

__all__ = [
    "BLOCKS",
    "RULES",
    "apply_narrative",
    "build_facts",
    "pair_id",
    "template_narrative",
]

_NARROW_NBSP = chr(0x202F)
_SPACED_UNIT = re.compile(r"(?<=\d)[ \u00a0](?=%)")
"""A space between a number and its percent sign: the PDF would break the line there."""
_DIGITS = 4
"""Values are rounded for reading; the display form carries what the report shows."""
_FIVE_YEARS = 60
_SMALL_CHANGE = 0.1
_CONFIRMATION = {
    "confirmed": "confirmed",
    "mixed": "mixed",
    "reversing": "contradicts",
    "unknown": "insufficient",
}
"""Whether the last months confirm the trend, in the words ``facts.json`` uses."""
_METRIC_IDS: Mapping[str, MetricId] = {
    "article_views": "article_views",
    "attention_share": "attention_share",
    "edition_traffic": "edition_traffic",
}
"""Changes below 10 % are shown with one decimal, as the template text does."""

METRICS: tuple[MetricFact, ...] = (
    MetricFact(
        id="attention_share",
        name="attention share",
        definition=(
            "article views per 1 million views of the whole edition: the size of interest, "
            "comparable across editions of different size"
        ),
    ),
    MetricFact(
        id="article_views",
        name="article views",
        definition="monthly views of the topic's main article (with its redirects)",
    ),
    MetricFact(
        id="edition_traffic",
        name="edition traffic",
        definition="monthly views of the whole language edition of Wikipedia",
    ),
)

BLOCKS: tuple[BlockRule, ...] = (
    BlockRule(
        name="headline",
        rule=(
            "The answer in one sentence, without numbers: which audience, and where its "
            "attention share is heading. Follows the states; never contradicts them."
        ),
        max_chars=200,
    ),
    BlockRule(
        name="happening",
        rule=(
            "What happened, two to four sentences: the size of interest (attention share), "
            "its change, and article views against edition traffic. Every number with its "
            "metric and its window."
        ),
        max_items=4,
        max_chars=320,
    ),
    BlockRule(
        name="robustness",
        rule=(
            "One entry per measured pair ({'pair': pairs[].id, 'text': ...}), the text "
            "starting with the pair's label: do the recent months confirm the long-term "
            "direction? Follow states.robustness and quote the recent_* numbers; when it is "
            "unknown, say it cannot be judged and why."
        ),
        max_items=99,
        max_chars=400,
    ),
    BlockRule(
        name="decision",
        rule=(
            "What it means for the decision: the conclusion first (conclusion.key, "
            "candidate), then at most one line per group of audiences with the same outcome."
        ),
        max_items=6,
        max_chars=400,
    ),
    BlockRule(
        name="next_step",
        rule=(
            "The next step in one sentence, naming examples of independent sources: Google "
            "Trends, search volume, a small ad test."
        ),
        max_chars=300,
    ),
    BlockRule(
        name="chat_answer",
        rule=(
            "Your reply in the chat: which item was analysed; the conclusion (headline, "
            "what happened, robustness, decision and next step) with the path to report_pdf; "
            "the assumptions (every caveat of caveats[]); what could change the conclusion "
            "(recent_confirmation, months that stand out, data_quality); then three to five "
            "next steps from follow_ups, saying which are instant (cached). Short paragraphs "
            "or bullets, no tables."
        ),
        max_chars=3500,
    ),
)

RULES: tuple[str, ...] = (
    "Write in the report language, for the user; use audience_note when given.",
    "Copy numbers from numbers[].display (rounding is fine); never compute new ones: no "
    "ratios, differences, sums, shares of totals or '1 in N'.",
    "Every sentence with a number names its metric with your glossary term (a list item may "
    "take it from the line that introduces the list, ending with ':'); give each metric one "
    "term in glossary and keep to it. A rejection quotes the words to write: use them.",
    "Name editions by their label (uk.wikipedia).",
    "An edition without an article has 'no article', never 'no interest'.",
    "Wikipedia views measure attention and curiosity, not demand, a market or willingness "
    "to pay: never call them demand.",
    "Never call views demand in headline, happening or robustness; the decision and the next "
    "step may speak of checking demand elsewhere.",
    "No statistical jargon (significant, p-value): say steady, mixed, turning, cannot be judged.",
    "A month in pairs[].anomalies with in_change is named with its month, its multiple and "
    "the 12-month change of the attention share without it, each with its metric; say "
    "possible_bot as 'possibly automated traffic'.",
    "Mention a season only when season.shown, naming season.period; when the user asked about "
    "timing and it is not shown, say why (season.reason).",
    "Follow the states: a declining momentum is a decline even for the largest audience.",
)


def pair_id(assessment: AssessmentOut) -> str:
    """``<topic>/<language>``: how facts and narrative refer to one (topic, edition)."""
    return f"{assessment.topic_id}/{assessment.project.split('.')[0]}"


def build_facts(
    summary: AnalysisSummary,
    translator: Translator,
    *,
    ui_strings: Mapping[str, str] | None = None,
    template_file: str,
) -> Facts:
    """Lay out a finished summary for the agent that writes the text.

    Args:
        summary: A summary with status ``ok``.
        translator: The report-language translator (formats the display values).
        ui_strings: Interface labels still to be translated, ``key: English template``.
        template_file: Path of the template narrative, for the agent to read.
    """
    english = Translator("en")
    measured = [a for a in summary.assessments if a.measured]
    decision = summary.decision
    return Facts(
        language=summary.request.report.language,
        question=summary.request.question_type,
        audience_note=summary.request.report.audience_note,
        period=f"{summary.period.start:%Y-%m} – {summary.period.end:%Y-%m}",
        topics=[
            f"{r.topic_id}: {r.label or r.query} ({r.qid or 'no item'})"
            + (f", {r.description}" if r.description else "")
            for r in summary.resolution
        ],
        metrics=list(METRICS),
        pairs=[_pair(summary, a, translator, english) for a in summary.assessments],
        conclusion={
            "key": decision.conclusion if decision else "none",
            "candidate": decision.candidate if decision else None,
        },
        findings=[
            FindingFact(
                kind=f.kind,
                pair=f"{f.topic_id}/{f.project.split('.')[0]}"
                if f.topic_id and f.project
                else None,
                text=f.text,
            )
            for f in summary.findings
        ],
        data_note=list(summary.data_note),
        limitations=list(summary.limitations),
        caveats=_caveats(summary.assessments, measured_count=len(measured)),
        follow_ups=_follow_ups(summary),
        blocks=list(BLOCKS),
        rules=list(RULES),
        ui_strings=dict(ui_strings or {}),
        template_file=template_file,
        report_pdf=summary.artifacts.report_pdf,
    )


def _pair(
    summary: AnalysisSummary, a: AssessmentOut, t: Translator, english: Translator
) -> PairFacts:
    normalised = summary.request.normalization == "per_million"
    pid = pair_id(a)
    months = next(
        (m.periods for m in summary.metrics if (m.topic_id, m.project) == (a.topic_id, a.project)),
        None,
    )
    recent = (
        f"last {a.recent_months} months vs the same months a year earlier"
        if a.recent_months
        else ""
    )
    score = next(
        (r.score for r in summary.ranking if (r.topic_id, r.project) == (a.topic_id, a.project)),
        None,
    )
    relation = english.t(f"basis.{a.relation_basis}") if a.relation_basis else ""
    basis = english.t(f"basis.{a.basis}") if a.basis else ""
    main: MetricId = "attention_share" if normalised else "article_views"
    candidates: list[tuple[str, MetricId | None, str, float | None, str]] = [
        ("per_million", "attention_share", "period average", a.per_million, "per_million"),
        ("views_avg", "article_views", "period average, per month", a.views_avg, "views"),
        ("change", main, basis, a.change, "fraction"),
        ("article_change", "article_views", relation, a.article_change, "fraction"),
        ("edition_change", "edition_traffic", relation, a.edition_change, "fraction"),
        ("share_change", "attention_share", relation, a.share_change, "fraction"),
        ("recent_article", "article_views", recent, a.recent_article, "fraction"),
        ("recent_edition", "edition_traffic", recent, a.recent_edition, "fraction"),
        ("recent_share", "attention_share", recent, a.recent_shift, "fraction"),
        ("recent_months", None, "length of the recent window", a.recent_months, "count"),
        ("months", None, "months of data", months, "count"),
        ("rank_score", None, "ranking score, 0 to 1", score, "score"),
    ]
    numbers = [
        NumberFact(
            id=f"{pid}.{name}",
            metric=metric,
            window=window,
            value=round(value, _DIGITS),
            unit=unit,  # type: ignore[arg-type]
            display=_display(t, value, unit),
        )
        for name, metric, window, value, unit in candidates
        if value is not None
    ]
    numbers += _month_numbers(a, pid, main, t)
    numbers += _season_numbers(a, pid, t)
    states = {
        "size": a.size,
        "momentum": a.momentum,
        "vs_edition": a.relation,
        "recent_confirmation": _CONFIRMATION[str(a.robustness)],
        "outcome": a.outcome,
        "data_quality": a.data_quality.level if a.data_quality else None,
        "divergence": a.divergence,
    }
    reading = [line for line in (a.decision, a.robustness_line, a.edition_line) if line]
    return PairFacts(
        id=pid,
        topic=a.topic_id,
        project=a.project,
        label=a.label,
        measured=a.measured,
        states={k: str(v) for k, v in states.items() if v is not None},
        reading=reading,
        numbers=numbers,
        data_quality_reasons=list(a.data_quality.reasons) if a.data_quality else [],
        anomalies=[
            AnomalyFact(
                month=m.month,
                metrics=sorted(m.multiples),
                nature=m.nature,
                in_change=m.in_change,
                in_recent=m.in_recent,
            )
            for m in a.months
        ],
        season=_season(a),
    )


def _month_numbers(a: AssessmentOut, pid: str, main: MetricId, t: Translator) -> list[NumberFact]:
    out: list[NumberFact] = []
    for month in a.months:
        for metric, multiple in sorted(month.multiples.items()):
            out.append(
                NumberFact(
                    id=f"{pid}.month.{month.month}.{metric}",
                    metric=_METRIC_IDS.get(metric),
                    window=f"{month.month} against the months around it",
                    value=round(multiple, 2),
                    unit="multiple",
                    display=_display(t, multiple, "multiple"),
                )
            )
        if month.change_without is not None:
            out.append(
                NumberFact(
                    id=f"{pid}.month.{month.month}.change_without",
                    metric=main,
                    window=f"last 12 months vs the 12 before, without {month.month} and its "
                    "twin a year off",
                    value=round(month.change_without, _DIGITS),
                    unit="fraction",
                    display=_display(t, month.change_without, "fraction"),
                )
            )
    return out


def _season_numbers(a: AssessmentOut, pid: str, t: Translator) -> list[NumberFact]:
    season = a.season
    if season is None or not season.shown:
        return []
    window = f"calendar month against the usual level, {season.start} – {season.end}"
    return [
        NumberFact(
            id=f"{pid}.season.{name}",
            metric="article_views",
            window=window,
            value=round(value, _DIGITS),
            unit="fraction",
            display=_display(t, value, "fraction"),
        )
        for name, value in (("peak", season.peak), ("trough", season.trough))
        if value is not None
    ]


def _season(a: AssessmentOut) -> SeasonFact | None:
    season = a.season
    if season is None:
        return None
    period = f"{season.start} – {season.end}" if season.start and season.end else None
    return SeasonFact(
        shown=season.shown,
        reason=season.reason,
        period=period,
        years=season.years,
        peak_month=season.peak_month,
        trough_month=season.trough_month,
    )


def _display(t: Translator, value: float, unit: str) -> str:
    if unit == "fraction":
        return t.percent(value, 1 if abs(value) < _SMALL_CHANGE else 0, signed=True)
    if unit == "per_million":
        return t.number(value, 1)
    if unit == "score":
        return t.number(value, 2)
    if unit == "multiple":
        return "×" + t.number(value, 1)
    return t.number(value)


def _follow_ups(summary: AnalysisSummary) -> list[FollowUpFact]:
    """Refinements the user may want next; ``cached`` ones reuse the fetched data."""
    request = summary.request
    out: list[FollowUpFact] = []
    if request.report.seasonality != "show":
        out.append(
            FollowUpFact(
                id="seasons",
                what="which months of the year are strongest (the season on the whole history)",
                change='report.seasonality: "show"',
                cached=True,
            )
        )
    if summary.period.months < _FIVE_YEARS:
        out.append(
            FollowUpFact(
                id="longer_period",
                what="a longer period, up to 2015-07",
                change="period.start earlier",
                cached=False,
            )
        )
    out.append(
        FollowUpFact(
            id="add_editions",
            what="more language editions to compare",
            change="append to projects",
            cached=False,
        )
    )
    if request.normalization == "per_million":
        out.append(
            FollowUpFact(
                id="raw_views",
                what="raw article views instead of the attention share",
                change='normalization: "absolute"',
                cached=True,
            )
        )
    if not request.report.appendix:
        out.append(
            FollowUpFact(
                id="method_page",
                what="a second PDF page with the method and data checks",
                change="report.appendix: true",
                cached=True,
            )
        )
    return out


def _caveats(assessments: Sequence[AssessmentOut], *, measured_count: int) -> list[CaveatFact]:
    out = [
        CaveatFact(
            id="curiosity_not_demand",
            meaning=(
                "Wikipedia views measure attention and curiosity, not demand or willingness "
                "to pay; confirm with an independent source before investing."
            ),
        ),
        CaveatFact(
            id="language_not_country",
            meaning=(
                "A language edition is not a country: readers of uk.wikipedia live in many "
                "countries, and people of one country read several editions."
            ),
        ),
    ]
    if measured_count > 1:
        out.append(
            CaveatFact(
                id="coverage_differs",
                meaning=(
                    "Editions cover a topic differently (article length, related articles), "
                    "which shifts views apart from interest."
                ),
            )
        )
    for a in assessments:
        # One caveat per pair for all its months: a separate id per month was the most
        # frequent reason a text was rejected (verified 2026-09-23 on the evals).
        months = [m for m in a.months if m.in_change and m.nature != "edition"]
        if months:
            listed = ", ".join(f"{m.month} ({m.nature})" for m in months)
            out.append(
                CaveatFact(
                    id=f"months:{pair_id(a)}",
                    meaning=(
                        f"In {a.label}, {listed} stand{'s' if len(months) == 1 else ''} out and "
                        "lie in the 12-month comparison: name them and the change without them."
                    ),
                    pair=a.label,
                )
            )
        if a.outcome == "no_article":
            meaning = f"{a.label} has no article on the topic: no article, not no interest."
        elif a.outcome == "substitute":
            meaning = f"{a.label} is measured through a substitute article; name it every time."
        elif a.outcome == "low_trust":
            meaning = f"The data for {a.label} are too weak for a conclusion."
        else:
            continue
        out.append(CaveatFact(id=f"{a.outcome}:{pair_id(a)}", meaning=meaning, pair=a.label))
    return out


def template_narrative(summary: AnalysisSummary, translator: Translator) -> Narrative:
    """The code's own text as a narrative: the fallback, and a reference for the agent."""
    decision = summary.decision
    decision_lines = _decision_lines(decision, summary.assessments)
    robustness = [
        PairText(pair=pair_id(a), text=a.robustness_line)
        for a in summary.assessments
        if a.measured and a.robustness_line
    ]
    next_step = decision.next_step if decision else ""
    caveats = [*summary.limitations, *summary.general_limitations]
    chat = [
        *_topic_lines(summary, translator),
        "",
        f"**{summary.verdict.headline}**",
        "",
        *(f"- {line}" for line in summary.happening),
        "",
        *(f"- {r.text}" for r in robustness),
        "",
        *decision_lines,
        next_step,
        "",
        *(f"- {line}" for line in caveats),
    ]
    if summary.artifacts.report_pdf:
        chat += ["", f"PDF: {summary.artifacts.report_pdf}"]
    measured = sum(1 for a in summary.assessments if a.measured)
    return Narrative(
        language=summary.request.report.language,
        glossary={
            "attention_share": translator.t("metric.attention_share").lower(),
            "article_views": translator.t("metric.article_views").lower(),
            "edition_traffic": translator.t("metric.edition_views").lower(),
        },
        headline=summary.verdict.headline,
        happening=list(summary.happening),
        robustness=robustness,
        decision=decision_lines,
        next_step=next_step,
        chat_answer="\n".join(chat).strip(),
        # Anomalous months are the agent's to describe: the template does not name them.
        covered_caveats=[
            c.id
            for c in _caveats(summary.assessments, measured_count=measured)
            if not c.id.startswith("months:")
        ],
    )


def _topic_lines(summary: AnalysisSummary, t: Translator) -> list[str]:
    """Which item was analysed: the reader must see it was the language, not the snake."""
    return [
        t.t(
            "summary.topic_line",
            label=topic.label or topic.query,
            description=(
                t.t("gap.entity_description", description=topic.description)
                if topic.description
                else ""
            ),
            qid=topic.qid,
        )
        for topic in summary.resolution
        if topic.qid is not None
    ]


def _decision_lines(
    decision: DecisionOut | None, assessments: Sequence[AssessmentOut]
) -> list[str]:
    if decision is None:
        return []
    lines = [decision.summary] if decision.summary else []
    lines += decision.lines
    if not lines:  # one audience: its outcome is the decision
        lines = [a.decision for a in assessments[:1]]
    return lines


def _typeset(narrative: Narrative) -> Narrative:
    """Keep "-22 %" on one line in the reports, as the template text does."""

    def fix(text: str) -> str:
        return _SPACED_UNIT.sub(_NARROW_NBSP, text)

    return narrative.model_copy(
        update={
            "headline": fix(narrative.headline),
            "happening": [fix(line) for line in narrative.happening],
            "robustness": [
                r.model_copy(update={"text": fix(r.text)}) for r in narrative.robustness
            ],
            "decision": [fix(line) for line in narrative.decision],
            "next_step": fix(narrative.next_step),
        }
    )


def apply_narrative(summary: AnalysisSummary, narrative: Narrative) -> AnalysisSummary:
    """The summary with the agent's text in place of the template text.

    The first decision line becomes the conclusion, the rest the per-audience lines; the
    robustness text replaces each pair's line.
    """
    narrative = _typeset(narrative)
    by_pair = {r.pair: r.text for r in narrative.robustness}
    assessments = [
        a.model_copy(update={"robustness_line": by_pair.get(pair_id(a), a.robustness_line)})
        for a in summary.assessments
    ]
    decision = summary.decision
    if decision is not None:
        decision = decision.model_copy(
            update={
                "summary": narrative.decision[0] if narrative.decision else None,
                "lines": list(narrative.decision[1:]),
                "next_step": narrative.next_step,
            }
        )
    return summary.model_copy(
        update={
            "verdict": summary.verdict.model_copy(update={"headline": narrative.headline}),
            "happening": list(narrative.happening),
            "assessments": assessments,
            "decision": decision,
            "narrative_source": "agent",
            "chat_answer": narrative.chat_answer,
        }
    )
