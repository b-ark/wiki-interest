"""Checks the agent's text against the observations it cites before it goes into the report.

The agent writes in any language, so the checks rely on what does not depend on it: the
observations each paragraph cites (they must exist, and its numbers must be theirs), the
shape and length of the blocks, and a few patterns of the languages the skill knows: "five
years ago" instead of the period an observation names, a country instead of a language,
views counted as people, "demand" for attention. The patterns cover the languages the skill
knows and are skipped for the rest.

Every problem is a sentence addressed to the agent: what is wrong, where, and what to do.
"""

# ruff: noqa: RUF001  -- Cyrillic and Polish letters in the patterns are intentional.

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from string import Formatter

from wiki_interest.application.facts import LIMITS, PARAGRAPH_PERCENTAGES, STORY_PARAGRAPHS
from wiki_interest.contracts.narrative import Facts, Narrative, NarrativeProblem, Paragraph
from wiki_interest.contracts.summary import ObservationOut
from wiki_interest.domain.prose_numbers import extract_numbers, matches

__all__ = ["check_narrative"]

_ALWAYS_ALLOWED = (12.0, 24.0, 1_000_000.0)
"""Counts any text may use: the 12-month windows, "per 1 000 000 views"."""
_EXCERPT = 120

_ANYWHERE: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"(?i)\b1\s+(?:in|of|из|з|із|na|z|ze|von|sur|de|su|op|av)\s+\d"),
        "Do not write '1 in N': quote the numbers the observations give.",
    ),
    (re.compile(r"(?i)\bp\s*[=<≤]\s*0"), "No p-values: say whether the trend is steady."),
)
_YEARS_AGO = re.compile(
    r"(?i)\b(?:\d+|two|three|four|five|six|seven|several)\s+years?\s+ago\b"
    r"|\b(?:\d+|дв[аеух]\w*|тр[иёе]\w*|четыр\w*|пят\w*|шест\w*|сем\w*|нескольк\w*)"
    r"\s+(?:год\w*|лет)\s+назад"
    r"|\b(?:\d+|дв\w*|тр\w*|чотир\w*|п.ят\w*|шіст\w*|сім\w*|кільк\w*)"
    r"\s+(?:рок\w*|рік)\s+тому"
    r"|\b(?:\d+|dw\w*|trz\w*|czter\w*|pięć\w*|pięci\w*|sześ\w*|siedm?\w*|kilk\w*)"
    r"\s+lat\w*\s+temu"
    r"|\bsprzed\s+(?:\d+|dw\w*|trz\w*|czter\w*|pięci\w*|sześ\w*|kilk\w*)\s+lat"
    r"|\bpřed\s+(?:\d+|dvěma|třemi|čtyřmi|pěti|šesti|sedmi|několika)\s+lety"
    r"|\bvor\s+(?:\d+|zwei|drei|vier|fünf|sechs|sieben|einigen)\s+jahren"
)
"""A period counted back from today: the observations name their months instead."""
_PEOPLE = re.compile(
    r"(?i)\d[\d\s\u00a0\u202f,.]*\s*(?:people|persons|readers|человек|людей|читател\w*|"
    r"осіб|людини|читач\w*|osób|osoby|czytelnik\w*|lidí|čtenář\w*|"
    r"Menschen|Personen|Leser)\b"
)
"""A count of views written as a count of people."""
_SPEEDS_UP = re.compile(
    r"(?i)accelerat|speed(?:s|ing)?\s+up|faster\s+than\s+(?:before|ever)|ускор|прискор"
    r"|przyspiesz|zrychl|beschleunig"
)
"""A change said to speed up: only an observation that says so ("speeds up") allows it. A cheap
model read "the article lost more than the edition" as the fall speeding up (2026-09-25)."""
_NOT_AN_EDITION = r"(?!\s+[Ww]ikipedi)"
_COUNTRIES: Mapping[str, str] = {
    "ru": r"\bRussia\b|\bРосси|\bРосі[їяю]\b|\bRosj[aię]\b|\bRusk[oua]\b|\bRussland\b",
    "uk": r"\bUkraine\b|\bУкраин[аеуы]\b|\bУкраїн[аиіу]\b|\bUkrain(?:a|ie|y|ę)\b"
    r"|\bUkrajin[aěuy]\b",
    "pl": rf"\bPoland\b|\bPols(?:ka|ki)\b{_NOT_AN_EDITION}|\bPols(?:ce|kę|ko|ku)\b"
    r"|\bПольш[аеиу]\b|\bПольщ[аіу]\b|\bPolen\b",
    "cs": r"\bCzech Republic\b|\bCzechia\b|\bCzech(?:y|ach|ami)\b|\bČesk[ou]\b"
    r"|\bČeské republi|\bЧехи[яиюей]\b|\bЧехі[яїю]\b|\bTschechien\b",
    "de": r"\bGermany\b|\bDeutschland\b|\bГермани[яиюей]\b|\bНімеччин[аиіу]\b"
    r"|\bNiem(?:cy|czech|iec)\b|\bNěmeck[ouu]\b",
    "fr": r"\bFrance\b|\bФранци[яиюей]\b|\bФранці[яїю]\b|\bFrancj[aię]\b|\bFrankreich\b",
    "es": r"\bSpain\b|\bИспани[яиюей]\b|\bІспані[яїю]\b|\bHiszpani[aię]\b|\bSpanien\b",
    "it": r"\bItaly\b|\bИтали[яиюей]\b|\bІталі[яїю]\b|\bWłoch(?:y|ach)\b|\bItalien\b",
}
"""Country names of an edition's language, in the languages the skill knows. Adjectives of
the language are lower case in these languages ("polska Wikipedia"), names of the country
capitalised, except Polish, where "Polska Wikipedia" opening a sentence is the edition."""
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
_DESCRIPTIVE = ("headline", "story")
"""Blocks that describe the Wikipedia data: "demand" there would call views demand. The
meaning and the check may speak of demand: "check the demand with a small ad test"."""
_SENTENCE_BREAK = re.compile(r"[.!?…]\s+")
_FOREIGN_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
"""Kana, CJK ideographs and Hangul: a cheap model sometimes drops a Chinese word into Ukrainian."""
_CJK_LANGUAGES = frozenset({"zh", "ja", "ko"})


