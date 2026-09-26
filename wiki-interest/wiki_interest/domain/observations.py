"""Observations: what the monthly series of a topic show, as statements a writer can explain.

The code decides every direction, comparison and ratio; the agent picks the observations that
answer the user's question and explains them in the user's language. Each observation is one
true statement in plain English with the numbers it quotes, a weight (how much it matters) and
a stable id the agent's text cites, so the text can be checked against what it cites.

The detectors read the *attention share*: the article's views per million views of its whole
language edition, which removes the effect of Wikipedia as a whole gaining or losing readers.

Calendar years, as the report's charts draw them (2021, 2022...): "now" is the last calendar
year, a partial one (January–August 2026) averaged over the months it has, and the long trend
reads full calendar years only, so a partial year's missing season cannot make a trend. A
change compares like with like: "now" against the same months a year earlier (2025 against
2024, January–August 2026 against January–August 2025), the last three months against the
same months a year earlier.

Detectors (each fires only when its data show it):

- ``size``: how often the article is opened in the last calendar year and in the first full
  one of the window;
- ``long_term``: a long decline or rise, a wave that has passed, or a flat range, over full
  calendar years;
- ``vs_edition``: the topic against the whole edition, "now" against a year earlier;
- ``season``: a school-year rhythm, another yearly rhythm, or none (each month against the
  13 months centred on it, medians over years); a timing only when the peak came every year;
- ``spike``: a one-off month far above what that calendar month usually brings;
- ``wave`` / ``unusual``: several months far above the usual level, either a passing wave of
  attention or a flat abrupt plateau that looks automated;
- ``step``: the biggest lasting change of level, the seasonal rhythm removed;
- ``recent``: the last three months against the change of "now" (continues, slower,
  stopped...);
- ``editions``: one topic in two editions in the last calendar year, relative and absolute
  size, and their directions against a year earlier;
- ``topics``: several topics of the user's in one edition against each other;
- ``decision:*``: what the above imply for the next check (timing, audience, where to
  look), a signal, never a decision to invest;
- ``headline``: for one topic, the answer in one sentence without numbers.
"""

# ruff: noqa: RUF001, RUF002  -- the minus sign in the statements is intentional.

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date
from enum import StrEnum
from itertools import pairwise
from statistics import mean, median
from typing import Literal

__all__ = [
    "MONTH_NAMES",
    "Observation",
    "ObservationSettings",
    "PairHistory",
    "Quoted",
    "ShareMove",
    "ViewsDirection",
    "Weight",
    "YearChange",
    "YearLevel",
    "edition_name",
    "observe",
    "round_count",
    "round_share",
    "share_move",
    "views_direction",
    "year_levels",
]

ShareMove = Literal["gained", "held", "lost"]
"""What a change of the share did against a year earlier (:func:`share_move`)."""
ViewsDirection = Literal["up", "flat", "down"]
"""Where an article's views went against a year earlier (:func:`views_direction`)."""

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
_YEAR = 12
_RECENT = 3
_STEP_HALF = 6
_HALF_WINDOW = 6
_MIN_WINDOW = 9
_SUMMER = (6, 7, 8)
_SCHOOL_PEAKS = (9, 10, 11)
_THOUSANDS = 1_000
_TEN_THOUSANDS = 10_000
_EDITION_NAMES = {
    "ar": "Arabic", "bg": "Bulgarian", "ca": "Catalan", "cs": "Czech", "da": "Danish",
    "de": "German", "el": "Greek", "en": "English", "eo": "Esperanto", "es": "Spanish",
    "et": "Estonian", "fa": "Persian", "fi": "Finnish", "fr": "French", "he": "Hebrew",
    "hi": "Hindi", "hr": "Croatian", "hu": "Hungarian", "id": "Indonesian", "it": "Italian",
    "ja": "Japanese", "kk": "Kazakh", "ko": "Korean", "lt": "Lithuanian", "lv": "Latvian",
    "nl": "Dutch", "no": "Norwegian", "pl": "Polish", "pt": "Portuguese", "ro": "Romanian",
    "ru": "Russian", "sk": "Slovak", "sl": "Slovenian", "sr": "Serbian", "sv": "Swedish",
    "th": "Thai", "tr": "Turkish", "uk": "Ukrainian", "vi": "Vietnamese", "zh": "Chinese",
}  # fmt: skip


class Weight(StrEnum):
    """How much an observation matters to the text.

    ``caution`` is a data problem the reader must know before trusting a comparison; ``high``
    the main signals; ``medium`` supporting ones; ``low`` and ``context`` background;
    ``decision`` what the data imply for a decision.
    """

    CAUTION = "caution"
    HIGH = "high"
    MEDIUM = "medium"
    CONTEXT = "context"
    LOW = "low"
    DECISION = "decision"


_ORDER = {w: i for i, w in enumerate(Weight)}


@dataclass(frozen=True, slots=True)
class Quoted:
    """A number an observation states: a text citing it may quote it (rounding allowed).

    ``percent``: written as a percentage (``-46`` for "−46 %").
    """

    value: float
    percent: bool = False


@dataclass(frozen=True, slots=True)
class Observation:
    """One statement about the data.

    Attributes:
        id: Stable identifier the text cites (``season:astronomy/uk``).
        kind: The detector (``season``, ``decision``...).
        pair: ``<topic>/<language>`` it is about, ``None`` when it spans pairs.
        weight: How much it matters.
        statement: The statement in plain English, numbers as a reader sees them.
        numbers: The numbers ``statement`` quotes.
        month: The month a ``step`` or a ``spike`` happened in, for the chart to mark it.
    """

    id: str
    kind: str
    pair: str | None
    weight: Weight
    statement: str
    numbers: tuple[Quoted, ...] = ()
    month: date | None = None


@dataclass(frozen=True, slots=True)
class PairHistory:
    """The monthly series of one topic in one edition, oldest first, aligned by month.

    Attributes:
        topic_id: The request's topic id.
        topic: How the text names the topic (its label).
        project: The edition (``uk.wikipedia``).
        months: First day of each month.
        views: The article's monthly views (with redirects); ``None`` where missing.
        edition: The edition's monthly views; ``None`` where missing.
        substitute: The article measured instead, when the edition has none on the topic (a
            broader or related one): it gets its own observations and a caution, but is never
            compared with the topic elsewhere; charts name it next to the edition.
    """

    topic_id: str
    topic: str
    project: str
    months: tuple[date, ...]
    views: tuple[float | None, ...]
    edition: tuple[float | None, ...]
    substitute: str | None = None

    @property
    def language(self) -> str:
        """The edition's language code (``uk``)."""
        return self.project.split(".")[0]

    @property
    def pair(self) -> str:
        """``<topic>/<language>``, as facts and the text refer to the pair."""
        return f"{self.topic_id}/{self.language}"


