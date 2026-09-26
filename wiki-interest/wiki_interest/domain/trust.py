"""The analysis window's verdict for one series, and how far it can be trusted.

The report answers for the months the user asked about (the *analysis window*); the longer
history the charts show is context. This module turns a pair's monthly attention share into
a verdict over the window: ``growing``, ``stable``, ``declining`` or ``insufficient_data``.

How the verdict is read:

- The share is read with its seasonal rhythm divided out and unusual months (bursts,
  plateaus, and months that one day dominates) left out.
- A step inside the window (a lasting change of level, see
  :func:`~wiki_interest.domain.observations.pair_steps`) splits it: when at least
  ``min_segment_months`` follow the last step, the trend is read from it on, so a drop that
  already happened is not read as a continuing fall ("stabilised after a drop").
- The trend is the Theil–Sen slope of the log share over that segment, in % a year; within
  ``stable_pct_per_year`` either way it is ``stable``. The reader sees the trend line's level
  at the segment's start and end, drawn on the chart.
- Too short a window or too few views a month give ``insufficient_data``.

Every threshold lives in :class:`TrustSettings`; ``method.md`` lists them.
"""

from __future__ import annotations

import math
import random
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from itertools import pairwise
from statistics import mean, median, pstdev
from typing import TYPE_CHECKING

from wiki_interest.domain.trend_tests import pairwise_median_slope

if TYPE_CHECKING:
    # Only for annotations: the observations read the verdicts this module gives.
    from wiki_interest.domain.observations import PairHistory, Step

__all__ = [
    "Breakpoint",
    "BreakpointVerdict",
    "Confidence",
    "Reason",
    "TrendVerdict",
    "Trust",
    "TrustSettings",
    "WindowTrend",
    "assess_trust",
    "bootstrap_ci",
    "breakpoint_verdict",
    "control_step",
    "control_trend",
    "day_spike_months",
    "segment_slope",
    "signal_to_noise",
    "theil_sen",
    "window_trend",
    "yoy_counts",
]

_YEAR = 12
_PERCENT = 100.0
_HALF = 6
"""Months on each side of a step: the observations' step detector reads six against six."""


class TrendVerdict(StrEnum):
    """Where a series' attention share went over the analysis window."""

    GROWING = "growing"
    STABLE = "stable"
    DECLINING = "declining"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True, slots=True)
class TrustSettings:
    """Every threshold of the window's verdict and of the trust in it.

    Attributes:
        stable_pct_per_year: A trend within this many % a year either way is ``stable``. Ten
            per cent a year is about the year-to-year noise of a mid-sized article's share
            (the calendar-year detectors use the same 10 % for a move), and below what a
            product decision would act on.
        min_window_months: Fewer months in the window give ``insufficient_data``: under a
            year the seasonal rhythm and the trend cannot be told apart.
        min_segment_months: Months a step inside the window must leave after it before the
            trend is read from it on; fewer, and the whole window is read. More than a year:
            a trend over one seasonal cycle reads the season (a school-year topic after a
            September step "grew" 85 % a year while its views fell by half, final v0.2 run).
        split_step: Ratio of the six months after a month to the six before (seasonal rhythm
            removed) that splits the window's trend. Lower than the ``step`` a history
            observation needs (1.35): inside a two-year window a 25 % shift within a year is
            already more than twice the stable band, and reading a trend across it would call
            one past drop a steady fall.
        volume_floor: Mean monthly views under which a series gives ``insufficient_data``:
            under a hundred views a month a handful of readers moves the share by tens of %.
        yoy_strong: Of the window's last twelve months, how many must sit on the verdict's
            side of the same month a year earlier for a strong signal (9 of 12: a coin
            would give it about 7 % of the time).
        snr_min: Least signal-to-noise ratio (the segment's change over the spread of its
            month-to-month changes) for a change to stand out of the noise.
        control_explains: Share of the article's change the control articles must match, the
            same way, for the change to be the edition's (a step then is an ``artifact``).
        day_spike_share: A month where one day took more than this share of the views is a
            spike month and is left out of the slope (20 %: six times a day's fair share).
        bootstrap_reps: Resamples of the block bootstrap of the slope's interval.
        bootstrap_block: Months per block: three keep a quarter's dependence together.
        bootstrap_seed: The bootstrap's seed: the same data give the same interval.
        ci_level: Coverage of the slope's interval (90 %).
        rename_months: Months either side of a step a move of the article counts for.
        control_sample: Articles in an edition's control basket.
        control_candidates: Articles drawn from the top list before the outliers are left
            out, so the basket keeps its size.
        control_top: How deep into the month's top list the basket draws.
        control_seed: The draw's seed: the same top list gives the same basket.
        control_ttl_days: Days a stored basket is used before it is built again.
        control_spike_multiple: A candidate whose reference month is over this many times
            its median of the twelve months before was in the top list for a burst: left out.
    """

    stable_pct_per_year: float = 10.0
    min_window_months: int = 12
    min_segment_months: int = 15
    split_step: float = 1.25
    volume_floor: float = 100.0
    yoy_strong: int = 9
    snr_min: float = 2.0
    control_explains: float = 0.5
    day_spike_share: float = 0.2
    bootstrap_reps: int = 1000
    bootstrap_block: int = 3
    bootstrap_seed: int = 20260926
    ci_level: float = 0.9
    rename_months: int = 1
    control_sample: int = 100
    control_candidates: int = 150
    control_top: int = 1000
    control_seed: int = 20260926
    control_ttl_days: int = 180
    control_spike_multiple: float = 3.0


