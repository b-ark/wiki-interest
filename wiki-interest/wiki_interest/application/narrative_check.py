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

_HINT_OPTIONS = 3
_SHORT_WORD = 3
_LONG_WORD = 8
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
_UNMEASURED = ("caveats",)
"""Blocks of warnings, not measurements: a number there must be a fact, but needs no metric."""
_DESCRIPTIVE = ("headline", "happening", "robustness")
"""Blocks that describe the Wikipedia data: "demand" there would call views demand. The
decision and the next step may speak of demand: "check the demand with Google Trends"."""
_SENTENCE_BREAK = re.compile(r"[.!?…]\s+")
_LIST_ITEM = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_PER_MILLION = re.compile(
    r"(?i)(?<!\w)(?:per|на|na|pro|por|par|je|pe|op|al|för)\s+(?:1\s*)?"
    r"(?:million|mln|мільйон|миллион|млн|milion|milión|millón|milione|miljoen|miljon|millió)"
)
""""Per million" in the languages the reports are written in: it names the attention share as
surely as the glossary term does, for a number whose unit is per million."""
_FOREIGN_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
"""Kana, CJK ideographs and Hangul: a cheap model sometimes drops a Chinese word into Ukrainian."""
_CJK_LANGUAGES = frozenset({"zh", "ja", "ko"})


@dataclass(frozen=True, slots=True)
class _Known:
    """A number the text may quote, on the scale prose writes it.

    ``unit`` and ``display`` come from ``numbers[]``: the unit decides whether "per million"
    names the metric, the display form lets a problem show the agent the words to write.
    """

    value: float
    percent: bool
    metric: str | None
    pair: str | None
    unit: str | None = None
    display: str | None = None


