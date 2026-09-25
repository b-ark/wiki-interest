"""From a summary to ``facts.json``, the template text, and back with the agent's text.

The summary already holds every observation; this module lays them out for the agent with
the rules for writing, a worked example and the interface labels to translate; writes the
code's own text (the observations strung together: the report before the agent's text, and
the fallback), puts an accepted narrative into the summary so the renderers print it, and
composes the chat answer from the report text.
"""

# ruff: noqa: RUF001  -- the minus sign and narrow spaces are intentional.

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from wiki_interest.application.summary_builder import period_notes
from wiki_interest.contracts.narrative import Facts, FollowUpFact, Narrative, Paragraph
from wiki_interest.contracts.summary import AnalysisSummary, ObservationOut
from wiki_interest.i18n import Translator

__all__ = [
    "EXAMPLE",
    "LIMITS",
    "PARAGRAPH_PERCENTAGES",
    "RULES",
    "STORY_PARAGRAPHS",
    "apply_narrative",
    "build_facts",
    "compose_chat",
    "template_limits",
    "template_narrative",
]

_NARROW_NBSP = chr(0x202F)
_SPACED_UNIT = re.compile(r"(?<=\d)[ \u00a0](?=%)")
"""A space between a number and its percent sign: the PDF would break the line there."""
_FIVE_YEARS = 60
_TEMPLATE_PARAGRAPHS = 4
_TEMPLATE_STATEMENTS = 3
_TEMPLATE_DECISIONS = 3
_STORY_WEIGHTS = ("caution", "high")
_CHAT_FOLLOW_UPS = 3
"""How many next steps the chat answer offers."""
_BLANK_LINES = re.compile(r"\n{3,}")

LIMITS: Mapping[str, int] = {
    "topic": 240,
    "headline": 200,
    "story": 500,
    "story_total": 1400,
    "meaning": 450,
    "check": 300,
    "limits": 250,
}
"""Longest text of each block, in characters (a story paragraph each; the whole story)."""
STORY_PARAGRAPHS = (2, 4)
"""Fewest and most paragraphs of the story (one is allowed when little was observed)."""
PARAGRAPH_PERCENTAGES = 4
"""Most percentages in a paragraph: more is the observations translated, not explained."""

RULES: tuple[str, ...] = (
    "Write in the report language, for a founder who decides where to invest and does not "
    "know how the data were computed; use audience_note when given. Explain, do not list "
    "statistics.",
    f"headline: the answer to the user's question in one sentence, without numbers (at most "
    f"{LIMITS['headline']} characters).",
    f"story: {STORY_PARAGRAPHS[0]} to {STORY_PARAGRAPHS[1]} short paragraphs (at most "
    f"{LIMITS['story']} characters each, {LIMITS['story_total']} in all). Pick the "
    "observations that answer this question, starting from caution and high ones, and "
    "connect them into one story: why the numbers move, not only that they move. The "
    "observations are your notes, not text to translate: say what they mean together, in "
    "your own words. Leave the rest out. Each paragraph lists the ids of the observations it "
    "relies on in 'uses'.",
    f"meaning: what it means for the user's decision (at most {LIMITS['meaning']} "
    "characters), built from the decision observations that fit the question; cite them in "
    "'uses'.",
    f"check: one concrete way to check the conclusion outside Wikipedia, one sentence (at "
    f"most {LIMITS['check']} characters).",
    f"limits: one line (at most {LIMITS['limits']} characters): page views show curiosity, "
    "not willingness to pay; an edition is a language, not a country.",
    "Numbers: only those of the observations a paragraph cites (rounding is fine); never "
    "compute a new one (no ratios, 'N times', sums or differences). Prefer the words and "
    "counts given ('about half', 'about 560 times a month'); at most four percentages in a "
    "paragraph. The story gives two numbers the reader needs: how big the interest is (the "
    "views per million views of the size observation) and how the article moved against its "
    "whole edition (the edition's change and the article's, from the vs_edition observation).",
    "Name periods as the observations do ('in 2021', 'January–August 2026 against the same "
    "months of 2025'), never 'N years ago'. A change keeps the comparison it was made on, and "
    "a partial year stays partial, with its caution.",
    "Views are how often the article is opened ('the article is opened about 560 times a "
    "month'), never a number of people, never demand or a market.",
    "Every cause or guess comes from an observation and keeps its 'possibly' or 'probably'; "
    "add no causes of your own and no outside events.",
    "Name editions by their language ('the Polish Wikipedia'), never by a country.",
    "Cite every caution observation of an edition your text talks about.",
    "ui: every label of facts.ui translated into the report language, same keys, "
    "{placeholders} kept as they are; leave 'ui' empty only when facts.ui is empty.",
)

