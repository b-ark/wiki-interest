"""Months that stand out from their surroundings, and what probably caused them.

A single month twice as high as usual moves a year-over-year comparison by several percent;
the reader should know about it and see the number without it. A month stands out when its
value, against the median of the months around it (which follows a trend), is a real multiple
of it and either unusual for this series (several robust standard deviations of all such
deviations) or large whatever the noise. A month that is high every year is a season, not an
anomaly.

The cause is read from the access split. Human interest from news reaches every access method
(desktop, mobile web, apps); unflagged automated traffic usually hits one. A jump confined to
one method, or together with a jump in traffic Wikimedia classifies as automated, is a
possible bot; a jump across methods, or with a burst of daily views, an event.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from statistics import median

from wiki_interest.domain.findings import SeasonalProfile
from wiki_interest.domain.models import Series

__all__ = [
    "AnomalyNature",
    "AnomalySettings",
    "MonthlyAnomaly",
    "anomaly_nature",
    "explained_by_season",
    "find_monthly_anomalies",
    "yoy_without",
]

_MONTHS = 12


class AnomalyNature(StrEnum):
    """The probable cause of an anomalous month."""

    EVENT = "event"
    """Readers came through every access method, or daily views show a burst."""
    POSSIBLE_BOT = "possible_bot"
    """The extra views came through one access method, or with automated traffic."""
    UNKNOWN = "unknown"
    """Neither pattern is clear, or the month is a drop."""


@dataclass(frozen=True, slots=True)
class AnomalySettings:
    """Thresholds of the monthly detector; documented in ``references/methodology.md``.

    Attributes:
        half_window: Months on each side whose median is the month's baseline.
        min_months: Fewest observed months before anomalies are looked for.
        mad_multiplier: Robust standard deviations the log deviation must reach, measured
            against all months of the series: a noisy series needs a larger jump.
        min_multiple: The month is at least this multiple of its baseline (or at most its
            inverse, for a drop).
        strong_multiple: From this multiple (or its inverse) a month stands out however noisy
            the series is.
        mad_scale: Turns a MAD into a standard deviation estimate for normal data.
        min_other_years: A month high (or low) in at least half of the other years with data
            for that calendar month is a season; checked only with this many other years.
        dominant_share: Share of the extra views one access method must hold to suggest a bot.
        quiet_multiple: The other methods stay below this multiple of their baseline.
        spread_multiple: Two or more methods above this multiple make an event.
        automated_multiple: Automated traffic above this multiple of its baseline in the same
            month suggests a bot.
    """

    half_window: int = 6
    min_months: int = 12
    mad_multiplier: float = 2.5
    min_multiple: float = 1.6
    strong_multiple: float = 1.8
    mad_scale: float = 1.4826
    min_other_years: int = 2
    dominant_share: float = 0.85
    quiet_multiple: float = 1.3
    spread_multiple: float = 1.5
    automated_multiple: float = 3.0


_DEFAULT_SETTINGS = AnomalySettings()


@dataclass(frozen=True, slots=True)
class MonthlyAnomaly:
    """One month far from its surroundings.

    Attributes:
        month: The month.
        index: Position of the month in the series.
        value: The month's value.
        baseline: Median of the surrounding months.
        multiple: ``value / baseline``; below one for a drop.
    """

    month: date
    index: int
    value: float
    baseline: float
    multiple: float


def find_monthly_anomalies(
    series: Series, settings: AnomalySettings = _DEFAULT_SETTINGS
) -> tuple[MonthlyAnomaly, ...]:
    """Months of ``series`` that stand out, in chronological order."""
    values = series.values
    observed = [v for v in values if v is not None and v > 0]
    if len(observed) < settings.min_months:
        return ()
    deviations: dict[int, tuple[float, float]] = {}
    for i, value in enumerate(values):
        base = _baseline(values, i, settings.half_window)
        if value is not None and value > 0 and base is not None and base > 0:
            deviations[i] = (math.log(value / base), base)
    if not deviations:
        return ()
    logs = [d for d, _ in deviations.values()]
    centre = median(logs)
    spread = settings.mad_scale * median(abs(d - centre) for d in logs)
    floor = math.log(settings.min_multiple)
    strong = math.log(settings.strong_multiple)
    out: list[MonthlyAnomaly] = []
    for i, (deviation, base) in deviations.items():
        unusual = spread <= 0 or abs(deviation - centre) >= settings.mad_multiplier * spread
        if abs(deviation) < floor or not (unusual or abs(deviation) >= strong):
            continue
        if _seasonal(i, deviation, deviations, settings):
            continue
        value = values[i]
        assert value is not None
        out.append(MonthlyAnomaly(series.points[i].period, i, value, base, math.exp(deviation)))
    return tuple(out)


def _baseline(values: Sequence[float | None], index: int, half_window: int) -> float | None:
    around = [
        v
        for j in range(max(0, index - half_window), min(len(values), index + half_window + 1))
        if j != index and (v := values[j]) is not None and v > 0
    ]
    return median(around) if len(around) >= half_window else None


def _seasonal(
    index: int,
    deviation: float,
    deviations: Mapping[int, tuple[float, float]],
    settings: AnomalySettings,
) -> bool:
    """High (or low) in at least half of the other years for that calendar month."""
    others = [
        deviations[j][0]
        for j in range(index % _MONTHS, max(deviations) + 1, _MONTHS)
        if j != index and j in deviations
    ]
    if len(others) < settings.min_other_years:
        return False
    half = math.log(settings.min_multiple) / 2
    same_way = [d for d in others if d * deviation > 0 and abs(d) >= half]
    return len(same_way) * 2 >= len(others)


def explained_by_season(
    anomaly: MonthlyAnomaly, profile: SeasonalProfile | None, *, share: float = 0.5
) -> bool:
    """Whether the calendar month's usual effect accounts for the deviation.

    Inside a two-year window every calendar month occurs twice, too few to tell a season
    from an event; the profile of the whole history can. A September at three times the
    summer months is the school year, not news, when Septembers are usually far above the
    average: the month is dropped when its usual effect goes the same way and covers at
    least ``share`` of the deviation (on the log scale).
    """
    if profile is None:
        return False
    effect = profile.effects[anomaly.month.month - 1]
    if effect is None or effect <= -1:
        return False
    usual, seen = math.log1p(effect), math.log(anomaly.multiple)
    return usual * seen > 0 and abs(usual) >= share * abs(seen)


def anomaly_nature(
    anomaly: MonthlyAnomaly,
    by_access: Mapping[str, Series],
    *,
    automated: Series | None = None,
    burst: bool = False,
    settings: AnomalySettings = _DEFAULT_SETTINGS,
) -> AnomalyNature:
    """The probable cause of a rise, from the access split of the same month.

    Args:
        anomaly: A month found in the article's views.
        by_access: Human views of the same article per access method, aligned with the
            series ``anomaly`` was found in.
        automated: Traffic Wikimedia classifies as automated, aligned the same way.
        burst: Whether daily views show a burst inside the month.
        settings: Thresholds.
    """
    if anomaly.multiple < 1:
        return AnomalyNature.UNKNOWN
    i = anomaly.index
    if automated is not None:
        auto = _multiple(automated, i, settings)
        if auto is not None and auto >= settings.automated_multiple:
            return AnomalyNature.POSSIBLE_BOT
    multiples: dict[str, float] = {}
    excess: dict[str, float] = {}
    for name, series in by_access.items():
        value = series.values[i] if i < len(series.values) else None
        base = _baseline(series.values, i, settings.half_window)
        if value is None or base is None or base <= 0:
            continue
        multiples[name] = value / base
        excess[name] = max(0.0, value - base)
    total = sum(excess.values())
    if total > 0:
        top = max(excess, key=lambda k: excess[k])
        quiet = all(m < settings.quiet_multiple for k, m in multiples.items() if k != top)
        if excess[top] / total >= settings.dominant_share and quiet:
            return AnomalyNature.POSSIBLE_BOT
    if burst or sum(1 for m in multiples.values() if m >= settings.spread_multiple) >= 2:  # noqa: PLR2004
        return AnomalyNature.EVENT
    return AnomalyNature.UNKNOWN


def _multiple(series: Series, index: int, settings: AnomalySettings) -> float | None:
    values = series.values
    value = values[index] if index < len(values) else None
    base = _baseline(values, index, settings.half_window)
    if value is None or base is None or base <= 0:
        return None
    return value / base


def yoy_without(values: Sequence[float | None], excluded: int) -> float | None:
    """Last 12 months over the 12 before, without month ``excluded`` and its twin a year off.

    Dropping the twin keeps both sums over the same calendar months, so seasons still cancel.

    Returns:
        The change, or ``None`` with fewer than 24 values, a gap, or ``excluded`` outside
        the last 24 months.
    """
    if len(values) < 2 * _MONTHS:
        return None
    window = list(values[-2 * _MONTHS :])
    position = excluded - (len(values) - 2 * _MONTHS)
    if not 0 <= position < 2 * _MONTHS:
        return None
    twin = position + _MONTHS if position < _MONTHS else position - _MONTHS
    before = [v for k, v in enumerate(window[:_MONTHS]) if k not in (position, twin)]
    after = [v for k, v in enumerate(window[_MONTHS:], _MONTHS) if k not in (position, twin)]
    if any(v is None for v in (*before, *after)):
        return None
    then = sum(v for v in before if v is not None)
    now = sum(v for v in after if v is not None)
    return now / then - 1 if then > 0 else None