@dataclass(frozen=True, slots=True)
class ObservationSettings:
    """Thresholds of the detectors; the defaults were tuned on six topics (2026-09-24).

    Attributes:
        min_trend_months: Months of data a year-on-year reading needs.
        min_long_years: Years the long-term reading needs.
        long_change: Ratio of the last year's share to the first year's that counts as a
            large change (0.7: 30 % lower; its inverse for a rise).
        steady_step: Year-on-year change of the share that counts as a step (3 %).
        wave_peak: How far over the first year a middle year must peak to make a wave.
        wave_fall: How far below its peak the last year must be to make a wave.
        moves: Change of the share against a year earlier that counts as a move (10 %): the
            share gained, held or lost.
        edition_moves: Change of the edition's views that counts as losing readers (5 %).
        outlier: A month this many times its expected level is out of the ordinary.
        plateau_months: Months in a row far above the usual level that make a plateau.
        flat_plateau_months: A plateau at least this long and this flat looks automated.
        flat_plateau_spread: Largest ratio of highest to lowest month of a flat plateau.
        rhythm: Spread between the strongest and weakest calendar month that makes a rhythm (%).
        rhythm_peak: Peak (%) a rhythm needs before the timing of a launch follows from it.
        school_peak: Peak (%) in September–November that makes a school-year rhythm.
        school_summer: Summer level (%) below which a school-year rhythm is read.
        step: Ratio of the level after to the level before that makes a step.
        strong_step: A step at least this large is a main signal.
        edition_step: A step the edition itself took at the same time, of at least this ratio.
        same_size: Ratio under which two editions get about the same relative attention.
        observe_years: Years of history the long-term detectors read.
        partial_months: Fewest months a partial last calendar year needs to stand for "now";
            with fewer, "now" is the last full year.
        partial_bias: How far (%) a partial year's months usually run from the topic's
            yearly level before the text is warned not to set it against full years.
        season_years: Years a season's peak must come in the same month (among the year's
            two strongest) before a timing or an audience follows from it.
        large_audience: How many times the views of another edition make an audience much
            larger; under ``same_size`` two audiences are about the same size.
    """

    min_trend_months: int = 24
    min_long_years: int = 3
    long_change: float = 0.7
    steady_step: float = 0.03
    wave_peak: float = 1.1
    wave_fall: float = 0.75
    moves: float = 10.0
    edition_moves: float = 5.0
    outlier: float = 3.0
    plateau_months: int = 3
    flat_plateau_months: int = 9
    flat_plateau_spread: float = 2.0
    rhythm: float = 30.0
    rhythm_peak: float = 25.0
    school_peak: float = 60.0
    school_summer: float = -15.0
    step: float = 1.35
    strong_step: float = 1.6
    edition_step: float = 1.2
    same_size: float = 1.25
    observe_years: int = 6
    partial_months: int = 3
    partial_bias: float = 10.0
    season_years: int = 4
    large_audience: float = 3.0


_DEFAULT = ObservationSettings()


def edition_name(project: str) -> str:
    """``the Ukrainian Wikipedia`` for ``uk.wikipedia``; the label when the language is unknown."""
    name = _EDITION_NAMES.get(project.split(".", maxsplit=1)[0])
    return f"the {name} Wikipedia" if name else project


# -- wording ---------------------------------------------------------------------------------


def round_count(value: float) -> float:
    """A count as a reader pictures it: 560, 3,800, 69,000."""
    digits = -3 if value >= _TEN_THOUSANDS else -2 if value >= _THOUSANDS else -1
    return round(value, digits)


def round_share(value: float) -> float:
    """An attention share as statements write it: 19.2, 145."""
    return round(value, 1) if value < 100 else round(value)  # noqa: PLR2004


def share_move(change: float, settings: ObservationSettings = _DEFAULT) -> ShareMove:
    """Whether a change of the share (%) gained, held or lost it: ``moves`` either way.

    The observations call a change within ``moves`` no move, so a chart saying "held" and a
    text saying "moved with its Wikipedia" read the same number the same way.
    """
    if change > settings.moves:
        return "gained"
    if change < -settings.moves:
        return "lost"
    return "held"


def views_direction(change: float, settings: ObservationSettings = _DEFAULT) -> ViewsDirection:
    """Whether the article's views (%, against a year earlier) went up, down or held."""
    if change > settings.moves:
        return "up"
    if change < -settings.moves:
        return "down"
    return "flat"


@dataclass(slots=True)
class _Words:
    """Formats numbers for a statement and remembers them, so the text may quote them."""

    quoted: list[Quoted] = field(default_factory=list)

    def pct(self, value: float) -> str:
        """A signed percentage: "−46 %"."""
        rounded = round(value)
        self.quoted.append(Quoted(rounded, percent=True))
        return f"{rounded:+d} %".replace("-", "−")

    def count(self, value: float) -> str:
        """A count a reader can picture: "about 560", "about 3,800", "about 69,000"."""
        rounded = round_count(value)
        self.quoted.append(Quoted(rounded))
        return f"about {rounded:,.0f}"

    def ratio(self, r: float) -> str:  # noqa: PLR0911 -- one wording per band
        """How a ratio of new to old reads: "about a fifth of", "about twice"."""
        for limit, words in (
            (0.13, "about an eighth of"),
            (0.18, "about a sixth of"),
            (0.23, "about a fifth of"),
            (0.29, "about a quarter of"),
            (0.4, "about a third of"),
            (0.6, "about half of"),
        ):
            if r < limit:
                return f"{words} what it was"
        if r < 0.95:  # noqa: PLR2004
            return f"{self._plain(round((1 - r) * 100))} % lower than it was"
        if r <= 1.05:  # noqa: PLR2004
            return "about the same as it was"
        if r < 1.4:  # noqa: PLR2004
            return f"{self._plain(round((r - 1) * 100))} % higher than it was"
        if r < 1.8:  # noqa: PLR2004
            self.quoted.append(Quoted(1.5))  # a text may write "1.5 times"
            return "about one and a half times what it was"
        if r < 2.5:  # noqa: PLR2004
            self.quoted.append(Quoted(2))
            return "about twice what it was"
        return f"about {self._plain(round(r), percent=False)} times what it was"

    def times(self, r: float) -> str:
        """A size ratio: "about as much", "about twice as much", "about 7 times as much"."""
        if r < 1.25:  # noqa: PLR2004
            return "about as much"
        if r < 1.75:  # noqa: PLR2004
            self.quoted.append(Quoted(1.5))  # a text may write "1.5 times"
            return "about one and a half times as much"
        if r < 2.5:  # noqa: PLR2004
            self.quoted.append(Quoted(2))
            return "about twice as much"
        return f"about {self._plain(round(r), percent=False)} times as much"

    def per_million(self, value: float) -> str:
        """An attention share: "19.2", "145"."""
        rounded = round_share(value)
        self.quoted.append(Quoted(rounded))
        return f"{rounded:,}"

    def _plain(self, value: int, *, percent: bool = True) -> str:
        self.quoted.append(Quoted(value, percent=percent))
        return str(value)


def _month(d: date) -> str:
    return f"{MONTH_NAMES[d.month - 1]} {d.year}"


def _span(months: Sequence[date], first: int, last: int) -> str:
    """The months ``first`` to ``last``: "September 2020 – August 2021"."""
    return f"{_month(months[first])} – {_month(months[last])}"


@dataclass(frozen=True, slots=True)
class _Window:
    """Months ``[first, stop)`` of a pair's series, as a statement names them."""

    first: int
    stop: int
    label: str
    """How a statement names it: "2025", or "January–August 2026" for a partial year."""
    partial: bool = False
    """A calendar year with fewer than 12 months of data."""


@dataclass(frozen=True, slots=True)
class YearChange:
    """A window against the same months a year earlier, in %.

    Attributes:
        article: The article's views.
        edition: The views of its whole edition.
        share: The attention share: ``(1 + article) / (1 + edition) − 1``.
    """

    article: float
    edition: float
    share: float