EXAMPLE: Mapping[str, object] = {
    "observations": [
        {
            "id": "size:beekeeping/nl",
            "weight": "high",
            "statement": "In the Dutch Wikipedia the article on beekeeping is opened about 2,400 "
            "times a month in January–August 2026: 5.1 views per million views of the edition "
            "(its attention share, the size of interest comparable across editions). In 2021 "
            "it was opened about 2,300 times a month: about the same as it was.",
        },
        {
            "id": "long_term:beekeeping/nl",
            "weight": "high",
            "statement": "Its share of the Dutch Wikipedia's reading has risen almost every "
            "year (4 of 4 year-on-year steps, 2021–2025); in 2025 it was about one and a half "
            "times what it was in 2021. A long, steady rise.",
        },
        {
            "id": "vs_edition:beekeeping/nl",
            "weight": "high",
            "statement": "In January–August 2026 (against the same months of 2025) the Dutch "
            "Wikipedia as a whole was read less (−9 %), yet beekeeping held up (+4 % views): "
            "its share rose +14 %. The topic gains attention against a shrinking Wikipedia.",
        },
        {
            "id": "season:beekeeping/nl",
            "weight": "medium",
            "statement": "Beekeeping in the Dutch Wikipedia has a yearly rhythm: strongest in "
            "April (+62 % against its usual level), weakest in December (−41 %).",
        },
        {
            "id": "decision:timing:beekeeping/nl",
            "weight": "decision",
            "statement": "Interest in beekeeping in the Dutch Wikipedia peaks every April: "
            "anything launched or promoted should be ready by March.",
        },
        {
            "id": "decision:verdict:beekeeping/nl",
            "weight": "decision",
            "statement": "Interest in beekeeping in the Dutch Wikipedia grows against the "
            "edition: Wikipedia supports investing.",
        },
    ],
    "narrative": {
        "language": "en",
        "topic": "Beekeeping, the keeping of honey bees",
        "headline": "Yes: interest in beekeeping in the Dutch Wikipedia is growing, slowly "
        "and steadily.",
        "story": [
            {
                "text": "In January–August 2026 the article is opened about 2,400 times a "
                "month, 5.1 views per million views of the Dutch Wikipedia, much as in 2021. "
                "That looks flat, but it hides a rise: against the same months of 2025 the "
                "Dutch Wikipedia as a whole was read 9 % less, while beekeeping gained 4 % "
                "views. "
                "As a share of everything read there, it got about one and a half times more "
                "attention in 2025 than in 2021, and it rose almost every year.",
                "uses": [
                    "size:beekeeping/nl",
                    "vs_edition:beekeeping/nl",
                    "long_term:beekeeping/nl",
                ],
            },
            {
                "text": "The interest also has a calendar: every April the article is read far "
                "above its usual level, and December is its quietest month.",
                "uses": ["season:beekeeping/nl"],
            },
        ],
        "meaning": {
            "text": "Wikipedia supports the idea: attention is growing, not fading. Plan to "
            "be ready by March, before the April peak.",
            "uses": ["decision:verdict:beekeeping/nl", "decision:timing:beekeeping/nl"],
        },
        "check": "Compare how often people search for beekeeping courses this year and last.",
        "limits": "Page views show curiosity, not willingness to pay; the Dutch Wikipedia is "
        "a language, not a country.",
        "ui": {
            "report.decision": "(each key of facts.ui with its label in the report language)",
            "chat.pdf": "(... keeping {path} as it is)",
        },
    },
}
"""A made-up topic, observations and the narrative written from them: the form, not content."""


def build_facts(summary: AnalysisSummary, *, ui: Mapping[str, str]) -> Facts:
    """Lay out a finished summary for the agent that writes the text.

    Args:
        summary: A summary with status ``ok``.
        ui: Interface labels still to translate, ``key: English template``.
    """
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
        observations=list(summary.observations),
        follow_ups=_follow_ups(summary),
        rules=list(RULES),
        example=dict(EXAMPLE),
        ui=dict(ui),
        report_pdf=summary.artifacts.report_pdf,
    )