_DEFAULT = TrustSettings()


@dataclass(frozen=True, slots=True)
class WindowTrend:
    """The verdict of one pair over the analysis window.

    Attributes:
        pair: ``<topic>/<language>``.
        verdict: Where the attention share went.
        window_start: First month of the analysis window.
        window_end: Its last month.
        segment_start: First month the trend reads: the window's, or the month of the
            step it starts after.
        step: The step inside the window the segment starts at, if any.
        slope_pct_per_year: The trend in % a year; ``None`` without enough data.
        level_start: The trend line's share (per million views of the edition) at
            ``segment_start``.
        level_end: The trend line's share at ``window_end``.
        views_avg: Mean monthly views over the window.
        excluded: Months of the segment left out of the trend (unusual ones).
        months: Months of the segment the trend was fitted on.
        intercept: The trend line's log share at month index 0 of the series (for drawing).
        slope_log: The trend line's slope in log share a month (for drawing).
        segment_index: Index of ``segment_start`` in the series.
        end_index: Index of ``window_end`` in the series.
        points: The (month index, log adjusted share) the trend was fitted on.
        window_index: Index of ``window_start`` in the series.
    """

    pair: str
    verdict: TrendVerdict
    window_start: date
    window_end: date
    segment_start: date
    step: Step | None = None
    slope_pct_per_year: float | None = None
    level_start: float | None = None
    level_end: float | None = None
    views_avg: float | None = None
    excluded: tuple[date, ...] = ()
    months: int = 0
    intercept: float | None = None
    slope_log: float | None = None
    segment_index: int = 0
    end_index: int = 0
    points: tuple[tuple[float, float], ...] = ()
    window_index: int = 0


