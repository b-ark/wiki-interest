"""``facts.json`` and ``narrative.json``: the numbers the code found, the text the agent writes.

The code measures; the agent writes the analysis in the user's language. ``facts.json``
holds everything the text may say (states, numbers with their metric and window, the
caveats it must carry) and the rules for writing it. ``narrative.json`` is the agent's text;
the code checks it against the facts before it goes into the report.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "BlockRule",
    "CaveatFact",
    "Facts",
    "FindingFact",
    "MetricFact",
    "Narrative",
    "NarrativeProblem",
    "NumberFact",
    "PairFacts",
    "PairText",
]

MetricId = Literal["attention_share", "article_views", "edition_traffic"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class MetricFact(_Model):
    """One of the three metrics, in English: what the text must call it and what it means."""

    id: MetricId
    name: str
    definition: str


class NumberFact(_Model):
    """A number the text may quote.

    Attributes:
        id: Stable identifier (``astronomy/uk.share_change``).
        metric: Which metric it measures; ``None`` for counts (months of data).
        window: Which months it covers, in English.
        value: The raw value; changes are fractions (``-0.195``).
        unit: ``fraction`` (write it as a percentage), ``per_million``, ``views``, ``score``
            (ranking, 0 to 1) or ``count``.
        display: The value as the report writes it, in the report language: copy this.
    """

    id: str
    metric: MetricId | None
    window: str
    value: float
    unit: Literal["fraction", "per_million", "views", "score", "count"]
    display: str


class PairFacts(_Model):
    """One topic in one edition: its states and numbers.

    Attributes:
        id: Identifier ``<topic>/<language>``, used to key the robustness text.
        label: How the report names the pair (``uk.wikipedia``); the robustness text for the
            pair must contain it.
        measured: Whether the edition has an article to measure.
        states: The code's reading, as enum values: ``size`` (largest/similar/smaller),
            ``momentum`` (growing/flat/declining/unknown), ``vs_edition``
            (gaining/in_line/losing), ``robustness`` (confirmed/mixed/reversing/unknown),
            ``outcome``, ``data_quality`` (high/medium/low).
        reading: The same states in the report language, as the template text puts them.
        numbers: What the text may quote about this pair.
    """

    id: str
    topic: str
    project: str
    label: str
    measured: bool
    states: dict[str, str] = Field(default_factory=dict)
    reading: list[str] = Field(default_factory=list)
    numbers: list[NumberFact] = Field(default_factory=list)


class FindingFact(_Model):
    """A further fact the analysis found (a level shift, a burst, a season)."""

    kind: str
    pair: str | None
    text: str
    """In the report language; the numbers in it may be quoted."""


class CaveatFact(_Model):
    """A caveat the chat answer must carry; ``pair`` must then be named in it."""

    id: str
    meaning: str
    pair: str | None = None


class BlockRule(_Model):
    """How one block of ``narrative.json`` is written and checked."""

    name: str
    rule: str
    max_items: int = 1
    max_chars: int


class Facts(_Model):
    """Everything the agent needs to write the report text, and nothing it must compute.

    Attributes:
        language: The report language: the text is written in it.
        question: The question type: ``compare``, ``assess`` or ``rank``.
        audience_note: Context the user gave, if any.
        period: The analysed months (``2024-09 – 2026-08``).
        topics: Topic ids with the item analysed (``chess — Q718, strategy board game``).
        metrics: The three metrics in English.
        pairs: One entry per (topic, edition).
        conclusion: The overall conclusion key and the audience it names.
        findings: Further facts worth mentioning.
        data_note: The state of the data, in the report language.
        limitations: Caveats specific to this run, in the report language.
        caveats: What the chat answer must mention.
        blocks: The blocks of ``narrative.json`` with their rules.
        rules: Writing rules that apply to every block.
        ui_strings: Interface labels to translate (``key: English template``); empty when the
            report language has a catalog. Keep ``{placeholders}`` as they are.
        template_file: The code's own text in the report language (``narrative.template.json``):
            a reference to reuse or rewrite, and the fallback.
        report_pdf: Where the PDF is; the chat answer names it.
    """

    schema_version: Literal["1"] = "1"
    language: str
    question: str
    audience_note: str | None = None
    period: str
    topics: list[str]
    metrics: list[MetricFact]
    pairs: list[PairFacts]
    conclusion: dict[str, str | None]
    findings: list[FindingFact] = Field(default_factory=list)
    data_note: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    caveats: list[CaveatFact]
    blocks: list[BlockRule]
    rules: list[str]
    ui_strings: dict[str, str] = Field(default_factory=dict)
    template_file: str
    report_pdf: str | None = None


class PairText(_Model):
    """The robustness text of one pair."""

    pair: str
    text: str


class Narrative(_Model):
    """The report text the agent writes (``narrative.json``).

    Attributes:
        language: The language it is written in; must be the report language.
        glossary: The agent's term for each metric (``attention_share: "доля внимания"``);
            every sentence with a number names its metric with one of these terms.
        headline: The answer in one sentence, without numbers.
        happening: What happened: two to four sentences with the numbers.
        robustness: For every measured pair, whether the recent months confirm the trend.
        decision: What it means for the decision: the conclusion first, then per-audience lines.
        next_step: The next step in one sentence, with examples of independent sources.
        chat_answer: The answer for the chat, with the caveats and the path to the PDF.
        covered_caveats: Ids of the caveats the chat answer carries.
        ui: Translations of ``facts.ui_strings``.
    """

    language: str
    glossary: dict[MetricId, str]
    headline: str
    happening: list[str]
    robustness: list[PairText] = Field(default_factory=list)
    decision: list[str]
    next_step: str
    chat_answer: str
    covered_caveats: list[str] = Field(default_factory=list)
    ui: dict[str, str] = Field(default_factory=dict)


class NarrativeProblem(_Model):
    """One reason the text was rejected, addressed to the agent."""

    block: str
    message: str
    excerpt: str | None = None