def template_narrative(
    summary: AnalysisSummary, translator: Translator, *, ui: Mapping[str, str] | None = None
) -> Narrative:
    """The code's own text as a narrative: the fallback, and the report before the agent's.

    The story strings together the caution and high observations of each pair (then the
    comparisons across pairs), the meaning the decision observations. It is English: the
    observations are.

    Args:
        summary: A summary with status ``ok``.
        translator: The report-language translator.
        ui: Interface labels still to translate, ``key: English template``.
    """
    observations = summary.observations
    groups: dict[str | None, list[ObservationOut]] = {}
    for o in observations:
        if o.weight in _STORY_WEIGHTS:
            groups.setdefault(o.pair, []).append(o)
    story: list[Paragraph] = []
    room = LIMITS["story_total"]
    for chosen in groups.values():
        paragraph = _fitting(chosen, min(LIMITS["story"], room))
        if paragraph.text and len(paragraph.text) <= room:
            story.append(paragraph)
            room -= len(paragraph.text)
        if len(story) == _TEMPLATE_PARAGRAPHS:
            break
    decisions = _fitting(
        [o for o in observations if o.weight == "decision"][:_TEMPLATE_DECISIONS],
        LIMITS["meaning"],
    )
    decision = summary.decision
    fallback_meaning = (decision.summary or "") if decision else ""
    return Narrative(
        language=summary.request.report.language,
        topic=" ".join(_topic_lines(summary, translator)),
        headline=summary.verdict.headline,
        story=story or [Paragraph(text=line) for line in summary.happening],
        meaning=decisions if decisions.text else Paragraph(text=fallback_meaning),
        check=decision.next_step if decision else "",
        limits=template_limits(translator),
        ui=dict(ui or {}),
    )


def _fitting(observations: Sequence[ObservationOut], limit: int) -> Paragraph:
    """The first statements that fit ``limit`` and the cap on percentages, citing them.

    The template passes the checks the agent's text does.
    """
    chosen: list[ObservationOut] = []
    length = percentages = 0
    for o in observations[:_TEMPLATE_STATEMENTS]:
        count = sum(1 for q in o.numbers if q.percent)
        if chosen and (
            length + len(o.statement) + 1 > limit or percentages + count > PARAGRAPH_PERCENTAGES
        ):
            break
        chosen.append(o)
        length += len(o.statement) + 1
        percentages += count
    return Paragraph(text=" ".join(o.statement for o in chosen), uses=[o.id for o in chosen])


def template_limits(translator: Translator) -> str:
    """The limits line of the template text."""
    return translator.t("report.footer_caveats")


def compose_chat(
    summary: AnalysisSummary,
    limits: str,
    translator: Translator,
    previous: AnalysisSummary | None = None,
) -> str:
    """The answer the agent sends to the chat as it is, built from the report text.

    The agent's blocks are already checked and in the user's language; the code only lays
    them out and adds the item analysed, a few next steps and the path to the PDF, so the
    answer needs no second text and no second check. A label the agent left untranslated
    gives way to a form without words (``PDF: <path>``) or is left out, so the answer never
    switches to English.

    Args:
        summary: The summary as rendered, with the agent's text when it was accepted.
        limits: The limits line, the agent's or :func:`template_limits`.
        translator: The report-language translator, with the agent's interface labels.
        previous: The session's run before this one: a follow-up says what changed.
    """
    t = translator
    decision = summary.decision
    meaning = decision.summary if decision and decision.summary else ""
    heading = t.t("report.decision")
    if meaning and _translated(t, "report.decision"):
        meaning = f"**{heading}:** {meaning}"
    lines = [
        *([summary.topic_line] if summary.topic_line else _topic_lines(summary, t)),
        "",
        f"**{summary.verdict.headline}**",
        "",
        *_period_lines(summary, t),
        *_change_lines(summary, previous, t),
        "",
        *(line for paragraph in summary.happening for line in (paragraph, "")),
        meaning,
        decision.next_step if decision else "",
        "",
        f"_{limits}_" if limits else "",
        "",
        *_offer_lines(summary, t),
    ]
    if summary.artifacts.report_pdf:
        path = summary.artifacts.report_pdf
        pdf = t.t("chat.pdf", path=path)
        lines += ["", pdf if t.translates("chat.pdf") else f"PDF: {path}"]
    return _BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


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


def _translated(t: Translator, *keys: str) -> bool:
    """Whether every label read in the user's language.

    Lookups record their keys for the agent to translate, so callers look a label up first
    and ask this after: an untranslated label is still asked for on the next run.
    """
    return all(t.translates(key) for key in keys)


def _topic_lines(summary: AnalysisSummary, t: Translator) -> list[str]:
    """Which item was analysed: the reader must see it was the language, not the snake."""
    lines: list[str] = []
    for topic in summary.resolution:
        if topic.qid is None:
            continue
        label = topic.label or topic.query
        description = (
            t.t("gap.entity_description", description=topic.description)
            if topic.description
            else ""
        )
        line = t.t("summary.topic_line", label=label, description=description, qid=topic.qid)
        if not _translated(t, "summary.topic_line", "gap.entity_description"):
            tail = f" — {topic.description}" if topic.description else ""
            line = f"«{label}»{tail} ({topic.qid})"
        lines.append(line)
    return lines


def _period_lines(summary: AnalysisSummary, t: Translator) -> list[str]:
    """Why the period differs from the one asked for: the agent's text may leave it out."""
    notes = period_notes(summary.request.period, summary.period, t)
    return [text for key, text in notes if _translated(t, key)]