def window_trend(  # noqa: PLR0913 -- the series, what is known of it, and the window
    history: PairHistory,
    *,
    window_start: date,
    steps: Sequence[Step],
    adjusted: Sequence[float | None],
    excluded: Collection[int] = (),
    settings: TrustSettings = _DEFAULT,
) -> WindowTrend:
    """The verdict of ``history`` over the months from ``window_start`` to its end.

    Args:
        history: The pair's monthly series, from its first month with data.
        window_start: First month of the analysis window.
        steps: The pair's steps at ``settings.split_step`` (see ``pair_steps``).
        adjusted: The share per month with the seasonal rhythm divided out, ``None`` where
            missing or unusual (see ``pair_steps``).
        excluded: Indices of further months to leave out of the trend (a day that dominates
            a month's views).
        settings: Thresholds.
    """
    months = history.months
    n = len(months)
    first = next((i for i, m in enumerate(months) if m >= window_start), n)
    end = months[-1] if months else window_start
    base = WindowTrend(
        pair=history.pair,
        verdict=TrendVerdict.INSUFFICIENT_DATA,
        window_start=months[first] if first < n else window_start,
        window_end=end,
        segment_start=months[first] if first < n else window_start,
        end_index=max(n - 1, 0),
        segment_index=first,
        window_index=first,
    )
    views = [v for v in history.views[first:] if v is not None]
    views_avg = mean(views) if views else None
    base = replace(base, views_avg=views_avg)
    if n - first < settings.min_window_months or views_avg is None:
        return base
    if views_avg < settings.volume_floor:
        return base
    inside = [s for s in steps if first < s.index and n - s.index >= settings.min_segment_months]
    step = inside[-1] if inside else None
    start = step.index if step else first
    skip = set(excluded)
    points = [
        (float(k), math.log(x))
        for k in range(start, n)
        if k not in skip and (x := adjusted[k]) is not None and x > 0
    ]
    left_out = tuple(months[k] for k in range(start, n) if k in skip or adjusted[k] is None)
    if len(points) < settings.min_window_months // 2:
        return replace(base, segment_start=months[start], segment_index=start, excluded=left_out)
    slope = pairwise_median_slope(points)
    intercept = median(y - slope * x for x, y in points)
    pct = (math.exp(slope * _YEAR) - 1) * _PERCENT
    if abs(pct) < settings.stable_pct_per_year:
        verdict = TrendVerdict.STABLE
    else:
        verdict = TrendVerdict.GROWING if pct > 0 else TrendVerdict.DECLINING
    return WindowTrend(
        pair=history.pair,
        verdict=verdict,
        window_start=months[first],
        window_end=end,
        segment_start=months[start],
        step=step,
        slope_pct_per_year=pct,
        level_start=math.exp(intercept + slope * start),
        level_end=math.exp(intercept + slope * (n - 1)),
        views_avg=views_avg,
        excluded=left_out,
        months=len(points),
        intercept=intercept,
        slope_log=slope,
        segment_index=start,
        end_index=n - 1,
        points=tuple(points),
        window_index=first,
    )


# -- trust ------------------------------------------------------------------------------------


