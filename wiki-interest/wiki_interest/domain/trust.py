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
from collections.abc import Collection, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import StrEnum
from statistics import mean, median
from typing import TYPE_CHECKING

from wiki_interest.domain.trend_tests import pairwise_median_slope

if TYPE_CHECKING:
    # Only for annotations: the observations read the verdicts this module gives.
    from wiki_interest.domain.observations import PairHistory, Step

__all__ = [
    "TrendVerdict",
    "TrustSettings",
    "WindowTrend",
    "window_trend",
]

_YEAR = 12
_PERCENT = 100.0


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
            trend is read from it on; fewer, and the whole window is read.
        split_step: Ratio of the six months after a month to the six before (seasonal rhythm
            removed) that splits the window's trend. Lower than the ``step`` a history
            observation needs (1.35): inside a two-year window a 25 % shift within a year is
            already more than twice the stable band, and reading a trend across it would call
            one past drop a steady fall.
        volume_floor: Mean monthly views under which a series gives ``insufficient_data``:
            under a hundred views a month a handful of readers moves the share by tens of %.
    """

    stable_pct_per_year: float = 10.0
    min_window_months: int = 12
    min_segment_months: int = 12
    split_step: float = 1.25
    volume_floor: float = 100.0


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
    )