def _change_lines(
    summary: AnalysisSummary, previous: AnalysisSummary | None, t: Translator
) -> list[str]:
    """What a follow-up changed against the session's run before it, pair by pair.

    The agent sends the chat answer as it is and cannot add the comparison itself, so the
    code states it: the attention share and its change before and after, and the editions
    the follow-up added. Nothing when the runs share no topic.
    """
    if previous is None:
        return []
    if not {a.topic_id for a in summary.assessments} & {a.topic_id for a in previous.assessments}:
        return []
    before = {(a.topic_id, a.project): a for a in previous.assessments}
    items: list[str] = []
    for now in summary.assessments:
        then = before.get((now.topic_id, now.project))
        if not now.measured or then is None or not then.measured:
            continue
        parts: list[str] = []
        if now.per_million is not None and then.per_million is not None:
            parts.append(
                t.t(
                    "chat.previous_share",
                    before=t.number(then.per_million, 1),
                    after=t.number(now.per_million, 1),
                )
            )
        if now.change is not None and then.change is not None:
            parts.append(
                t.t(
                    "chat.previous_change",
                    before=t.percent(then.change, 0, signed=True),
                    after=t.percent(now.change, 0, signed=True),
                )
            )
        if parts:
            items.append(f"{now.label}: {', '.join(parts)}")
    added = [a.label for a in summary.assessments if (a.topic_id, a.project) not in before]
    if not items and not added:
        return []
    period = f"{previous.period.start:%Y-%m} – {previous.period.end:%Y-%m}"
    line = t.t("chat.previous", period=period)
    if items:
        line += " " + "; ".join(items) + "."
    if added:
        line += " " + t.t("chat.previous_added", projects=", ".join(added))
    keys = ["chat.previous", "chat.previous_share", "chat.previous_change"]
    keys += ["chat.previous_added"] if added else []
    return [line] if _translated(t, *keys) else []


def _offer_lines(summary: AnalysisSummary, t: Translator) -> list[str]:
    """A few next steps, the instant ones marked, each only when its label is translated.

    A follow-up run offers steps the first did not; their labels are new, and one left in
    English must not take the translated ones with it.
    """
    offers = _follow_ups(summary)[:_CHAT_FOLLOW_UPS]
    if not offers:
        return []
    # Every label is looked up before it is judged: the lookup asks for its translation.
    heading = t.t("chat.follow_ups")
    instant = f" ({t.t('chat.instant')})"
    if not _translated(t, "chat.instant"):
        instant = ""
    items = [(f"chat.follow_up.{f.id}", f.cached) for f in offers]
    lines = [(key, f"- {t.t(key)}{instant if cached else ''}") for key, cached in items]
    shown = [line for key, line in lines if _translated(t, key)]
    return [heading, *shown] if shown and _translated(t, "chat.follow_ups") else []


def _typeset(narrative: Narrative) -> Narrative:
    """Keep "-22 %" on one line in the reports, as the template text does."""

    def fix(text: str) -> str:
        return _SPACED_UNIT.sub(_NARROW_NBSP, text)

    return narrative.model_copy(
        update={
            "headline": fix(narrative.headline),
            "story": [p.model_copy(update={"text": fix(p.text)}) for p in narrative.story],
            "meaning": narrative.meaning.model_copy(update={"text": fix(narrative.meaning.text)}),
            "check": fix(narrative.check),
            "limits": fix(narrative.limits),
        }
    )


def apply_narrative(
    summary: AnalysisSummary, narrative: Narrative, *, source: str = "agent"
) -> AnalysisSummary:
    """The summary with ``narrative`` as its report text.

    The story takes the place of "what happened", the meaning and the check that of the
    decision block; the per-pair robustness lines go (the story covers them). The chat answer
    is composed when the summary is rendered.

    Args:
        summary: The summary to update.
        narrative: The text: the agent's, accepted, or the template.
        source: ``agent`` or ``template``.
    """
    narrative = _typeset(narrative)
    assessments = [a.model_copy(update={"robustness_line": None}) for a in summary.assessments]
    decision = summary.decision
    if decision is not None:
        decision = decision.model_copy(
            update={
                "summary": narrative.meaning.text or None,
                "lines": [],
                "next_step": narrative.check,
            }
        )
    return summary.model_copy(
        update={
            "verdict": summary.verdict.model_copy(update={"headline": narrative.headline}),
            "happening": [p.text for p in narrative.story],
            "cited": list(
                dict.fromkeys(oid for p in (*narrative.story, narrative.meaning) for oid in p.uses)
            ),
            "assessments": assessments,
            "decision": decision,
            "narrative_source": source,
            "topic_line": (narrative.topic.strip() or None) if source == "agent" else None,
        }
    )