class Confidence(StrEnum):
    """How far the window's verdict can be trusted (the rules: :func:`assess_trust`)."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class BreakpointVerdict(StrEnum):
    """What a step most probably is.

    ``artifact``: the control articles of the edition moved at least half as much the same
    month, or the article was renamed then: a change of counting or of title, not of
    interest. ``real``: neither. ``unknown``: no control data around that month.
    """

    REAL = "real"
    ARTIFACT = "artifact"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class Reason:
    """One short, machine-made reason behind a confidence level: a code and its numbers."""

    code: str
    params: tuple[tuple[str, float | int | str], ...] = ()

    def get(self, name: str) -> float | int | str | None:
        """The parameter ``name``, if given."""
        return dict(self.params).get(name)


@dataclass(frozen=True, slots=True)
class Breakpoint:
    """A step of the pair's level, checked against the control articles and the move log.

    Attributes:
        month: First month at the new level.
        change_pct: The article's change of level at the step, in %.
        control_change_pct: The control articles' median change of level the same month, in
            %; ``None`` without control data there.
        renamed: The article (or a title that now redirects to it) was moved within
            ``rename_months`` of the step.
        verdict: What the step most probably is.
        slope_before: The trend (% a year) of the segment before the step.
        slope_after: The trend (% a year) of the segment after it.
        in_window: The step lies inside the analysis window.
    """

    month: date
    change_pct: float
    control_change_pct: float | None
    renamed: bool
    verdict: BreakpointVerdict
    slope_before: float | None = None
    slope_after: float | None = None
    in_window: bool = False

    def flat_around(self, band: float) -> bool:
        """Whether the level is flat on both sides (within ``band`` % a year): a step."""
        return (
            self.slope_before is not None
            and self.slope_after is not None
            and abs(self.slope_before) < band
            and abs(self.slope_after) < band
        )


@dataclass(frozen=True, slots=True)
class Trust:
    """How far the window's verdict of one pair can be trusted, and why.

    Attributes:
        confidence: The level the rules give.
        yoy_down: Months of the window's last twelve below the same month a year earlier.
        yoy_up: Months above it.
        yoy_months: Months compared.
        yoy_consistency: Share of the compared months that moved in the verdict's direction
            (for ``stable``, the larger of the two).
        slope_pct_per_year: The trend of the segment, % a year.
        ci90: The 90 % interval of the slope from a block bootstrap, % a year.
        snr: The segment's change over the standard deviation of its month-to-month changes.
        control_change: The control articles' median trend over the same months, % a year.
        control_articles: How many control articles had data for it.
        breakpoints: The steps of the history and the window, oldest first.
        max_day_share: The largest share of a month's views that fell on one day, over the
            window.
        spike_months: Months where one day took more than ``day_spike_share``: left out of
            the slope.
        views_avg: Mean monthly views over the window.
        reasons: Why the level is what it is, most telling first.
    """

    confidence: Confidence
    yoy_down: int = 0
    yoy_up: int = 0
    yoy_months: int = 0
    yoy_consistency: float | None = None
    slope_pct_per_year: float | None = None
    ci90: tuple[float, float] | None = None
    snr: float | None = None
    control_change: float | None = None
    control_articles: int = 0
    breakpoints: tuple[Breakpoint, ...] = ()
    max_day_share: float | None = None
    spike_months: tuple[date, ...] = ()
    views_avg: float | None = None
    reasons: tuple[Reason, ...] = ()


def day_spike_months(
    daily: Sequence[tuple[date, float | None]], settings: TrustSettings = _DEFAULT
) -> tuple[dict[date, float], tuple[date, ...]]:
    """Each month's largest one-day share of its views, and the months one day dominated.

    Args:
        daily: ``(day, views)`` of the main article.
        settings: ``day_spike_share`` decides which months are spikes.

    Returns:
        ``{month: share}`` and the months over ``day_spike_share``, oldest first.
    """
    by_month: dict[date, list[float]] = {}
    for day, views in daily:
        if views is not None:
            by_month.setdefault(day.replace(day=1), []).append(views)
    shares = {m: max(v) / sum(v) for m, v in by_month.items() if sum(v) > 0}
    spikes = tuple(sorted(m for m, share in shares.items() if share > settings.day_spike_share))
    return shares, spikes


def yoy_counts(shares: Sequence[float | None], window_first: int) -> tuple[int, int, int]:
    """Months of the window's last twelve below and above the same month a year earlier.

    Only months inside the window and their year-earlier twins are read, so for the default
    two-year window the comparison stays in the window.

    Returns:
        ``(down, up, compared)``.
    """
    n = len(shares)
    down = up = compared = 0
    for k in range(max(n - _YEAR, window_first + _YEAR), n):
        now, then = shares[k], shares[k - _YEAR]
        if now is None or then is None:
            continue
        compared += 1
        if now < then:
            down += 1
        elif now > then:
            up += 1
    return down, up, compared


def theil_sen(points: Sequence[tuple[float, float]]) -> float | None:
    """The median slope of all pairs with distinct ``x``; ``None`` with fewer than two."""
    slopes = [
        (points[j][1] - points[i][1]) / (points[j][0] - points[i][0])
        for i in range(len(points) - 1)
        for j in range(i + 1, len(points))
        if points[j][0] != points[i][0]
    ]
    return median(slopes) if slopes else None


def bootstrap_ci(
    points: Sequence[tuple[float, float]], settings: TrustSettings = _DEFAULT
) -> tuple[float, float] | None:
    """The 90 % interval of the Theil–Sen slope (% a year), by a moving-block bootstrap.

    Blocks of ``bootstrap_block`` consecutive months keep the months' dependence; the
    generator is seeded (``bootstrap_seed``), so the same data give the same interval.
    """
    m = len(points)
    block = settings.bootstrap_block
    if m < 2 * block:
        return None
    rng = random.Random(settings.bootstrap_seed)
    starts = range(m - block + 1)
    slopes: list[float] = []
    for _ in range(settings.bootstrap_reps):
        sample: list[tuple[float, float]] = []
        while len(sample) < m:
            first = rng.choice(starts)
            sample.extend(points[first : first + block])
        slope = theil_sen(sorted(sample[:m]))
        if slope is not None:
            slopes.append(slope)
    if not slopes:
        return None
    slopes.sort()
    tail = (1 - settings.ci_level) / 2
    low = slopes[int(tail * (len(slopes) - 1))]
    high = slopes[int((1 - tail) * (len(slopes) - 1))]
    return _pct_year(low), _pct_year(high)


def signal_to_noise(points: Sequence[tuple[float, float]], slope: float) -> float | None:
    """The segment's fitted change over the spread of its month-to-month changes.

    Under 2 the change is no larger than what the months do from one to the next.
    """
    ordered = sorted(points)
    diffs = [(b[1] - a[1]) / (b[0] - a[0]) for a, b in pairwise(ordered) if b[0] != a[0]]
    if len(diffs) < 2:  # noqa: PLR2004 -- a spread needs two changes
        return None
    spread = pstdev(diffs)
    change = abs(slope * (ordered[-1][0] - ordered[0][0]))
    return change / spread if spread > 0 else None


def control_trend(
    controls: Sequence[Sequence[float | None]], first: int, stop: int
) -> tuple[float | None, int]:
    """The control articles' median trend (% a year) over months ``[first, stop)``.

    Args:
        controls: Each control article's monthly share, aligned with the pair's months.
        first: First month index of the segment.
        stop: One past its last.

    Returns:
        The median slope and how many articles had enough months to give one.
    """
    slopes = []
    for series in controls:
        points = [
            (float(k), math.log(x))
            for k in range(first, min(stop, len(series)))
            if (x := series[k]) is not None and x > 0
        ]
        if len(points) >= max((stop - first) // 2, 2):
            slope = theil_sen(points)
            if slope is not None:
                slopes.append(_pct_year(slope))
    return (median(slopes) if slopes else None), len(slopes)


def control_step(controls: Sequence[Sequence[float | None]], index: int) -> float | None:
    """The control articles' median change of level at ``index`` (six months against six), %."""
    ratios = []
    for series in controls:
        before = [x for x in series[max(index - _HALF, 0) : index] if x]
        after = [x for x in series[index : index + _HALF] if x]
        if len(before) >= _HALF - 2 and len(after) >= _HALF - 2:
            ratios.append(mean(after) / mean(before))
    return (median(ratios) - 1) * _PERCENT if ratios else None


