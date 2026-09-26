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
_LENGTH_SLACK = 1.1
"""A block is rejected only this far over its limit. The limits are what the rules ask for,
and the messages still name them; a paragraph 6 characters over (506 of 500) sent a whole
analysis back to the template (stage15)."""
_NAMED = re.compile(r"«([^»]+)»")
"""An article a caution names (a substitute): the text must name it too."""
_COUNTRIES: Mapping[str, str] = {
    "ru": r"\bRussia\b|\bРосси|\bРосі[їяю]\b|\bRosj[aię]\b|\bRusk[oua]\b|\bRussland\b",
    "uk": r"\bUkraine\b|\bУкраин[аеуы]\b|\bУкраїн[аиіу]\b|\bUkrain(?:a|ie|y|ę)\b"
    r"|\bUkrajin[aěuy]\b",
    "pl": r"\bPoland\b|\bPols(?:ce|kę)\b|\bПольш[аеиу]\b|\bПольщ[аіу]\b|\bPolen\b",
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
capitalised; Polish "Polska" and "Polski" are left out: opening a sentence they are the
language ("Polska Wikipedia", "Polska edycja") as often as the country (2026-09-25)."""
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
_TERMS: Mapping[str, tuple[tuple[str, str], ...]] = {
    "uk": ((r"обсяг\w* уваги", "частка уваги"),),
    "ru": ((r"объ[её]м\w* внимания", "доля внимания"),),
    "en": ((r"attention volume|volume of attention", "attention share"),),
}
"""One term per measure, as the charts and the code's lines use it: the article's share of its
Wikipedia's views is the attention share ("частка уваги"), its own count is views
("перегляди"). A pattern the report language must not use, and the term to write instead."""
_UI_MISSING_SHARE = 0.5
"""More labels than this share left out: the report's headings and charts stay English."""
_UI_MISSING_SHOWN = 6
_COMPARISONS = ("editions", "topics")
"""Observations that set editions or topics against each other: a story of several must cite
them, or it tells each apart instead of comparing (the user's report spec, 2026-09-25)."""
_TRADE_OFFS = ("decision:editions:", "decision:topics:")
"""The decision of a comparison: the meaning of several editions gives this trade-off."""
_DESCRIPTIVE = ("story",)
"""Blocks that describe the Wikipedia data: "demand" there would call views demand. The
meaning and the check may speak of demand: "check the demand with a small ad test"."""
_SENTENCE_BREAK = re.compile(r"[.!?…]\s+")
_CJK_SCRIPT = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]+")
"""Kana, CJK ideographs and Hangul: a cheap model sometimes drops a Chinese word into Ukrainian."""
_CJK_LANGUAGES = frozenset({"zh", "ja", "ko"})
_CYRILLIC_SCRIPT = re.compile(r"[\u0400-\u04ff]+")
"""Cyrillic: a cheap model writing Polish after reading Ukrainian drops in a Russian word
("To означает, że...", 2026-09-25)."""
_LATIN_LETTERS = re.compile(r"[A-Za-z]")
_CYRILLIC_LETTERS = re.compile(r"[\u0400-\u04ff]")
_MIN_LETTERS = 40
"""A block this short (a name, a code) is not judged by its letters."""
_CYRILLIC_LANGUAGES = frozenset(
    {"ru", "uk", "be", "bg", "sr", "mk", "kk", "ky", "tg", "mn", "tt", "ba", "cv", "ce", "sah"}
)


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
    checker.comparisons()
    checker.numbers()
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
            # The topic line opens the chat answer; a uk one once carried the item's
            # description in Chinese (stage15).
            if (odd := self._foreign_script(n.topic)) is not None:
                self.add(
                    "topic",
                    f"'{odd}' is in another script: write the topic line in the report "
                    "language, its description as facts.topics gives it.",
                    n.topic,
                )
        most = STORY_PARAGRAPHS[1]
        if not [p for p in n.story if p.text.strip()]:
            self.add("story", "Write the story: paragraphs that explain what is happening.")
        if len(n.story) > most:
            self.add("story", f"At most {most} paragraphs in 'story', got {len(n.story)}.")
        for paragraph in n.story:
            self.length("story", paragraph.text, required=True)
        total = sum(len(p.text) for p in n.story)
        if total > LIMITS["story_total"] * _LENGTH_SLACK:
            self.add(
                "story",
                f"Shorten the story to {LIMITS['story_total']} characters in all (now {total}, "
                f"cut at least {total - LIMITS['story_total']}): keep what answers the question "
                "and explain it, do not retell every observation.",
            )
        self.length("meaning", n.meaning.text, required=True)
        self.length("check", n.check)
        self.length("limits", n.limits, required=True)

    def length(self, block: str, text: str, *, required: bool = False) -> None:
        limit = LIMITS[block]
        if required and not text.strip():
            self.add(block, f"'{block}' is empty.")
        if len(text) > limit * _LENGTH_SLACK:
            self.add(
                block,
                f"Shorten to {limit} characters (now {len(text)}): cut at least "
                f"{len(text) - limit} characters, a clause or a number that repeats another "
                "paragraph, not the words that explain.",
                text[:80],
            )

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
        text = " ".join(p.text for _, p in self.paragraphs())
        for caution in by_weight.get("caution", []):
            if caution.id not in cited:
                self.add(
                    "story",
                    f"Carry the caution '{caution.id}' in the story and cite it: "
                    f"{caution.statement}",
                )
            for name in dict.fromkeys(_NAMED.findall(caution.statement)):
                if name not in text:
                    self.add(
                        "story",
                        f"Name the article «{name}» where the text talks about its edition: "
                        f"{caution.statement}",
                    )

    def comparisons(self) -> None:
        """Several editions or topics: the text compares them, it does not tell each apart.

        The story must build on a comparison observation, the meaning on a trade-off. One of
        each is enough: two topics in two editions have four comparisons, more than a story's
        length holds.
        """
        n = self.narrative
        story_uses = {oid for p in n.story for oid in p.uses}
        comparisons = [o for o in self.facts.observations if o.kind in _COMPARISONS]
        if comparisons and not story_uses & {o.id for o in comparisons}:
            first = comparisons[0]
            self.add(
                "story",
                "Compare, do not tell each edition apart: build the story on "
                f"{', '.join(repr(o.id) for o in comparisons)} and cite it, for example "
                f"'{first.id}': {first.statement}",
            )
        recommendations = [o.id for o in self.facts.observations if o.kind == "recommendation"]
        if recommendations and not set(n.meaning.uses) & set(recommendations):
            self.add(
                "meaning",
                "Explain the code's recommendation: cite "
                f"{', '.join(repr(i) for i in recommendations)} in 'uses'.",
            )
        names = self.facts.choice_names
        if names and n.meaning.text.strip():
            text = n.meaning.text.lower()
            if not any(name.lower() in text for name in names):
                self.add(
                    "meaning",
                    "Name the recommendation's choice in the meaning (the edition or topic "
                    "the recommendation observation chooses).",
                    n.meaning.text,
                )
        trade_offs = [o.id for o in self.facts.observations if o.id.startswith(_TRADE_OFFS)]
        if trade_offs and not set(n.meaning.uses) & set(trade_offs):
            self.add(
                "meaning",
                "Give the trade-off between the editions (a larger audience against a growing "
                f"one): cite one of {', '.join(repr(i) for i in trade_offs)} in 'uses'.",
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
                    f"(now {len(percentages)}: {', '.join(n.text for n in percentages)}): "
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

    @staticmethod
    def _allowed(observations: Iterable[ObservationOut]) -> list[_Allowed]:
        out = [_Allowed(q.value, q.percent) for o in observations for q in o.numbers]
        out += [_Allowed(v, False) for v in _ALWAYS_ALLOWED]
        return out

    # -- words ------------------------------------------------------------------------------

    def texts(self) -> Iterator[tuple[str, str]]:
        n = self.narrative
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
            if (odd := self._foreign_script(text)) is not None:
                self.add(
                    block,
                    f"'{odd}' is in another script: write every word in the report language "
                    "(article names in «» may keep theirs).",
                    text,
                )
            elif self._mostly_latin(text):
                self.add(
                    block,
                    f"Write this block in the report language ('{language}'), not in English: "
                    "the observations are your notes, the report is in the user's language.",
                    text,
                )
            self.terms(block, text)
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
                    f"'{match.group(0)}': name the period as the observation does ('in 2021', "
                    "'January–August 2026', 'against the same months of 2025'), not counted "
                    "back from today.",
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

    def terms(self, block: str, text: str) -> None:
        """One term per measure: a wording the report language must not use, and its term."""
        for wording, term in _TERMS.get(self.facts.language, ()):
            if (found := re.search(wording, text, re.IGNORECASE)) is not None:
                self.add(
                    block,
                    f"'{found.group(0)}': write '{term}', the report's one term for it.",
                    text,
                )

    def _foreign_script(self, text: str) -> str | None:
        """The first word in a script the report language does not use, outside «names»."""
        bare = _NAMED.sub("", text)
        language = self.facts.language
        scripts = []
        if language not in _CJK_LANGUAGES:
            scripts.append(_CJK_SCRIPT)
        if language not in _CYRILLIC_LANGUAGES:
            scripts.append(_CYRILLIC_SCRIPT)
        for script in scripts:
            if (match := script.search(bare)) is not None:
                return match.group(0)
        return None

    def _mostly_latin(self, text: str) -> bool:
        """A block of a Cyrillic report language written mostly in Latin letters.

        A cheap model wrote a whole Russian report in English, copying the English
        observations, with ``language: ru`` (2026-09-26). Names in «» and codes (``uk``,
        ``Google Trends``) are a few words; most of the letters must be the language's own.
        """
        if self.facts.language not in _CYRILLIC_LANGUAGES:
            return False
        bare = _NAMED.sub("", text)
        latin = len(_LATIN_LETTERS.findall(bare))
        cyrillic = len(_CYRILLIC_LETTERS.findall(bare))
        return latin + cyrillic >= _MIN_LETTERS and latin > cyrillic

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
        analysis (verified 2026-09-23 on the evals). No translation at all, or most labels
        left out, is rejected: the whole PDF would stay English.
        """
        if self.facts.ui and not self.narrative.ui:
            self.add(
                "ui",
                "Translate every label of facts.ui into 'ui' (same keys, keep the {placeholders}).",
            )
        missing = [key for key in self.facts.ui if key not in self.narrative.ui]
        if self.narrative.ui and len(missing) > len(self.facts.ui) * _UI_MISSING_SHARE:
            # An agent copied the example's two labels and left the other 37 in English: the
            # whole PDF's headings and charts stayed English (stage13).
            self.add(
                "ui",
                f"Translate every label of facts.ui, not a few: {len(missing)} of "
                f"{len(self.facts.ui)} are missing, for example "
                f"{', '.join(missing[:_UI_MISSING_SHOWN])}.",
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