def check_narrative(facts: Facts, narrative: Narrative) -> list[NarrativeProblem]:
    """Every reason ``narrative`` cannot go into the report; empty when it can.

    Args:
        facts: What the code computed for this run.
        narrative: The agent's text.
    """
    checker = _Checker(facts, narrative)
    checker.shape()
    checker.numbers_and_terms()
    checker.words()
    checker.caveats()
    checker.ui()
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
        self.marks = _distinctive_stems(self.terms)

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
        if n.topic.strip():
            self.length("topic", [n.topic])
        self.length("headline", [n.headline])
        if re.search(r"\d", n.headline):
            self.add("headline", "The headline has no numbers; they go in 'happening'.", n.headline)
        if len(list(_sentences(n.headline))) > 1:
            self.add("headline", "The headline is one sentence.", n.headline)
        self.length("happening", n.happening)
        self.length("decision", n.decision)
        self.length("next_step", [n.next_step])
        self.length("caveats", n.caveats)
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
        for line in n.caveats:
            yield "caveats", line, None

    def numbers_and_terms(self) -> None:
        for block, text, pair in self.texts():
            known = [k for k in self.known if pair is None or k.pair in (None, pair)]
            heading = ""
            for line in text.splitlines():
                table_row = line.lstrip().startswith("|")
                item = _LIST_ITEM.match(line) is not None
                # A list continues the line that introduces it ("Attention share:"): a metric
                # named there covers the numbers of every item.
                context = heading if item else ""
                for sentence in _sentences(line):
                    check_terms = not table_row and block not in _UNMEASURED
                    self.sentence(block, sentence, known, context, check_terms=check_terms)
                if not item:
                    heading = line if line.rstrip().endswith(":") else ""

    def sentence(
        self,
        block: str,
        sentence: str,
        known: Sequence[_Known],
        context: str = "",
        *,
        check_terms: bool,
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
            named = sorted({k.metric for k in hits if k.metric is not None})
            if not check_terms or not named or _is_count(number, hits):
                continue
            text = f"{context} {sentence}"
            if any(self.names(text, m, hits) for m in named):
                continue
            # A number only one metric has may go without its name, unless the sentence
            # names another metric: then it is attributed to the wrong one. Rejecting the
            # bare number cost a turn and often the whole text (verified 2026-09-23).
            others = [m for m in self.terms if m not in named]
            if len(named) > 1 or any(self.names(text, m, hits) for m in others):
                self.add(block, self.metric_hint(number, hits), sentence[:120])

    def names(self, text: str, metric: str, hits: Sequence[_Known]) -> bool:
        """Whether ``text`` names ``metric``: a term of it, or "per million" for a share."""
        words = re.findall(r"\w+", text.lower())
        for stems in self.marks.get(metric, []):
            if any(w.startswith(s) for s in stems for w in words):
                return True
        per_million = any(k.metric == metric and k.unit == "per_million" for k in hits)
        return per_million and _PER_MILLION.search(text) is not None

    def metric_hint(self, number: ProseNumber, hits: Sequence[_Known]) -> str:
        """The problem with the words to write: the agent's own term and the display form."""
        options: list[str] = []
        for hit in hits:
            if hit.metric is None:
                continue
            option = f"'{self.terms[hit.metric][-1]} {hit.display or number.text}'"
            if option not in options:
                options.append(option)
        return (
            f"{_quote(number)} needs its metric in the same sentence; write it as "
            f"{' or '.join(options[:_HINT_OPTIONS])}."
        )

    # -- words ------------------------------------------------------------------------------

    def words(self) -> None:
        language = self.facts.language
        jargon = _JARGON.get(language)
        demand = _DEMAND.get(language)
        for block, text, _ in self.texts():
            for pattern, message in _ANYWHERE:
                if pattern.search(text):
                    self.add(block, message, text[:120])
            odd = _FOREIGN_SCRIPT.search(text)
            if odd is not None and language not in _CJK_LANGUAGES:
                start = max(0, odd.start() - 40)
                self.add(block, "Remove the characters of another script.", text[start:][:120])
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
        items = " ".join(self.narrative.caveats)
        for caveat in self.facts.caveats:
            if caveat.id not in declared:
                self.add(
                    "covered_caveats",
                    f"Cover caveat '{caveat.id}' in caveats ({caveat.meaning}) and list its id.",
                )
            elif caveat.pair and caveat.pair.split(" ")[0] not in items:
                self.add("caveats", f"Caveat '{caveat.id}' must name {caveat.pair}.")

    def ui(self) -> None:
        """Translations keep their placeholders; a missing one stays English, not a rejection.

        The template lists every label, so the agent translates in place. A label left out
        costs an English word in the PDF; rejecting the text for it cost the user the whole
        analysis (verified 2026-09-23 on the evals). No translation at all is rejected: an
        agent that wrote the text from scratch dropped ``ui`` in a third of the runs, and
        the whole PDF stayed English.
        """
        if self.facts.template.ui and not self.narrative.ui:
            self.add(
                "ui",
                "Translate every label of facts.template.ui into 'ui' (same keys, keep the "
                "{placeholders}).",
            )
        for key, text in self.narrative.ui.items():
            english = self.facts.template.ui.get(key)
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
            value = n.value * 100 if fraction else n.value
            out.append(_Known(value, fraction, n.metric, pair.id, n.unit, n.display))
            # The display form always passes, whatever the rounding at a boundary: 1.95 is
            # shown as "×2,0", and "2,0" read back is 0.05 away from the value.
            out.extend(
                _Known(v, shown.is_percent, n.metric, pair.id, n.unit, n.display)
                for shown in extract_numbers(n.display, ignore_below=0)
                for v in shown.values
                if v != value
            )
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
    """Word stems of a term, so inflected forms match ("доля" finds "доли", "долю").

    Long words lose three letters: Polish and Ukrainian endings change more than two
    ("wyświetlenia", "wyświetleń"; "перегляди", "переглядів").
    """
    return [_stem(w) for w in re.findall(r"\w+", term.lower())]


def _stem(word: str) -> str:
    if len(word) <= _SHORT_WORD:
        return word
    cut = 3 if len(word) >= _LONG_WORD else 2
    return word[: max(_SHORT_WORD, len(word) - cut)]


def _distinctive_stems(terms: Mapping[str, list[str]]) -> dict[str, list[list[str]]]:
    """For every metric, the stems of each of its terms that no other metric's terms share.

    One distinctive stem names the metric: "289 переглядів" names "перегляди статті" when
    no other metric speaks of "перегляди", while "перегляди статті" and "перегляди видання"
    are told apart only by "статті" and "видання". A term with no stem of its own keeps all
    its stems, and then any of them names it.
    """
    stems = {m: [_stems(t) for t in ts] for m, ts in terms.items()}
    out: dict[str, list[list[str]]] = {}
    for metric, own in stems.items():
        others = {s for m, ts in stems.items() if m != metric for t in ts for s in t}
        # Stems of one word differ with the ending cut ("просмот", "просмо"), so a stem is
        # shared when it and another metric's stem are prefixes of one another.
        out[metric] = [
            [s for s in t if not any(s.startswith(o) or o.startswith(s) for o in others)] or t
            for t in own
            if t
        ]
    return out


def _is_count(number: ProseNumber, hits: Sequence[_Known]) -> bool:
    """A count or a window length ("the last 12 months"): it has no metric to name.

    Only whole numbers written without a percent sign qualify, so a change that happens to
    equal a number quoted in a finding still has to name its metric.
    """
    if number.is_percent:
        return False
    return any(k.metric is None and (k.unit == "count" or k.value in _ALWAYS_ALLOWED) for k in hits)


def _fields(template: str) -> set[str]:
    try:
        return {name for _, name, _, _ in Formatter().parse(template) if name}
    except ValueError:
        return {"<unbalanced braces>"}


def _quote(number: ProseNumber) -> str:
    return f"'{number.text}'"