def breakpoint_verdict(
    change_pct: float,
    control_pct: float | None,
    *,
    renamed: bool,
    settings: TrustSettings = _DEFAULT,
) -> BreakpointVerdict:
    """``artifact`` if the control moved at least half as much the same way, or a rename.

    Compared in log terms, so a fall of 40 % and a rise of 67 % weigh the same.
    """
    if renamed:
        return BreakpointVerdict.ARTIFACT
    if control_pct is None:
        return BreakpointVerdict.UNKNOWN
    article = math.log1p(change_pct / _PERCENT)
    control = math.log1p(control_pct / _PERCENT)
    if article and control / article >= settings.control_explains:
        return BreakpointVerdict.ARTIFACT
    return BreakpointVerdict.REAL


def segment_slope(adjusted: Sequence[float | None], first: int, stop: int) -> float | None:
    """The Theil–Sen trend (% a year) of the adjusted share over ``[first, stop)``."""
    points = [
        (float(k), math.log(x))
        for k in range(max(first, 0), min(stop, len(adjusted)))
        if (x := adjusted[k]) is not None and x > 0
    ]
    if len(points) < _HALF:
        return None
    slope = theil_sen(points)
    return None if slope is None else _pct_year(slope)


@dataclass(frozen=True, slots=True)
class _Measured:
    """The metrics of one verdict, before the rules weigh them."""

    down: int
    up: int
    compared: int
    direction: int
    ci: tuple[float, float] | None
    snr: float | None
    control: float | None
    control_count: int
    slope: float


