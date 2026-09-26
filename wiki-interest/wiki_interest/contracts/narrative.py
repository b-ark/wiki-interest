"""``facts.json`` and ``narrative.json``: what the code observed, and the text the agent writes.

The code measures and observes; the agent explains. ``facts.json`` holds the observations
(true statements about the data, each with an id, a weight and the numbers it quotes) and the
rules for writing. ``narrative.json`` is the agent's text: a story of a few
paragraphs, what it means for the user's decision, how to check it outside Wikipedia, and the
limits. Every paragraph lists the observations it relies on (``uses``), so the code can check
the text against exactly what it cites before it goes into the report.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from wiki_interest.contracts.summary import ObservationOut

__all__ = [
    "Facts",
    "FollowUpFact",
    "Narrative",
    "NarrativeProblem",
    "Paragraph",
]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FollowUpFact(_Model):
    """A next step the user can ask for, and what it changes in ``request.json``.

    ``cached``: the data are already fetched, so the rerun is instant; otherwise it fetches
    new data (a minute or two).
    """

    id: str
    what: str
    change: str
    cached: bool


class Paragraph(_Model):
    """A paragraph of the agent's text and the observations it relies on.

    Attributes:
        text: The paragraph, in the report language.
        uses: Ids of ``facts.observations`` the paragraph explains; its numbers must come
            from these observations.
    """

    text: str
    uses: list[str] = Field(default_factory=list)


class Narrative(_Model):
    """The report text the agent writes (``narrative.json``).

    The chat answer is not part of it: the code composes it from these blocks, so the user
    reads exactly the text that was checked.

    Attributes:
        language: The language it is written in; must be the report language.
        topic: Which item was analysed, in one line of the report language ("Python, the
            programming language"); the chat answer opens with it. Empty: the code's line.
        headline: Not used: the code writes the headline from the window's verdicts, so the
            answer always matches them (v0.2). Kept so an older text still reads.
        story: Two to four paragraphs that explain what is happening, each citing the
            observations it relies on.
        meaning: What it means for the user's decision, built on the ``decision``
            observations that fit the question.
        check: Not used: the code writes the next check (v0.2). Kept so an older text
            still reads.
        limits: One line: what page views can and cannot say.
        ui: Interface labels of the report: ``facts.ui`` lists them in English to translate.
    """

    language: str
    topic: str = ""
    headline: str = ""
    story: list[Paragraph]
    meaning: Paragraph
    check: str = ""
    limits: str
    ui: dict[str, str] = Field(default_factory=dict)


class Facts(_Model):
    """Everything the agent needs to write the report text, and nothing it must compute.

    Attributes:
        language: The report language: the text is written in it.
        question: The question type: ``compare``, ``assess`` or ``rank``.
        audience_note: Context the user gave, if any.
        period: The analysed months of the report's charts and table (``2024-09 – 2026-08``);
            each observation names its own months.
        topics: Topic ids with the item analysed (``chess — Q718, strategy board game``).
        observations: What the data show, most important first per pair: the only source of
            the text's facts and numbers.
        follow_ups: Next steps the chat answer offers; the code adds them.
        rules: How the text is written and checked.
        example: A worked example on a made-up topic: observations and the narrative written
            from them. It shows the form only; none of its content applies.
        ui: Interface labels still to translate (``key: English template``); the narrative
            answers them in its own ``ui``. Empty when the language has a catalog or the
            session translated them already.
        report_pdf: Where the PDF is; the chat answer names it.
        choice_names: How the meaning may name the recommendation's choice (an edition's
            language adjective in each catalog language, its code, or a topic's label).

    The code's own text (the fallback) is not here: the agent wrote from it when it was, and
    retold the observations instead of explaining them (verified 2026-09-25 on six topics).
    """

    schema_version: Literal["3"] = "3"
    language: str
    question: str
    audience_note: str | None = None
    period: str
    topics: list[str]
    observations: list[ObservationOut]
    follow_ups: list[FollowUpFact] = Field(default_factory=list)
    rules: list[str]
    example: dict[str, Any] = Field(default_factory=dict)
    ui: dict[str, str] = Field(default_factory=dict)
    report_pdf: str | None = None
    choice_names: list[str] = Field(default_factory=list)


class NarrativeProblem(_Model):
    """One reason the text was rejected, addressed to the agent."""

    block: str
    message: str
    excerpt: str | None = None
