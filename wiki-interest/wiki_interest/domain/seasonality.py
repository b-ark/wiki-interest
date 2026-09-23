"""Seasonality on the longest history, and whether it is solid enough to state.

A pattern read from two years of data is two observations per calendar month: one good
January makes a "January peak". The season is therefore measured on the article's whole
monthly history (Wikimedia's data starts in 2015-07), independently of the analysis window,
and stated only when it is material and repeats: enough full years, the peak and trough
months among the extremes of most years, and a peak-to-trough range worth mentioning.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from statistics import median

from wiki_interest.domain.findings import SeasonalProfile, seasonal_profile
from wiki_interest.domain.models import Series
from wiki_interest.domain.trend_tests import pairwise_median_slope, seasonal_strength

__all__ = ["SeasonEvidence", "SeasonReason", "SeasonSettings", "season_evidence"]

_MONTHS = 12
_EXTREMES = 2
"""A year agrees with the pattern when its peak month is among its two strongest months and
its trough month among its two weakest."""


class SeasonReason(StrEnum):
    """Why a pattern is or is not stated."""

    SOLID = "solid"
    """Enough years, repeated, and material: stated."""
    SHORT_HISTORY = "short_history"
    """Fewer full years than needed; each month was observed only a few times."""
    INCONSISTENT = "inconsistent"
    """The peak or trough month moves from year to year."""
    WEAK = "weak"
    """The calendar explains too little, or the peak and trough are close."""
    NO_DATA = "no_data"
    """Not every calendar month has been observed twice."""


@dataclass(frozen=True, slots=True)
class SeasonSettings:
    """When a seasonal pattern is stated; documented in ``references/methodology.md``.

    Attributes:
        min_years: Full calendar years of history needed.
        min_consistency: Share of those years whose extremes agree with the pattern.
        min_strength: Share of the detrended variation the calendar must explain.
        min_range: Peak month minus trough month, relative to the usual level.
    """

    min_years: int = 5
    min_consistency: float = 0.8
    min_strength: float = 0.3
    min_range: float = 0.25


_DEFAULT_SETTINGS = SeasonSettings()


@dataclass(frozen=True, slots=True)
class SeasonEvidence:
    """A seasonal profile with what speaks for and against stating it.

    Attributes:
        profile: Calendar-month effects over the whole history; ``None`` without data.
        strength: Share of the detrended variation the calendar explains.
        years: Full calendar years observed.
        consistency: Share of those years whose peak and trough agree with the profile.
        start: First month used.
        end: Last month used.
        reason: Whether it is stated, and why not.
    """

    profile: SeasonalProfile | None
    strength: float | None
    years: int
    consistency: float | None
    start: date | None
    end: date | None
    reason: SeasonReason

    @property
    def solid(self) -> bool:
        """Whether the pattern may be stated as a fact."""
        return self.reason is SeasonReason.SOLID


def season_evidence(
    history: Series, settings: SeasonSettings = _DEFAULT_SETTINGS
) -> SeasonEvidence:
    """Measure the season on ``history`` and judge whether it is solid.

    Args:
        history: Monthly views over the longest available period; leading months before the
            article existed (no data or zero) are skipped.
        settings: Thresholds.
    """
    points = list(history.points)
    while points and not points[0].value:
        points.pop(0)
    if not points:
        return SeasonEvidence(None, None, 0, None, None, None, SeasonReason.NO_DATA)
    trimmed = Series(history.granularity, history.unit, tuple(points))
    profile = seasonal_profile(trimmed)
    strength = seasonal_strength(trimmed.values, _MONTHS)
    ratios = _detrended(trimmed)
    years = _full_years(ratios)
    consistency = _consistency(years, profile) if profile is not None and years else None
    start, end = points[0].period, points[-1].period
    reason = _reason(profile, strength, len(years), consistency, settings)
    return SeasonEvidence(profile, strength, len(years), consistency, start, end, reason)


def _reason(
    profile: SeasonalProfile | None,
    strength: float | None,
    years: int,
    consistency: float | None,
    settings: SeasonSettings,
) -> SeasonReason:
    if profile is None:
        return SeasonReason.NO_DATA
    if years < settings.min_years:
        return SeasonReason.SHORT_HISTORY
    if strength is None or strength < settings.min_strength:
        return SeasonReason.WEAK  # no variation around the trend at all, or too little
    if profile.peak - profile.trough < settings.min_range:
        return SeasonReason.WEAK
    if consistency is None or consistency < settings.min_consistency:
        return SeasonReason.INCONSISTENT
    return SeasonReason.SOLID


def _detrended(series: Series) -> dict[date, float]:
    """Each positive observation over a robust exponential trend (as the profile uses)."""
    logs = [
        (float(i), math.log(p.value), p.period)
        for i, p in enumerate(series.points)
        if p.value is not None and p.value > 0
    ]
    if len(logs) < 2:  # noqa: PLR2004 -- a line needs two points
        return {}
    slope = pairwise_median_slope([(x, y) for x, y, _ in logs])
    intercept = median(y - slope * x for x, y, _ in logs)
    return {period: math.exp(y - intercept - slope * x) for x, y, period in logs}


def _full_years(ratios: dict[date, float]) -> list[dict[int, float]]:
    """Calendar years with all twelve months observed: month -> detrended ratio."""
    by_year: dict[int, dict[int, float]] = {}
    for period, ratio in ratios.items():
        by_year.setdefault(period.year, {})[period.month] = ratio
    return [months for _, months in sorted(by_year.items()) if len(months) == _MONTHS]


def _consistency(years: list[dict[int, float]], profile: SeasonalProfile) -> float:
    agree = 0
    for months in years:
        ranked = sorted(months, key=lambda m: months[m])
        if profile.peak_month in ranked[-_EXTREMES:] and profile.trough_month in ranked[:_EXTREMES]:
            agree += 1
    return agree / len(years)