def assess_trust(  # noqa: PLR0913 -- the verdict and everything that weighs on it
    trend: WindowTrend,
    *,
    shares: Sequence[float | None],
    breakpoints: Sequence[Breakpoint],
    controls: Sequence[Sequence[float | None]] = (),
    day_shares: dict[date, float] | None = None,
    spike_months: Sequence[date] = (),
    settings: TrustSettings = _DEFAULT,
) -> Trust:
    """The trust in one pair's window verdict: the metrics and the rules that weigh them.

    Rules (``method.md`` lists them with their thresholds):

    - ``insufficient_data``: ``low``; the reason says whether views or months are missing.
    - ``growing`` / ``declining``: three signals: the year-on-year consistency is at least
      ``yoy_strong`` of the months compared in the verdict's direction; the 90 % interval of
      the slope leaves out zero; the signal-to-noise ratio is at least ``snr_min``. Three
      give ``high``, two ``medium``, fewer ``low``. When the control articles moved at
      least ``control_explains`` as much the same way, the edition changed rather than the
      topic: ``low``.
    - ``stable``: ``high`` when the whole 90 % interval stays within the stable band;
      ``medium`` when it reaches past it (a trend cannot be ruled out); ``low`` with too few
      months fitted.

    Args:
        trend: The window's verdict.
        shares: The pair's monthly share (per million), aligned with its months.
        breakpoints: The steps with their verdicts (see :func:`breakpoint_verdict`).
        controls: The control articles' monthly shares, aligned with the pair's months.
        day_shares: Each month's largest one-day share of its views.
        spike_months: The months left out of the slope for a dominant day.
        settings: Thresholds.
    """
    window_days = {m: v for m, v in (day_shares or {}).items() if m >= trend.window_start}
    base = Trust(
        confidence=Confidence.LOW,
        breakpoints=tuple(breakpoints),
        max_day_share=max(window_days.values()) if window_days else None,
        spike_months=tuple(spike_months),
        views_avg=trend.views_avg,
    )
    if trend.verdict is TrendVerdict.INSUFFICIENT_DATA:
        few_views = trend.views_avg is not None and trend.views_avg < settings.volume_floor
        reason = (
            Reason("volume_low", (("views", round(trend.views_avg or 0)),))
            if few_views
            else Reason("window_short")
        )
        return replace(base, reasons=(reason,))
    m = _measure(trend, shares, controls, settings)
    if trend.verdict is TrendVerdict.STABLE:
        level, own = _stable_level(trend, m, settings)
        reasons = [_slope_reason(m), _yoy_reason(trend, m), *own]
    else:
        level, own = _trend_level(trend, m, settings)
        # When the control explains the change, that is the first thing the reader must know.
        leading = ("control_explains", "yoy_against")
        first = [r for r in own if r.code in leading]
        rest = [r for r in own if r.code not in leading]
        reasons = [*first, _yoy_reason(trend, m), _slope_reason(m), *rest]
    reasons += _context_reasons(trend, m, breakpoints, spike_months, settings)
    return replace(
        base,
        confidence=level,
        yoy_down=m.down,
        yoy_up=m.up,
        yoy_months=m.compared,
        yoy_consistency=m.direction / m.compared if m.compared else None,
        slope_pct_per_year=trend.slope_pct_per_year,
        ci90=m.ci,
        snr=m.snr,
        control_change=m.control,
        control_articles=m.control_count,
        reasons=tuple(reasons),
    )


def _measure(
    trend: WindowTrend,
    shares: Sequence[float | None],
    controls: Sequence[Sequence[float | None]],
    settings: TrustSettings,
) -> _Measured:
    assert trend.slope_log is not None
    down, up, compared = yoy_counts(shares, trend.window_index)
    direction = {TrendVerdict.GROWING: up, TrendVerdict.DECLINING: down}.get(
        trend.verdict, max(down, up)
    )
    control, count = control_trend(controls, trend.segment_index, trend.end_index + 1)
    return _Measured(
        down=down,
        up=up,
        compared=compared,
        direction=direction,
        ci=bootstrap_ci(trend.points, settings),
        snr=signal_to_noise(trend.points, trend.slope_log),
        control=control,
        control_count=count,
        slope=trend.slope_pct_per_year or 0.0,
    )