def _period(months: Sequence[date], first: int, stop: int) -> str:
    """How a statement names months[first:stop]: "2025", "January–August 2026"."""
    a, b = months[first], months[stop - 1]
    if a.year == b.year and a.month == 1 and b.month == 12:  # noqa: PLR2004
        return str(a.year)
    if a.year == b.year:
        return f"{MONTH_NAMES[a.month - 1]}–{MONTH_NAMES[b.month - 1]} {a.year}"
    return _span(months, first, stop - 1)


# -- series arithmetic -----------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Pair:
    """A pair's series ready for the detectors: share per million, unusual months marked."""

    history: PairHistory
    start: int
    """First month of the window the trend detectors read; the season reads them all."""
    shares: tuple[float | None, ...]
    plateau: tuple[int, int] | None
    flat_plateau: bool
    spikes: frozenset[int]
    profile: dict[int, float]
    """Calendar month -> its usual level against the year's, in % (medians over years)."""

    @property
    def n(self) -> int:
        return len(self.shares)

    def share(self, first: int, stop: int) -> float | None:
        """Share over months[first:stop]: total views over total edition views, per million."""
        views = edition = 0.0
        for k in range(max(first, 0), min(stop, self.n)):
            v, e = self.history.views[k], self.history.edition[k]
            if v is not None and e:
                views += v
                edition += e
        return views / edition * 1e6 if edition else None

    def views_mean(self, first: int, stop: int) -> float | None:
        values = [v for v in self.history.views[max(first, 0) : stop] if v is not None]
        return mean(values) if values else None

    def total(self, series: Sequence[float | None], first: int, stop: int) -> float:
        return sum(v for v in series[max(first, 0) : stop] if v is not None)

    def calendar_years(self) -> list[_Window]:
        """The calendar years of the trend window from its first January; the last may be partial.

        A year the window cuts at its start is left out: its missing months would read as a
        change of level.
        """
        months = self.history.months
        k = next((i for i in range(max(self.start, 0), self.n) if months[i].month == 1), None)
        out: list[_Window] = []
        while k is not None and k < self.n:
            stop = min(k + _YEAR, self.n)
            out.append(_Window(k, stop, _period(months, k, stop), partial=stop - k < _YEAR))
            k = stop
        return out

    def full_years(self) -> list[_Window]:
        return [y for y in self.calendar_years() if not y.partial]

    def now(self, settings: ObservationSettings) -> _Window | None:
        """The window "now" stands for: the last calendar year, partial or not, with enough months.

        With too few months in the last year, the last full year; without any calendar
        year (an article younger than a year from its first January), the months there are.
        """
        years = self.calendar_years()
        if years:
            last = years[-1]
            if not last.partial or last.stop - last.first >= settings.partial_months:
                return last
        full = [y for y in years if not y.partial]
        if full:
            return full[-1]
        first = max(self.start, 0)
        if first >= self.n:
            return None
        return _Window(first, self.n, _period(self.history.months, first, self.n))

    def against_year_before(self, window: _Window) -> YearChange | None:
        """``window`` against the same months a year earlier.

        A partial year is set against the same months, not the whole year before: its
        missing season would read as a fall. Both windows need every month's data.
        """
        h = self.history
        first, stop = window.first - _YEAR, window.stop - _YEAR
        if first < 0:
            return None
        months = (*range(first, stop), *range(window.first, window.stop))
        if any(h.views[k] is None or not h.edition[k] for k in months):
            return None
        views = self.total(h.views, window.first, window.stop), self.total(h.views, first, stop)
        edition = (
            self.total(h.edition, window.first, window.stop),
            self.total(h.edition, first, stop),
        )
        if not views[1]:
            return None
        article = views[0] / views[1]
        whole = edition[0] / edition[1]
        return YearChange(
            article=(article - 1) * 100,
            edition=(whole - 1) * 100,
            share=(article / whole - 1) * 100,
        )

    def peak_every_year(self, month: int, years: int) -> bool:
        """Whether ``month`` is among the two strongest of every year, over at least ``years``.

        Years are 12-month blocks counted back from the last month; months are read against
        the months around them (:func:`_relative`), bursts and plateaus left out. A block
        without ``month`` or with fewer than half its months read is not counted.
        """
        months = self.history.months
        skip = frozenset(k for k in range(self.n) if not self.usual(k))
        relative = _relative(self.shares, skip)
        counted = 0
        for back in range(self.n // _YEAR):
            stop = self.n - back * _YEAR
            block = [
                (r, months[k].month)
                for k in range(stop - _YEAR, stop)
                if (r := relative[k]) is not None
            ]
            if len(block) < _YEAR // 2 or month not in {m for _, m in block}:
                continue
            counted += 1
            strongest = {m for _, m in sorted(block, reverse=True)[:2]}
            if month not in strongest:
                return False
        return counted >= years

    def partial_bias(self, window: _Window) -> float:
        """How far (%) the months of ``window`` usually run from the topic's yearly level."""
        months = self.history.months
        return mean(self.profile[months[k].month] for k in range(window.first, window.stop))

    def usual(self, k: int) -> bool:
        return k not in self.spikes and not self.in_plateau(k)

    def in_plateau(self, k: int) -> bool:
        return self.plateau is not None and self.plateau[0] <= k <= self.plateau[1]


def _prepare(history: PairHistory, start: int, settings: ObservationSettings) -> _Pair:
    shares = tuple(
        v / e * 1e6 if v is not None and e else None
        for v, e in zip(history.views, history.edition, strict=True)
    )
    n = len(shares)
    known = [s for s in shares if s is not None]
    base = median(known) if known else 0.0
    high = [s is not None and base > 0 and s > settings.outlier * base for s in shares]
    plateau: tuple[int, int] | None = None
    k = 0
    while k < n:
        if not high[k]:
            k += 1
            continue
        j = k
        while j + 1 < n and high[j + 1]:
            j += 1
        longer = plateau is None or j - k > plateau[1] - plateau[0]
        if j - k + 1 >= settings.plateau_months and longer:
            plateau = (k, j)
        k = j + 1
    flat = False
    if plateau is not None:
        inside = [s for s in shares[plateau[0] : plateau[1] + 1] if s]
        flat = (
            len(inside) >= settings.flat_plateau_months
            and max(inside) / min(inside) < settings.flat_plateau_spread
        )
    loose = _profile(history.months, shares, skip=frozenset())
    spikes = frozenset(
        k
        for k in range(n)
        if (s := shares[k]) is not None
        and (level := _year_level(shares, k)) is not None
        and s > settings.outlier * level * (1 + loose[history.months[k].month] / 100)
        and not (plateau is not None and plateau[0] <= k <= plateau[1])
    )
    skip = spikes | (frozenset(range(plateau[0], plateau[1] + 1)) if plateau else frozenset())
    return _Pair(
        history=history,
        start=start,
        shares=shares,
        plateau=plateau,
        flat_plateau=flat,
        spikes=spikes,
        profile=_profile(history.months, shares, skip=skip),
    )


def _year_level(shares: Sequence[float | None], k: int) -> float | None:
    """The median share of the 12-month block (counted back from the end) holding month k."""
    n = len(shares)
    back = (n - 1 - k) // _YEAR
    stop = n - back * _YEAR
    block = [s for s in shares[max(stop - _YEAR, 0) : stop] if s is not None]
    return median(block) if block else None


def _relative(shares: Sequence[float | None], skip: frozenset[int]) -> list[float | None]:
    """Each month's share against the median of the 13 months centred on it.

    The centred median takes the trend out: in a series falling 40 % a year the first months
    of any year are higher than its last, which a comparison with the year's own median would
    read as a season. Months in ``skip`` are neither read nor counted in a window; a month
    without six months on either side, or with fewer than nine usual ones around it, has none.
    """
    n = len(shares)
    out: list[float | None] = [None] * n
    for k in range(_HALF_WINDOW, n - _HALF_WINDOW):
        s = shares[k]
        if s is None or k in skip:
            continue
        window = [
            v
            for j in range(k - _HALF_WINDOW, k + _HALF_WINDOW + 1)
            if j not in skip and (v := shares[j]) is not None
        ]
        if len(window) < _MIN_WINDOW:
            continue
        level = median(window)
        if level > 0:
            out[k] = s / level
    return out


def _profile(
    months: Sequence[date], shares: Sequence[float | None], *, skip: frozenset[int]
) -> dict[int, float]:
    """Each calendar month's level against the months around it, in %, as a median over years.

    Medians keep one extraordinary month from making a season; ``skip`` leaves out months
    already known to be out of the ordinary.
    """
    by_month: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    for k, r in enumerate(_relative(shares, skip)):
        if r is not None:
            by_month[months[k].month].append(r)
    return {m: (median(v) - 1) * 100 if v else 0.0 for m, v in by_month.items()}


# -- detectors -------------------------------------------------------------------------------


class _Detector:
    """Runs the detectors of one pair; each appends what its data show."""

    def __init__(self, pair: _Pair, settings: ObservationSettings) -> None:
        self.p = pair
        self.s = settings
        self.h = pair.history
        self.ed = edition_name(self.h.project)
        self.topic = self.h.topic
        self.out: list[Observation] = []
        self.long_dir = "unknown"
        self.last_change: float | None = None
        """The share's change of "now" against a year earlier (%), as ``vs_edition`` read it."""
        self.now_label = ""
        """How the statements name "now": "2025", "January–August 2026"."""
        self.year_change: YearChange | None = None
        """"Now" against the same months a year earlier, as ``vs_edition`` read it."""
        self.against = ""
        """What "now" is compared with: "2024", "the same months of 2025"."""

    def add(  # noqa: PLR0913 -- an observation's every field
        self,
        kind: str,
        weight: Weight,
        words: _Words,
        statement: str,
        key: str = "",
        *,
        month: date | None = None,
    ) -> None:
        suffix = f":{key}" if key else ""
        self.out.append(
            Observation(
                id=f"{kind}{suffix}:{self.h.pair}",
                kind=kind,
                pair=self.h.pair,
                weight=weight,
                statement=statement[0].upper() + statement[1:],
                numbers=tuple(words.quoted),
                month=month,
            )
        )

    def run(self) -> list[Observation]:
        self.unusual()
        self.size()
        self.long_term()
        self.vs_edition()
        self.season()
        self.spike()
        self.step()
        self.recent()
        self.verdict()
        return self.out

    # Each detector is small and independent; the order above is the order of the facts.

    def unusual(self) -> None:
        p = self.p
        if p.plateau is None or p.plateau[1] < p.start:
            return
        first, last = p.plateau
        w = _Words()
        months = p.history.months
        span = _span(months, first, last)
        length = last - first + 1
        if p.flat_plateau:
            self.add(
                "unusual",
                Weight.CAUTION,
                w,
                f"{self.topic} in {self.ed}: {span} its views stayed several times the usual "
                f"level, almost flat, for {length} months, then dropped back at once. A flat, "
                "abrupt run like this is probably automated traffic, not readers; comparisons "
                "that include those months overstate it.",
            )
        else:
            self.add(
                "wave",
                Weight.HIGH,
                w,
                f"{self.topic} in {self.ed}: {span} it was read several times as much as usual "
                f"for {length} months, then went back. A wave of attention (possibly "
                "news-driven) that did not last.",
            )

    def size(self) -> None:
        p, s = self.p, self.s
        w = _Words()
        window = p.now(s)
        now = None if window is None else p.views_mean(window.first, window.stop)
        if window is None or now is None:
            return
        text = (
            f"In {self.ed} the article on {self.topic} is opened {w.count(now)} times a month "
            f"in {window.label}"
        )
        share = p.share(window.first, window.stop)
        if share:
            text += (
                f": {w.per_million(share)} views per million views of the edition (its "
                "attention share, the size of interest comparable across editions)"
            )
        full = p.full_years()
        if full and full[0].first < window.first:
            then = p.views_mean(full[0].first, full[0].stop)
            if then:
                text += (
                    f". In {full[0].label} it was opened {w.count(then)} times a month: "
                    f"{w.ratio(now / then)}"
                )
        text += "."
        if window.partial and p.n >= s.min_long_years * _YEAR:
            bias = p.partial_bias(window)
            if abs(bias) >= s.partial_bias:
                text += (
                    f" {window.label} is not a full year, and for this topic these months "
                    f"usually run {w.pct(bias)} against its yearly level: set it against full "
                    "years with care."
                )
        self.add("size", Weight.HIGH, w, text)

    def long_term(self) -> None:
        p, s = self.p, self.s
        full = p.full_years()
        if len(full) < s.min_long_years:
            return
        shares = [p.share(y.first, y.stop) for y in full]
        if any(x is None or x <= 0 for x in shares):
            return
        ys = [x for x in shares if x is not None]
        first_year, last_year = full[0].label, full[-1].label
        steps = len(ys) - 1
        falls = sum(1 for a, b in pairwise(ys) if b < a * (1 - s.steady_step))
        rises = sum(1 for a, b in pairwise(ys) if b > a * (1 + s.steady_step))
        peak = max(range(len(ys)), key=ys.__getitem__)
        change = ys[-1] / ys[0]
        wave = 0 < peak < len(ys) - 1 and ys[peak] > ys[0] * s.wave_peak
        w = _Words()
        ed = self.ed
        years = f"{first_year}–{last_year}"
        if wave and ys[-1] < ys[peak] * s.wave_fall:
            self.long_dir = "wave"
            text = (
                f"Its attention share in {ed} was highest in {full[peak].label} and has fallen "
                f"since: in {last_year} it was {w.ratio(ys[-1] / ys[peak])} at that peak."
            )
            if ys[peak] > ys[0] * 1.3:
                text += " A wave that has passed, not a lasting rise."
            self.add("long_term", Weight.HIGH, w, text)
        elif change < s.long_change and falls >= steps - 1:
            self.long_dir = "decline"
            self.add(
                "long_term",
                Weight.HIGH,
                w,
                f"Its attention share in {ed} has fallen almost every year ({falls} of "
                f"{steps} year-on-year steps, {years}); in {last_year} it was "
                f"{w.ratio(change)} in {first_year}. A long, steady decline, not a recent dip.",
            )
        elif change > 1 / s.long_change and rises >= steps - 1:
            self.long_dir = "rise"
            self.add(
                "long_term",
                Weight.HIGH,
                w,
                f"Its attention share in {ed} has risen almost every year ({rises} of "
                f"{steps} year-on-year steps, {years}); in {last_year} it was "
                f"{w.ratio(change)} in {first_year}. A long, steady rise.",
            )
        elif change < s.long_change or change > 1 / s.long_change:
            self.long_dir = "decline" if change < 1 else "rise"
            kind = "fall" if change < 1 else "rise"
            self.add(
                "long_term",
                Weight.HIGH,
                w,
                f"Its attention share in {ed} in {last_year} was {w.ratio(change)} in "
                f"{first_year}: a large {kind} overall ({years}), though not every year.",
            )
        else:
            self.long_dir = "flat"
            self.add(
                "long_term",
                Weight.MEDIUM,
                w,
                f"Its attention share in {ed} stayed in the same range over {years}: in "
                f"{last_year} it was {w.ratio(change)} in {first_year}.",
            )

    def vs_edition(self) -> None:
        p, s = self.p, self.s
        if p.n - p.start < s.min_trend_months:
            return
        window = p.now(s)
        change = None if window is None else p.against_year_before(window)
        if window is None or change is None:
            return
        a, e, sh = change.article, change.edition, change.share
        self.last_change = sh
        self.year_change = change
        self.now_label = window.label
        w = _Words()
        ed, topic = self.ed, self.topic
        earlier = self.h.months[window.first].year - 1
        against = f"the same months of {earlier}" if window.partial else str(earlier)
        self.against = against
        when = f"In {window.label} (against {against})"
        if e < -s.edition_moves and sh < -s.moves:
            text = (
                f"{when} {ed} as a whole was read less ({w.pct(e)} views), and the article on "
                f"{topic} fell more than that ({w.pct(a)} views), so its attention share fell "
                f"({w.pct(sh)}). Only part of the fall is Wikipedia losing readers; the topic "
                "itself is read less. (This compares the article with the edition over the "
                "year; only the recent months tell whether the fall is quickening.)"
            )
        elif e < -s.edition_moves and abs(sh) <= s.moves:
            text = (
                f"{when} {topic} is read less ({w.pct(a)} views), but {ed} as a whole fell about "
                f"as much ({w.pct(e)}); its attention share barely changed ({w.pct(sh)}). The "
                "fall in views comes from Wikipedia losing readers, not from the topic."
            )
        elif e < -s.edition_moves:
            held = "held up" if a > -s.edition_moves else "fell less"
            text = (
                f"{when} {ed} as a whole was read less ({w.pct(e)}), yet {topic} {held} "
                f"({w.pct(a)} views): its attention share rose {w.pct(sh)}. The topic gains "
                "attention against a shrinking Wikipedia."
            )
        elif sh < -s.moves:
            text = (
                f"{when} {topic} is read less ({w.pct(a)} views) while {ed} as a whole changed "
                f"{w.pct(e)}: the topic itself loses attention (attention share {w.pct(sh)})."
            )
        elif sh > s.moves:
            text = (
                f"{when} {topic} gained attention against {ed}: views {w.pct(a)}, the edition "
                f"{w.pct(e)}, attention share {w.pct(sh)}."
            )
        else:
            self.add(
                "vs_edition",
                Weight.LOW,
                w,
                f"{when} {topic} moved with {ed}: views {w.pct(a)}, the edition {w.pct(e)}, "
                f"attention share {w.pct(sh)}.",
            )
            return
        self.add("vs_edition", Weight.HIGH, w, text)

    def season(self) -> None:
        p, s = self.p, self.s
        if p.n < s.min_long_years * _YEAR:
            return
        prof = p.profile
        top = max(prof, key=lambda m: prof[m])
        low = min(prof, key=lambda m: prof[m])
        summer = mean(prof[m] for m in _SUMMER)
        before = MONTH_NAMES[(top - 2) % 12]
        w = _Words()
        topic, ed = self.topic, self.ed
        # A timing or an audience follows from a season only when its peak came every year,
        # over enough years: two or three repetitions of a month are limited evidence.
        firm = p.peak_every_year(top, s.season_years)
        limited = (
            " With this few years of data, or a peak that moved between months, this is "
            "limited evidence."
        )
        if prof[top] > s.school_peak and top in _SCHOOL_PEAKS and summer < s.school_summer:
            if not firm:
                self.add(
                    "season",
                    Weight.LOW,
                    w,
                    f"{topic} in {ed} tends to peak in {MONTH_NAMES[top - 1]} "
                    f"({w.pct(prof[top])} against its usual level) and to drop in summer "
                    f"({MONTH_NAMES[low - 1]} {w.pct(prof[low])}), like the school year." + limited,
                )
                return
            self.add(
                "season",
                Weight.HIGH,
                w,
                f"Every year {topic} in {ed} peaks in {MONTH_NAMES[top - 1]} "
                f"({w.pct(prof[top])} against its usual level) and drops in summer "
                f"({MONTH_NAMES[low - 1]} {w.pct(prof[low])}). That is the school-year rhythm: "
                "the readers are probably largely school students.",
            )
            self.add(
                "decision",
                Weight.DECISION,
                _Words(),
                f"The readers in {ed} are probably largely school students: an offer tied to "
                "the school year (for students, or for parents and teachers) fits the data "
                f"better than one for adults; be ready by {before}.",
                key="audience",
            )
        elif prof[top] - prof[low] > s.rhythm:
            strong = prof[top] > s.rhythm_peak and firm
            self.add(
                "season",
                Weight.MEDIUM if strong else Weight.LOW,
                w,
                f"{topic} in {ed} has a yearly rhythm: strongest in {MONTH_NAMES[top - 1]} "
                f"({w.pct(prof[top])} against its usual level), weakest in "
                f"{MONTH_NAMES[low - 1]} ({w.pct(prof[low])})." + ("" if firm else limited),
            )
            if strong:
                self.add(
                    "decision",
                    Weight.DECISION,
                    _Words(),
                    f"Interest in {topic} in {ed} peaks every {MONTH_NAMES[top - 1]}: anything "
                    f"launched or promoted should be ready by {before}.",
                    key="timing",
                )
        else:
            self.add(
                "season",
                Weight.LOW,
                w,
                f"{topic} in {ed} has no marked season: typical months stay within "
                f"{w.pct(prof[low])} … {w.pct(prof[top])} of the usual level.",
            )

    def spike(self) -> None:
        p = self.p
        spikes = [k for k in p.spikes if k >= p.start]
        if not spikes:
            return
        k = max(spikes, key=lambda i: p.shares[i] or 0.0)
        self.add(
            "spike",
            Weight.MEDIUM,
            _Words(),
            f"In {_month(p.history.months[k])} {self.topic} was read several times as much as "
            f"that month usually brings in {self.ed}, and the next month it was back: a one-off "
            "burst, possibly news. A burst like this is not lasting interest.",
            month=p.history.months[k],
        )

    def step(self) -> None:
        p, s, h = self.p, self.s, self.h
        adjusted = [
            x / (1 + p.profile[h.months[k].month] / 100) if x is not None and p.usual(k) else None
            for k, x in enumerate(p.shares)
        ]
        best: tuple[int, float] | None = None
        for i in range(max(p.start, 0) + _STEP_HALF, p.n - _STEP_HALF + 1):
            ratio = _level_ratio(adjusted, i)
            if ratio is not None and (best is None or abs(math.log(ratio)) > abs(best[1])):
                best = (i, math.log(ratio))
        if best is None or abs(best[1]) < math.log(s.step):
            return
        i, d = best
        later = [x for x in adjusted[i:] if x]
        earlier = [x for x in adjusted[:i] if x]
        stays = (median(later) < median(earlier)) == (d < 0)
        edition = _level_ratio(list(h.edition), i)
        w = _Words()
        text = (
            f"The biggest step in {self.topic}'s level in {self.ed} came in "
            f"{_month(h.months[i])}: over the six months from then its attention share was "
            f"{w.ratio(math.exp(d))} in the six months before (seasonal rhythm removed)"
            + (", and the level stayed there." if stays else ".")
        )
        if edition is not None and abs(math.log(edition)) > math.log(s.edition_step):
            text += (
                f" {self.ed} as a whole changed at the same time, so the step may come from how "
                "the edition is counted or reached, not from the topic."
            )
        weight = Weight.HIGH if abs(d) > math.log(s.strong_step) else Weight.MEDIUM
        self.add("step", weight, w, text, month=h.months[i])

    def recent(self) -> None:  # noqa: PLR0912 -- one wording per case
        p, s = self.p, self.s
        if p.n - p.start < _YEAR + _RECENT or self.last_change is None:
            return
        now = p.share(p.n - _RECENT, p.n)
        then = p.share(p.n - _YEAR - _RECENT, p.n - _YEAR)
        if not now or not then:
            return
        r = (now / then - 1) * 100
        sh = self.last_change
        months = p.history.months
        span = (
            f"{MONTH_NAMES[months[p.n - _RECENT].month - 1]}–"
            f"{MONTH_NAMES[months[p.n - 1].month - 1]} {months[p.n - 1].year}"
        )
        w = _Words()
        figures = (
            f"({w.pct(r)} share against the same months a year earlier; {self.now_label}: "
            f"{w.pct(sh)})"
        )
        weight = Weight.MEDIUM
        if sh < -s.moves:
            if r > s.edition_moves:
                text = (
                    f"In the last three months ({span}) the fall stopped: the share is higher "
                    f"than a year earlier {figures}. Three months are too few to call a turn."
                )
                weight = Weight.HIGH
            elif r > -s.moves:
                text = f"In the last three months ({span}) the fall levelled off {figures}."
            elif r > sh + s.moves:
                text = (
                    f"In the last three months ({span}) the fall continues, but more slowly "
                    f"than in {self.now_label} {figures}."
                )
            elif r < sh - s.moves:
                text = f"In the last three months ({span}) the fall speeds up {figures}."
                weight = Weight.HIGH
            else:
                text = (
                    f"In the last three months ({span}) the fall continues at about the same "
                    f"pace {figures}."
                )
                weight = Weight.LOW
        elif sh > s.moves:
            if r < -s.edition_moves:
                text = (
                    f"In the last three months ({span}) the rise stopped: the share is lower "
                    f"than a year earlier {figures}."
                )
                weight = Weight.HIGH
            elif r < sh - s.moves:
                text = (
                    f"In the last three months ({span}) the rise continues, but more slowly "
                    f"{figures}."
                )
            else:
                text = f"In the last three months ({span}) the rise continues {figures}."
                weight = Weight.LOW
        elif abs(r) > s.moves * 1.5:
            direction = "up" if r > 0 else "down"
            text = (
                f"In the last three months ({span}) the share moved {direction} after a flat "
                f"year {figures}; three months are too few to call a turn."
            )
        else:
            text = f"The last three months ({span}) show no change {figures}."
            weight = Weight.LOW
        self.add("recent", weight, w, text)

    def verdict(self) -> None:
        """What Wikipedia signals for the next check: the audience's direction and the share's.

        The views say whether the audience grows; the attention share whether it grows of its
        own or with its Wikipedia. Wikipedia is a signal to check further, never a decision
        to invest.
        """
        change, s = self.year_change, self.s
        if change is None:
            return
        topic, ed = self.topic, self.ed
        views = views_direction(change.article, s)
        move = share_move(change.share, s)
        if views == "up":
            text = {
                "gained": f"Interest in {topic} in {ed} grows, faster than its Wikipedia: a "
                "signal worth checking further.",
                "held": f"The audience of {topic} in {ed} grows with its Wikipedia: a growing "
                "audience worth checking further, though not a rise of its own.",
                "lost": f"The audience of {topic} in {ed} grows, but more slowly than its "
                "Wikipedia: a weak signal.",
            }[move]
        elif views == "down" and move == "lost":
            text = (
                f"Interest in {topic} in {ed} is shrinking, faster than its Wikipedia: "
                "Wikipedia gives no growth signal to check."
            )
        elif views == "down":
            text = (
                f"The article on {topic} in {ed} is read less, but no more than its Wikipedia "
                "as a whole: the interest is there, with no sign of growth."
            )
        elif self.long_dir in ("decline", "wave"):
            text = (
                f"Interest in {topic} in {ed} holds steady now after a longer decline: "
                "Wikipedia gives no growth signal to check."
            )
        else:
            text = {
                "gained": f"Interest in {topic} in {ed} holds steady while its Wikipedia is read "
                "less: it keeps its readers, with no sign of growth.",
                "held": f"Interest in {topic} in {ed} holds steady: Wikipedia shows neither "
                "growth nor a decline.",
                "lost": f"Interest in {topic} in {ed} holds steady while its Wikipedia grows: no "
                "growth of its own.",
            }[move]
        self.add("decision", Weight.DECISION, _Words(), text, key="verdict")


def _level_ratio(values: Sequence[float | None], i: int) -> float | None:
    """Mean of the six months from ``i`` over the mean of the six before, if enough data.

    Months out of the ordinary are ``None`` already, so means place a step at its month.
    """
    before = [x for x in values[max(i - _STEP_HALF, 0) : i] if x]
    after = [x for x in values[i : i + _STEP_HALF] if x]
    enough = _STEP_HALF - 2
    if len(before) < enough or len(after) < enough:
        return None
    return mean(after) / mean(before)


# -- across pairs ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Standing:
    """A pair's level "now" (its last calendar year) and how it moved a year on."""

    pair: _Pair
    share: float
    views: float
    change: float | None
    """The share's change against a year earlier (%)."""
    period: str
    """The months "now" covers, as the statement names them."""
    year: YearChange | None = None
    """"Now" against the same months a year earlier: views, edition, share."""
    against: str = ""
    """What "now" is compared with: "2024", "the same months of 2025"."""


def _standing(pair: _Pair, detector: _Detector, settings: ObservationSettings) -> _Standing | None:
    window = pair.now(settings)
    if window is None:
        return None
    share = pair.share(window.first, window.stop)
    views = pair.views_mean(window.first, window.stop)
    if not share or not views:
        return None
    return _Standing(
        pair,
        share,
        views,
        detector.last_change,
        window.label,
        year=detector.year_change,
        against=detector.against,
    )


_VIEWS_WORDS = {"up": "went up", "flat": "held", "down": "went down"}


def _editions(a: _Standing, b: _Standing, settings: ObservationSettings) -> list[Observation]:
    """One topic in two editions over the same months, compared rather than told twice.

    The audience (views a month), the attention share (the same against the size of each
    Wikipedia), where the views went and whether each article gained, held or lost its share,
    against the same months a year earlier; then what that means for the next check.
    """
    w = _Words()
    topic = a.pair.history.topic
    big, small = (a, b) if a.views >= b.views else (b, a)

    def name(x: _Standing) -> str:
        return edition_name(x.pair.history.project)

    period = f"In {a.period}" if a.period == b.period else f"In {a.period} and {b.period}"
    similar = big.views / small.views < settings.same_size
    text = (
        _audiences(w, topic, (big, small), period, name, settings=settings)
        + " "
        + _shares(w, topic, (big, small), name, settings, similar=similar)
    )
    if big.year is not None and small.year is not None:
        text += " " + _directions(w, (big, small), name, settings)
    topic_id = a.pair.history.topic_id
    hint = _where_to_look(topic, (big, small), name, settings, similar=similar)
    return [
        Observation(
            id=f"editions:{topic_id}",
            kind="editions",
            pair=None,
            weight=Weight.HIGH,
            statement=text,
            numbers=tuple(w.quoted),
        ),
        Observation(
            id=f"decision:editions:{topic_id}",
            kind="decision",
            pair=None,
            weight=Weight.DECISION,
            statement=hint[0].upper() + hint[1:],
        ),
    ]


_Two = tuple["_Standing", "_Standing"]
"""The larger audience first, then the smaller one."""


def _audiences(  # noqa: PLR0913 -- the two sides and how to name them
    w: _Words,
    topic: str,
    two: _Two,
    period: str,
    name: Callable[[_Standing], str],
    *,
    settings: ObservationSettings,
) -> str:
    """Where the audience is larger, in views a month."""
    big, small = two
    ratio = big.views / small.views
    if ratio < settings.same_size:
        return (
            f"{period} the article on {topic} is opened about as often in {name(big)} as in "
            f"{name(small)} ({w.count(big.views)} and {w.count(small.views)} times a month)."
        )
    much = "much " if ratio >= settings.large_audience else ""
    return (
        f"{period} the article on {topic} is opened {w.count(big.views)} times a month in "
        f"{name(big)} against {w.count(small.views)} in {name(small)}: {name(big)} is the "
        f"{much}larger audience ({w.times(ratio)})."
    )


def _shares(  # noqa: PLR0913 -- the two sides and how to name them
    w: _Words,
    topic: str,
    two: _Two,
    name: Callable[[_Standing], str],
    settings: ObservationSettings,
    *,
    similar: bool,
) -> str:
    """Whether the gap in audience holds once each Wikipedia's size is taken into account."""
    big, small = two
    ratio = big.share / small.share
    lead, other = (big, small) if ratio >= 1 else (small, big)
    shares = (  # the edition that gives the topic more attention first
        f"({w.per_million(lead.share)} against {w.per_million(other.share)} views per million "
        "views of each Wikipedia: the attention share)"
    )
    same = 1 / settings.same_size < ratio < settings.same_size
    if similar:
        if same:
            return (
                "Relative to the size of each Wikipedia the attention is about the same too "
                f"{shares}."
            )
        return (
            f"Relative to the size of each Wikipedia, {topic} gets "
            f"{w.times(max(ratio, 1 / ratio))} attention in {name(lead)} as in {name(other)} "
            f"{shares}."
        )
    if ratio <= 1 / settings.same_size:
        return (
            f"Relative to the size of each Wikipedia it is the other way round: {name(small)} "
            f"gives the topic more attention {shares}; its Wikipedia is smaller."
        )
    if same:
        return (
            f"Relative to the size of each Wikipedia the gap almost disappears {shares}: the "
            f"larger audience in {name(big)} comes from its larger Wikipedia."
        )
    narrows = ratio < big.views / small.views / 2
    return (
        f"Relative to the size of each Wikipedia the gap {'narrows' if narrows else 'holds'}: "
        f"{name(big)} gives the topic {w.times(ratio)} attention {shares}."
    )


def _directions(
    w: _Words,
    two: _Two,
    name: Callable[[_Standing], str],
    settings: ObservationSettings,
) -> str:
    """Where the views went and whether each article kept its share, a year on."""
    big, small = two
    assert big.year is not None
    assert small.year is not None
    against = big.against if big.against == small.against else "a year earlier"
    x, y = big.year.article, small.year.article
    dx, dy = views_direction(x, settings), views_direction(y, settings)
    if dx == dy != "flat":
        faster = big if abs(x) > abs(y) else small
        pace = (
            f", more sharply in {name(faster)}"
            if abs(x - y) > settings.moves
            else ", at about the same pace"
        )
        verb = "read less" if dx == "down" else "read more"
        text = (
            f"Against {against} both are {verb}: {name(big)} {w.pct(x)}, {name(small)} "
            f"{w.pct(y)} views{pace}."
        )
    elif dx == dy:
        text = f"Against {against} both hold steady ({w.pct(x)} and {w.pct(y)} views)."
    else:
        text = (
            f"Against {against} the views {_VIEWS_WORDS[dx]} in {name(big)} ({w.pct(x)}) and "
            f"{_VIEWS_WORDS[dy]} in {name(small)} ({w.pct(y)})."
        )
    mx, my = share_move(big.year.share, settings), share_move(small.year.share, settings)
    if mx == my:
        return f"{text} Against its own Wikipedia the article {mx} attention share in both."
    return (
        f"{text} Against its own Wikipedia it {mx} attention share in {name(big)} and {my} it "
        f"in {name(small)}."
    )


def _where_to_look(  # noqa: PLR0911 -- one wording per case
    topic: str,
    two: _Two,
    name: Callable[[_Standing], str],
    settings: ObservationSettings,
    *,
    similar: bool,
) -> str:
    """The trade-off for the next check: a larger audience against a growing one.

    Wikipedia is a signal to check further, never a decision; a small audience that grows is
    an early signal whose low base may inflate it.
    """
    big, small = two
    if big.year is None or small.year is None:
        if similar:
            return f"The two audiences of {topic} are about the same size."
        return (
            f"{name(big)} is the larger audience for {topic}: the natural place to start checking."
        )
    big_up = views_direction(big.year.article, settings) == "up"
    small_up = views_direction(small.year.article, settings) == "up"
    if similar:
        if big_up and small_up:
            return (
                f"The two audiences of {topic} are about the same size and both grow: a signal "
                "worth checking further in either."
            )
        if big_up or small_up:
            grows = big if big_up else small
            return (
                f"The two audiences of {topic} are about the same size, and only {name(grows)} "
                "grows: the stronger signal to check further."
            )
        return (
            f"The two audiences of {topic} are about the same size, and neither grows: "
            "Wikipedia gives no growth signal to check."
        )
    if big_up:
        also = f"; {name(small)} grows too, from a smaller base" if small_up else ""
        return (
            f"{name(big)} is the larger audience for {topic} and it grows{also}: the stronger "
            "signal to check further."
        )
    if small_up:
        return (
            f"{name(big)} offers the larger existing audience, but only {name(small)} grows: an "
            "early signal there; check whether its small base inflates the growth."
        )
    return (
        f"{name(big)} offers the larger existing audience, but neither edition shows growing "
        f"interest in {topic}."
    )


def _topics(standings: Sequence[_Standing], settings: ObservationSettings) -> list[Observation]:
    """Several of the user's topics in one edition: which gets more attention, which moves."""
    ranked = sorted(standings, key=lambda x: x.share, reverse=True)
    top = ranked[0]
    project = top.pair.history.project
    language = top.pair.history.language
    ed = edition_name(project)
    w = _Words()
    name = top.pair.history.topic
    parts = []
    for x in ranked[1:]:
        ratio = top.share / x.share
        if ratio < settings.same_size:
            parts.append(f"{x.pair.history.topic} gets about as much as {name}")
        else:
            parts.append(f"{name} gets {w.times(ratio)} as {x.pair.history.topic}")
    text = f"In {ed}, {name} gets the most attention of the topics asked about"
    if parts:
        text += " (relative to the edition): " + "; ".join(parts)
    text += "."
    moving = [x for x in ranked if x.change is not None]
    if moving:
        text += f" The share in {top.period} against a year earlier: " + ", ".join(
            f"{x.pair.history.topic} {w.pct(x.change)}"  # type: ignore[arg-type]
            for x in moving
        )
        text += "."
    out = [
        Observation(
            id=f"topics:{language}",
            kind="topics",
            pair=None,
            weight=Weight.HIGH,
            statement=text,
            numbers=tuple(w.quoted),
        )
    ]
    rising = [x for x in moving if x.change is not None and x.change > settings.moves]
    falling = [x for x in moving if x.change is not None and x.change < -settings.moves]
    if rising and falling:
        names = ", ".join(x.pair.history.topic for x in rising)
        out.append(
            Observation(
                id=f"decision:topics:{language}",
                kind="decision",
                pair=None,
                weight=Weight.DECISION,
                statement=(
                    f"In {ed} attention grows for {names} while other topics asked about lose it: "
                    f"{names} is the stronger candidate there."
                ),
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class YearLevel:
    """The attention share and views of one calendar year, as the observations read them.

    Attributes:
        year: The calendar year.
        first: Its first month with data in the window.
        last: Its last month in the window.
        share: Views per million views of the edition over those months.
        views: Mean monthly views over those months.
        partial: Fewer than 12 months (the last year of the data).
        change: Against the same months a year earlier, as ``vs_edition`` reads it; ``None``
            without a year of data before.
    """

    year: int
    first: date
    last: date
    share: float
    views: float
    partial: bool
    change: YearChange | None = None


def year_levels(
    history: PairHistory,
    *,
    trend_start: date | None = None,
    settings: ObservationSettings = _DEFAULT,
) -> list[YearLevel]:
    """The calendar years the observations read for ``history``, for a chart to draw.

    The same windows as ``size`` and ``long_term``: from the first January of the window, a
    partial last year only with enough months to stand for "now".
    """
    trimmed = _from_first_data(history)
    if trimmed is None:
        return []
    pair = _prepare(trimmed, _index_of(trimmed.months, trend_start), settings)
    months = trimmed.months
    out: list[YearLevel] = []
    for window in pair.calendar_years():
        if window.partial and window.stop - window.first < settings.partial_months:
            continue
        share = pair.share(window.first, window.stop)
        views = pair.views_mean(window.first, window.stop)
        if share is None or views is None:
            continue
        out.append(
            YearLevel(
                year=months[window.first].year,
                first=months[window.first],
                last=months[window.stop - 1],
                share=share,
                views=views,
                partial=window.partial,
                change=pair.against_year_before(window),
            )
        )
    return out


def observe(
    histories: Sequence[PairHistory],
    *,
    trend_start: date | None = None,
    settings: ObservationSettings = _DEFAULT,
) -> list[Observation]:
    """Every observation the series support, most important first within each pair.

    Args:
        histories: One per (topic, edition) with an article, over the whole window read
            (the season uses all of it).
        trend_start: First month the trend detectors read; ``None`` reads the whole window.
            A period the user named is read on its own.
        settings: Detector thresholds.
    """
    trimmed = [t for h in histories if (t := _from_first_data(h)) is not None]
    prepared = [_prepare(h, _index_of(h.months, trend_start), settings) for h in trimmed]
    out: list[Observation] = []
    detectors: dict[str, _Detector] = {}
    for pair in prepared:
        detector = _Detector(pair, settings)
        found = detector.run()
        detectors[pair.history.pair] = detector
        out.extend(sorted(found, key=lambda o: _ORDER[o.weight]))
    # A substitute measures another subject: it is never set against the topic.
    standings = {
        p.history.pair: s
        for p in prepared
        if not p.history.substitute
        and (s := _standing(p, detectors[p.history.pair], settings)) is not None
    }
    by_topic: dict[str, list[_Standing]] = {}
    by_edition: dict[str, list[_Standing]] = {}
    for s in standings.values():
        by_topic.setdefault(s.pair.history.topic_id, []).append(s)
        by_edition.setdefault(s.pair.history.project, []).append(s)
    for group in by_topic.values():
        if len(group) == 2:  # noqa: PLR2004
            out.extend(_editions(group[0], group[1], settings))
    for group in by_edition.values():
        if len(group) >= 2:  # noqa: PLR2004
            out.extend(_topics(group, settings))
    if len(by_topic) == 1:
        headline = _headline(next(iter(by_topic.values())), settings)
        if headline is not None:
            out.append(headline)
    return out


_ONE_EDITION = {
    ("up", "gained"): "is growing, faster than its Wikipedia",
    ("up", "held"): "is growing with its Wikipedia",
    ("up", "lost"): "is growing, but more slowly than its Wikipedia",
    ("down", "lost"): "is falling, faster than its Wikipedia",
    ("down", "held"): "is falling with its Wikipedia as a whole",
    ("down", "gained"): "is falling, but less than its Wikipedia as a whole",
}
_GROUP_WORDS = {"up": "growing", "down": "falling", "flat": "holding steady"}


def _headline(group: Sequence[_Standing], settings: ObservationSettings) -> Observation | None:
    """The answer in one sentence without numbers, over the window of the charts.

    For one topic: where its views went against the same months a year earlier, in each
    edition, and for one edition whether that beat its Wikipedia. The template text uses it
    as its headline; the agent may write its own.
    """
    moved = [x for x in group if x.year is not None]
    if not moved:
        return None
    topic = moved[0].pair.history.topic
    directions = {
        id(x): views_direction(x.year.article, settings) for x in moved if x.year is not None
    }
    if len(moved) == 1:
        (only,) = moved
        assert only.year is not None
        direction = directions[id(only)]
        move = share_move(only.year.share, settings)
        what = _ONE_EDITION.get((direction, move), "is holding steady")
        text = f"Interest in {topic} in {edition_name(only.pair.history.project)} {what}."
    elif len(set(directions.values())) == 1:
        direction = next(iter(directions.values()))
        scope = "both editions" if len(moved) == 2 else "every edition"  # noqa: PLR2004
        text = f"Interest in {topic} is {_GROUP_WORDS[direction]} in {scope}"
        if direction != "flat" and len(moved) == 2:  # noqa: PLR2004
            a, b = moved
            assert a.year is not None
            assert b.year is not None
            if abs(a.year.article - b.year.article) > settings.moves:
                sharper = a if abs(a.year.article) > abs(b.year.article) else b
                how = "more sharply" if direction == "down" else "faster"
                text += f", {how} in {edition_name(sharper.pair.history.project)}"
            else:
                text += ", at about the same pace"
        text += "."
    else:
        parts = [
            f"{_GROUP_WORDS[d]} in "
            + " and ".join(
                edition_name(x.pair.history.project) for x in moved if directions[id(x)] == d
            )
            for d in ("up", "flat", "down")
            if d in directions.values()
        ]
        text = f"Interest in {topic} is " + "; ".join(parts) + "."
    return Observation(
        id=f"headline:{moved[0].pair.history.topic_id}",
        kind="headline",
        pair=None,
        weight=Weight.CONTEXT,
        statement=text[0].upper() + text[1:],
    )


def _from_first_data(history: PairHistory) -> PairHistory | None:
    """``history`` from its first month with data.

    An article younger than the window, or a window longer than the data, must not read as
    years of zero interest.
    """
    first = next(
        (
            k
            for k, (v, e) in enumerate(zip(history.views, history.edition, strict=True))
            if v is not None and e
        ),
        None,
    )
    if first is None:
        return None
    return replace(
        history,
        months=history.months[first:],
        views=history.views[first:],
        edition=history.edition[first:],
    )


def _index_of(months: Sequence[date], start: date | None) -> int:
    if start is None:
        return 0
    return next((i for i, m in enumerate(months) if m >= start), len(months))
