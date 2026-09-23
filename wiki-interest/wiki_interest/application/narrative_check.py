"""Checks the agent's text against the facts before it goes into the report.

The agent writes in any language, so the checks rely on what does not depend on it: the
numbers (each must be one the code computed), the metric terms the agent declared in its
glossary (each sentence with a number must name its metric), labels of the editions, the
declared caveats, the shape and length of the blocks. Word lists (``demand`` and its
translations) cover the languages the skill knows and are skipped for the rest.

Every problem is a sentence addressed to the agent: what is wrong, where, and what to do.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from string import Formatter

from wiki_interest.contracts.narrative import Facts, Narrative, NarrativeProblem
from wiki_interest.domain.prose_numbers import ProseNumber, extract_numbers, matches

__all__ = ["check_narrative"]

_LISTED_KEYS = 10
_ALWAYS_ALLOWED = (12.0, 24.0, 1_000_000.0)
"""Counts any text may use: the 12-month windows, "per 1 000 000 views"."""

_ANYWHERE: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b1\s+(?:in|of|из|з|із|na|z|ze|von|sur|de|su|op|av)\s+\d"),
        "Do not write '1 in N': quote the attention share per million as it is.",
    ),
    (re.compile(r"(?i)\bp\s*[=<≤]\s*0"), "No p-values: say whether the trend is steady."),
)
_JARGON: Mapping[str, str] = {
    "en": r"statistical(?:ly)? significan",
    "ru": r"статистическ\w* значим",
    "uk": r"статистичн\w* значущ",
    "pl": r"istotn\w* statystyczn|statystyczn\w* istotn",
    "cs": r"statisticky významn|statistick\w* významn",
    "de": r"statistisch signifikant",
}
_DEMAND: Mapping[str, str] = {
    "en": r"\bdemand",
    "ru": r"спрос",
    "uk": r"попит",
    "pl": r"popyt",
    "cs": r"poptávk",
    "de": r"nachfrage",
}
_DESCRIPTIVE = ("headline", "happening", "robustness")
"""Blocks that describe the Wikipedia data: "demand" there would call views demand. The
decision and the next step may speak of demand: "check the demand with Google Trends"."""
_SENTENCE_BREAK = re.compile(r"[.!?…]\s+")


@dataclass(frozen=True, slots=True)
class _Known:
    """A number the text may quote, on the scale prose writes it."""

    value: float
    percent: bool
    metric: str | None
    pair: str | None


def check_narrative(
    facts: Facts, narrative: Narrative, *, ui_cached: Mapping[str, str] | None = None
) -> list[NarrativeProblem]:
    """Every reason ``narrative`` cannot go into the report; empty when it can.

    Args:
        facts: What the code computed for this run.
        narrative: The agent's text.
        ui_cached: Interface translations kept from an earlier run of the session.
    """
    checker = _Checker(facts, narrative)
    checker.shape()
    checker.numbers_and_terms()
    checker.words()
    checker.caveats()
    checker.ui(ui_cached or {})
    return checker.problems


class _Checker:
    def __init__(self, facts: Facts, narrative: Narrative) -> None:
        self.facts = facts
        self.narrative = narrative
        self.problems: list[NarrativeProblem] = []
        self.rules = {b.name: b for b in facts.blocks}
        self.known = _known(facts)
        self.terms: dict[str, list[str]] = {
            metric.id: [
                metric.name,
                *([narrative.glossary[metric.id]] if metric.id in narrative.glossary else []),
            ]
            for metric in facts.metrics
        }

    def add(self, block: str, message: str, excerpt: str | None = None) -> None:
        self.problems.append(NarrativeProblem(block=block, message=message, excerpt=excerpt))

    # -- shape ------------------------------------------------------------------------------

    def shape(self) -> None:
        n = self.narrative
        if n.language != self.facts.language:
            self.add(
                "language",
                f"Write in '{self.facts.language}' (facts.language), not '{n.language}'.",
            )
        missing = [m.id for m in self.facts.metrics if not n.glossary.get(m.id, "").strip()]
        if missing:
            self.add("glossary", f"Give your term for every metric; missing: {', '.join(missing)}.")
        self.length("headline", [n.headline])
        if re.search(r"\d", n.headline):
            self.add("headline", "The headline has no numbers; they go in 'happening'.", n.headline)
        if len(list(_sentences(n.headline))) > 1:
            self.add("headline", "The headline is one sentence.", n.headline)
        self.length("happening", n.happening)
        self.length("decision", n.decision)
        self.length("next_step", [n.next_step])
        self.length("chat_answer", [n.chat_answer])
        self.robustness()

    def length(self, block: str, items: Sequence[str]) -> None:
        rule = self.rules.get(block)
        if rule is None:
            return
        if not [i for i in items if i.strip()]:
            self.add(block, f"'{block}' is empty.")
        if len(items) > rule.max_items:
            self.add(block, f"At most {rule.max_items} items in '{block}', got {len(items)}.")
        for item in items:
            if len(item) > rule.max_chars:
                self.add(
                    block, f"Shorten to {rule.max_chars} characters (now {len(item)}).", item[:80]
                )

    def robustness(self) -> None:
        measured = {p.id: p for p in self.facts.pairs if p.measured}
        given = [r.pair for r in self.narrative.robustness]
        for pid in measured:
            if pid not in given:
                self.add("robustness", f"Add the robustness text for pair '{pid}'.")
        for entry in self.narrative.robustness:
            pair = measured.get(entry.pair)
            if pair is None:
                self.add("robustness", f"'{entry.pair}' is not a measured pair of facts.pairs.")
                continue
            if given.count(entry.pair) > 1:
                self.add("robustness", f"One text per pair; '{entry.pair}' has several.")
            if pair.project not in entry.text:
                self.add(
                    "robustness",
                    f"Name the edition as '{pair.project}' in its text.",
                    entry.text[:80],
                )
            rule = self.rules.get("robustness")
            if rule is not None and len(entry.text) > rule.max_chars:
                self.add("robustness", f"Shorten to {rule.max_chars} characters.", entry.text[:80])

    # -- numbers ----------------------------------------------------------------------------

    def texts(self) -> Iterator[tuple[str, str, str | None]]:
        """(block, text, pair) for every text the reader sees."""
        n = self.narrative
        yield "headline", n.headline, None
        for line in n.happening:
            yield "happening", line, None
        for entry in n.robustness:
            yield "robustness", entry.text, entry.pair
        for line in n.decision:
            yield "decision", line, None
        yield "next_step", n.next_step, None
        yield "chat_answer", n.chat_answer, None

    def numbers_and_terms(self) -> None:
        for block, text, pair in self.texts():
            known = [k for k in self.known if pair is None or k.pair in (None, pair)]
            for line in text.splitlines():
                table_row = line.lstrip().startswith("|")
                for sentence in _sentences(line):
                    self.sentence(block, sentence, known, check_terms=not table_row)

    def sentence(
        self, block: str, sentence: str, known: Sequence[_Known], *, check_terms: bool
    ) -> None:
        for number in extract_numbers(sentence):
            hits = [k for k in known if matches(number, k.value, percent=k.percent)]
            if not hits:
                self.add(
                    block,
                    f"{number.text} is not in facts.json: copy numbers from "
                    "numbers[].display and compute nothing new.",
                    sentence[:120],
                )
                continue
            metrics = {k.metric for k in hits}
            named = [m for m in metrics if m is not None]
            if not check_terms or not named:
                continue
            if not any(self.names(sentence, m) for m in named):
                terms = " or ".join(f"'{self.terms[m][-1]}'" for m in sorted(named))
                self.add(
                    block,
                    f"{_quote(number)} needs its metric in the same sentence: {terms}.",
                    sentence[:120],
                )

    def names(self, sentence: str, metric: str) -> bool:
        return any(_has_term(sentence, term) for term in self.terms.get(metric, []))

    # -- words ------------------------------------------------------------------------------

    def words(self) -> None:
        language = self.facts.language
        jargon = _JARGON.get(language)
        demand = _DEMAND.get(language)
        for block, text, _ in self.texts():
            for pattern, message in _ANYWHERE:
                if pattern.search(text):
                    self.add(block, message, text[:120])
            if jargon and re.search(jargon, text, re.IGNORECASE):
                self.add(
                    block,
                    "No statistical jargon: say steady, mixed or cannot be judged.",
                    text[:120],
                )
            if demand and block in _DESCRIPTIVE and re.search(demand, text, re.IGNORECASE):
                self.add(
                    block,
                    "Wikipedia views are attention, not demand: describe them as attention.",
                    text[:120],
                )

    # -- caveats and interface --------------------------------------------------------------

    def caveats(self) -> None:
        declared = set(self.narrative.covered_caveats)
        for caveat in self.facts.caveats:
            if caveat.id not in declared:
                self.add(
                    "covered_caveats",
                    f"Cover caveat '{caveat.id}' in chat_answer "
                    f"({caveat.meaning}) and list its id.",
                )
            elif caveat.pair and caveat.pair.split(" ")[0] not in self.narrative.chat_answer:
                self.add("chat_answer", f"Caveat '{caveat.id}' must name {caveat.pair}.")

    def ui(self, cached: Mapping[str, str]) -> None:
        given = {**cached, **self.narrative.ui}
        missing = [key for key in self.facts.ui_strings if not given.get(key, "").strip()]
        if missing:
            self.add(
                "ui",
                f"Translate every key of facts.ui_strings; missing: "
                f"{', '.join(missing[:_LISTED_KEYS])}{'…' if len(missing) > _LISTED_KEYS else ''}.",
            )
        for key, text in self.narrative.ui.items():
            english = self.facts.ui_strings.get(key)
            if english is not None and _fields(english) != _fields(text):
                self.add(
                    "ui",
                    f"Keep the placeholders of '{key}' as they are: "
                    f"{', '.join(sorted(_fields(english))) or 'none'}.",
                    text[:80],
                )


def _known(facts: Facts) -> list[_Known]:
    """Numbers the text may quote: the facts, plus those inside texts the code wrote."""
    out: list[_Known] = []
    for pair in facts.pairs:
        for n in pair.numbers:
            fraction = n.unit == "fraction"
            out.append(_Known(n.value * 100 if fraction else n.value, fraction, n.metric, pair.id))
    quoted: list[tuple[str, str | None]] = [
        *((f.text, f.pair) for f in facts.findings),
        *((line, None) for line in (*facts.data_note, *facts.limitations)),
        *((line, p.id) for p in facts.pairs for line in p.reading),
    ]
    for text, pair_id in quoted:
        for number in extract_numbers(text, ignore_below=0):
            out.extend(_Known(v, number.is_percent, None, pair_id) for v in number.values)
    out.extend(_Known(v, False, None, None) for v in _ALWAYS_ALLOWED)
    return out


def _sentences(text: str) -> Iterator[str]:
    """Split at sentence ends followed by a capital letter ("3 мес. доля" stays one)."""
    start = 0
    for match in _SENTENCE_BREAK.finditer(text):
        following = text[match.end() : match.end() + 1]
        if following.isupper():
            yield text[start : match.end()].strip()
            start = match.end()
    rest = text[start:].strip()
    if rest:
        yield rest


def _stems(term: str) -> list[str]:
    """Word stems of a term, so inflected forms match ("доля" finds "доли", "долю")."""
    words = re.findall(r"\w+", term.lower())
    return [w[: max(3, len(w) - 2)] if len(w) > 3 else w for w in words]  # noqa: PLR2004


def _has_term(sentence: str, term: str) -> bool:
    words = re.findall(r"\w+", sentence.lower())
    stems = _stems(term)
    return bool(stems) and all(any(w.startswith(s) for w in words) for s in stems)


def _fields(template: str) -> set[str]:
    try:
        return {name for _, name, _, _ in Formatter().parse(template) if name}
    except ValueError:
        return {"<unbalanced braces>"}


def _quote(number: ProseNumber) -> str:
    return f"'{number.text}'"