def _yoy_reason(trend: WindowTrend, m: _Measured) -> Reason:
    return Reason(
        "yoy",
        (("down", m.down), ("up", m.up), ("months", m.compared), ("verdict", trend.verdict)),
    )


def _slope_reason(m: _Measured) -> Reason:
    bounds = () if m.ci is None else (("low", round(m.ci[0])), ("high", round(m.ci[1])))
    return Reason("slope", (("slope", round(m.slope)), *bounds))


def _stable_level(
    trend: WindowTrend, m: _Measured, settings: TrustSettings
) -> tuple[Confidence, list[Reason]]:
    band = settings.stable_pct_per_year
    if len(trend.points) < settings.min_window_months:
        return Confidence.LOW, [Reason("few_months", (("months", len(trend.points)),))]
    if m.ci is not None and -band < m.ci[0] and m.ci[1] < band:
        return Confidence.HIGH, []
    return Confidence.MEDIUM, [Reason("ci_wide", (("band", round(band)),))]


def _trend_level(
    trend: WindowTrend, m: _Measured, settings: TrustSettings
) -> tuple[Confidence, list[Reason]]:
    growing = trend.verdict is TrendVerdict.GROWING
    reasons: list[Reason] = []
    signals = 0
    if m.compared and m.direction >= settings.yoy_strong * m.compared / _YEAR:
        signals += 1
    if m.ci is not None and (m.ci[0] > 0 if growing else m.ci[1] < 0):
        signals += 1
    else:
        reasons.append(Reason("ci_zero"))
    if m.snr is not None and m.snr >= settings.snr_min:
        signals += 1
    else:
        reasons.append(Reason("snr_low", (("snr", round(m.snr or 0.0, 1)),)))
    level = {3: Confidence.HIGH, 2: Confidence.MEDIUM}.get(signals, Confidence.LOW)
    if m.compared and m.direction * 2 < m.compared:
        # Most months sit on the other side of the year before: the slope contradicts them.
        level = Confidence.LOW
        reasons.insert(0, Reason("yoy_against", (("count", m.direction), ("months", m.compared))))
    if m.control is not None and m.slope and m.control / m.slope >= settings.control_explains:
        level = Confidence.LOW
        reasons.insert(0, Reason("control_explains", (("change", round(m.control)),)))
    return level, reasons


def _context_reasons(
    trend: WindowTrend,
    m: _Measured,
    breakpoints: Sequence[Breakpoint],
    spike_months: Sequence[date],
    settings: TrustSettings,
) -> list[Reason]:
    """The control, renames, technical steps and spike months: what the line always states."""
    out: list[Reason] = []
    if m.control is not None:
        out.append(Reason("control", (("change", round(m.control)), ("articles", m.control_count))))
    else:
        out.append(Reason("control_none"))
    renames = [b for b in breakpoints if b.renamed]
    out.append(
        Reason("renames", (("months", ", ".join(f"{b.month:%Y-%m}" for b in renames)),))
        if renames
        else Reason("renames_none")
    )
    out += [
        Reason("artifact", (("month", f"{b.month:%Y-%m}"),))
        for b in breakpoints
        if b.verdict is BreakpointVerdict.ARTIFACT
    ]
    if spike_months:
        out.append(
            Reason("day_spikes", (("months", ", ".join(f"{d:%Y-%m}" for d in spike_months)),))
        )
    if trend.verdict is not TrendVerdict.STABLE:
        out += [
            Reason("step_not_trend", (("month", f"{b.month:%Y-%m}"),))
            for b in breakpoints
            if b.in_window and b.flat_around(settings.stable_pct_per_year)
        ]
    return out


def _pct_year(slope: float) -> float:
    """A slope in log share a month as % a year."""
    return (math.exp(slope * _YEAR) - 1) * _PERCENT