@dataclass(frozen=True, slots=True)
class _Allowed:
    """A number a block may quote: from an observation it cites, or always allowed."""

    value: float
    percent: bool


def check_narrative(facts: Facts, narrative: Narrative) -> list[NarrativeProblem]:
    """Every reason ``narrative`` cannot go into the report; empty when it can.

    Args:
        facts: What the code observed for this run.
        narrative: The agent's text.
    """
    checker = _Checker(facts, narrative)
    checker.shape()
    checker.citations()
    checker.numbers()
    checker.directions()
    checker.words()
    checker.ui()
    return checker.problems


class _Checker:
    def __init__(self, facts: Facts, narrative: Narrative) -> None:
        self.facts = facts
        self.narrative = narrative
        self.problems: list[NarrativeProblem] = []
        self.observations = {o.id: o for o in facts.observations}

    def add(self, block: str, message: str, excerpt: str | None = None) -> None:
        self.problems.append(
            NarrativeProblem(
                block=block,
                message=message,
                excerpt=excerpt[:_EXCERPT] if excerpt else None,
            )
        )

    # -- shape ------------------------------------------------------------------------------

    def shape(self) -> None:
        n = self.narrative
        if n.language != self.facts.language:
            self.add(
                "language",
                f"Write in '{self.facts.language}' (facts.language), not '{n.language}'.",
            )
        if n.topic.strip():
            self.length("topic", n.topic)
        self.length("headline", n.headline, required=True)
        if extract_numbers(n.headline):
            self.add("headline", "The headline has no numbers; they go in the story.", n.headline)
        if len(list(_sentences(n.headline))) > 1:
            self.add("headline", "The headline is one sentence.", n.headline)
        most = STORY_PARAGRAPHS[1]
        if not [p for p in n.story if p.text.strip()]:
            self.add("story", "Write the story: paragraphs that explain what is happening.")
        if len(n.story) > most:
            self.add("story", f"At most {most} paragraphs in 'story', got {len(n.story)}.")
        for paragraph in n.story:
            self.length("story", paragraph.text, required=True)
        total = sum(len(p.text) for p in n.story)
        if total > LIMITS["story_total"]:
            self.add(
                "story",
                f"Shorten the story to {LIMITS['story_total']} characters in all (now {total}): "
                "keep what answers the question and explain it, do not retell every observation.",
            )
        self.length("meaning", n.meaning.text, required=True)
        self.length("check", n.check, required=True)
        self.length("limits", n.limits, required=True)

    def length(self, block: str, text: str, *, required: bool = False) -> None:
        limit = LIMITS[block]
        if required and not text.strip():
            self.add(block, f"'{block}' is empty.")
        if len(text) > limit:
            self.add(block, f"Shorten to {limit} characters (now {len(text)}).", text[:80])

    # -- citations --------------------------------------------------------------------------

    def citations(self) -> None:
        n = self.narrative
        cited: set[str] = set()
        for block, paragraph in self.paragraphs():
            if not paragraph.uses and paragraph.text.strip():
                self.add(
                    block,
                    "List in 'uses' the ids of the observations this paragraph relies on.",
                    paragraph.text,
                )
            for oid in paragraph.uses:
                if oid not in self.observations:
                    self.add(
                        block,
                        f"'{oid}' is not an observation of facts.json: cite ids as they are "
                        "listed in facts.observations.",
                    )
                cited.add(oid)
        by_weight = self._by_weight()
        main = by_weight.get("high", []) + by_weight.get("caution", [])
        story_uses = {oid for p in n.story for oid in p.uses}
        if main and not story_uses & {o.id for o in main}:
            self.add(
                "story",
                "Build the story on the main observations: cite at least one caution or high "
                f"one ({', '.join(o.id for o in main[:4])}).",
            )
        decisions = by_weight.get("decision", [])
        if decisions and not set(n.meaning.uses) & {o.id for o in decisions}:
            self.add(
                "meaning",
                "Build the meaning on the decision observations that fit the question and "
                f"cite them in 'uses' ({', '.join(o.id for o in decisions[:4])}).",
            )
        for caution in by_weight.get("caution", []):
            if caution.id not in cited:
                self.add(
                    "story",
                    f"Carry the caution '{caution.id}' in the story and cite it: "
                    f"{caution.statement}",
                )

    def _by_weight(self) -> dict[str, list[ObservationOut]]:
        out: dict[str, list[ObservationOut]] = {}
        for o in self.facts.observations:
            out.setdefault(o.weight, []).append(o)
        return out

    def paragraphs(self) -> Iterator[tuple[str, Paragraph]]:
        for paragraph in self.narrative.story:
            yield "story", paragraph
        yield "meaning", self.narrative.meaning

    # -- numbers ----------------------------------------------------------------------------

    def numbers(self) -> None:
        everything = self._allowed(self.facts.observations)
        for block, paragraph in self.paragraphs():
            cited = [self.observations[i] for i in paragraph.uses if i in self.observations]
            self._numbers_in(block, paragraph.text, self._allowed(cited), paragraph.uses)
            percentages = [n for n in extract_numbers(paragraph.text) if n.is_percent]
            if len(percentages) > PARAGRAPH_PERCENTAGES:
                self.add(
                    block,
                    f"At most {PARAGRAPH_PERCENTAGES} percentages in a paragraph "
                    f"(now {len(percentages)}): "
                    "keep the ones that carry the point and say the rest in words ('fell faster "
                    "than the whole Wikipedia').",
                    paragraph.text,
                )
        for block, text in (("check", self.narrative.check), ("limits", self.narrative.limits)):
            self._numbers_in(block, text, everything, None)

    def _numbers_in(
        self,
        block: str,
        text: str,
        allowed: Sequence[_Allowed],
        uses: Sequence[str] | None,
    ) -> None:
        for sentence in _sentences(text):
            for number in extract_numbers(sentence):
                if any(matches(number, a.value, percent=a.percent) for a in allowed):
                    continue
                where = (
                    f"the observations this paragraph cites ({', '.join(uses)})"
                    if uses
                    else "the observations"
                )
                self.add(
                    block,
                    f"'{number.text}' is not in {where}: quote their numbers (rounding is "
                    "fine), cite the observation a number comes from, and compute nothing new.",
                    sentence,
                )

    def directions(self) -> None:
        """A paragraph keeps the direction of what it cites: nothing speeds up unless said so."""
        for block, paragraph in self.paragraphs():
            match = _SPEEDS_UP.search(paragraph.text)
            if match is None:
                continue
            cited = [self.observations[i] for i in paragraph.uses if i in self.observations]
            if not any("the fall speeds up" in o.statement for o in cited):
                self.add(
                    block,
                    f"'{match.group(0)}': none of the observations this paragraph cites says the "
                    "change speeds up. Keep each observation's direction: 'lost more than the "
                    "edition' compares the article with Wikipedia, not this year with the last.",
                    paragraph.text,
                )

    @staticmethod
    def _allowed(observations: Iterable[ObservationOut]) -> list[_Allowed]:
        out = [_Allowed(q.value, q.percent) for o in observations for q in o.numbers]
        out += [_Allowed(v, False) for v in _ALWAYS_ALLOWED]
        return out

    # -- words ------------------------------------------------------------------------------

    def texts(self) -> Iterator[tuple[str, str]]:
        n = self.narrative
        yield "headline", n.headline
        for paragraph in n.story:
            yield "story", paragraph.text
        yield "meaning", n.meaning.text
        yield "check", n.check
        yield "limits", n.limits

    def words(self) -> None:
        language = self.facts.language
        jargon = _JARGON.get(language)
        demand = _DEMAND.get(language)
        countries = self._countries()
        for block, text in self.texts():
            for pattern, message in _ANYWHERE:
                if pattern.search(text):
                    self.add(block, message, text)
            odd = _FOREIGN_SCRIPT.search(text)
            if odd is not None and language not in _CJK_LANGUAGES:
                self.add(
                    block, "Remove the characters of another script.", text[odd.start() - 40 :]
                )
            if jargon and re.search(jargon, text, re.IGNORECASE):
                self.add(block, "No statistical jargon: say steady, mixed or unclear.", text)
            if demand and block in _DESCRIPTIVE and re.search(demand, text, re.IGNORECASE):
                self.add(
                    block,
                    "Wikipedia views are attention, not demand: describe them as attention.",
                    text,
                )
            if block in ("check", "limits"):
                # "the Polish Wikipedia is a language, not Poland" is right in the limits, and
                # search volume "in Poland" is how a check outside Wikipedia is done.
                continue
            if (match := _YEARS_AGO.search(text)) is not None:
                self.add(
                    block,
                    f"'{match.group(0)}': name the period as the observation does ('September "
                    "2020 – August 2021', 'over the last year'), not counted back from today.",
                    text,
                )
            if (match := _PEOPLE.search(text)) is not None:
                self.add(
                    block,
                    f"'{match.group(0)}': views count how often the article is opened, not "
                    "people; write 'the article is opened N times a month'.",
                    text,
                )
            if countries is not None and (match := countries.search(text)) is not None:
                self.add(
                    block,
                    f"'{match.group(0)}': name the edition by its language ('the Polish "
                    "Wikipedia'), not a country: an edition is read in many countries.",
                    text,
                )

    def _countries(self) -> re.Pattern[str] | None:
        languages = {
            o.pair.split("/")[-1] for o in self.facts.observations if o.pair and "/" in o.pair
        }
        patterns = [f"(?:{_COUNTRIES[code]})" for code in sorted(languages) if code in _COUNTRIES]
        return re.compile("|".join(patterns)) if patterns else None

    # -- interface --------------------------------------------------------------------------

    def ui(self) -> None:
        """Translations keep their placeholders; a missing one stays English, not a rejection.

        The facts list every label, so the agent translates in place. A label left out
        costs an English word in the PDF; rejecting the text for it cost the user the whole
        analysis (verified 2026-09-23 on the evals). No translation at all is rejected: an
        agent that wrote the text from scratch dropped ``ui`` in a third of the runs, and
        the whole PDF stayed English.
        """
        if self.facts.ui and not self.narrative.ui:
            self.add(
                "ui",
                "Translate every label of facts.ui into 'ui' (same keys, keep the {placeholders}).",
            )
        for key, text in self.narrative.ui.items():
            english = self.facts.ui.get(key)
            if english is not None and _fields(english) != _fields(text):
                self.add(
                    "ui",
                    f"Keep the placeholders of '{key}' as they are: "
                    f"{', '.join(sorted(_fields(english))) or 'none'}.",
                    text[:80],
                )


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


def _fields(template: str) -> set[str]:
    try:
        return {name for _, name, _, _ in Formatter().parse(template) if name}
    except ValueError:
        return {"<unbalanced braces>"}
