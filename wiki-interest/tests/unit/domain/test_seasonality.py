"""Seasons on the whole history: stated only with enough years, repeated and material."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

from wiki_interest.domain.models import Granularity, Point, Series, SeriesUnit
from wiki_interest.domain.seasonality import SeasonReason, SeasonSettings, season_evidence


def _series(values: Sequence[float | None], start: date = date(2015, 7, 1)) -> Series:
    points = []
    for i, value in enumerate(values):
        index = start.year * 12 + start.month - 1 + i
        points.append(Point(date(index // 12, index % 12 + 1, 1), value))
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, tuple(points))


def _seasonal(years: int, *, start: date = date(2015, 1, 1), amplitude: float = 0.6) -> Series:
    """September high, July low, every year, on a slow rise."""
    values: list[float | None] = []
    for i in range(12 * years):
        month = (start.month - 1 + i) % 12 + 1
        effect = amplitude if month == 9 else -amplitude / 2 if month == 7 else 0.0
        wobble = 0.03 * math.sin(i * 1.7)
        values.append(1000.0 * (1 + 0.01 * i) * (1 + effect + wobble))
    return _series(values, start)


def test_a_repeated_material_season_is_solid() -> None:
    evidence = season_evidence(_seasonal(8))
    assert evidence.reason is SeasonReason.SOLID
    assert evidence.solid
    assert evidence.profile is not None
    assert (evidence.profile.peak_month, evidence.profile.trough_month) == (9, 7)
    assert evidence.years == 8
    assert evidence.consistency == 1.0
    assert (evidence.start, evidence.end) == (date(2015, 1, 1), date(2022, 12, 1))


def test_three_years_are_too_short_whatever_the_pattern() -> None:
    assert season_evidence(_seasonal(3)).reason is SeasonReason.SHORT_HISTORY


def test_months_before_the_article_existed_are_skipped() -> None:
    values: list[float | None] = [None] * 18
    values += _seasonal(6, start=date(2017, 1, 1)).values
    padded = _series(values)
    evidence = season_evidence(padded)
    assert evidence.start == date(2017, 1, 1)
    assert evidence.years == 6


def test_a_small_range_is_weak() -> None:
    assert season_evidence(_seasonal(8, amplitude=0.05)).reason is SeasonReason.WEAK


def test_a_peak_that_moves_between_years_is_inconsistent() -> None:
    values: list[float | None] = []
    for year in range(8):
        peak = 9 if year % 2 == 0 else 3  # September in half of the years, March in the rest
        for month in range(1, 13):
            effect = 0.8 if month == peak else -0.3 if month == 7 else 0.0
            values.append(1000.0 * (1 + effect))
    evidence = season_evidence(_series(values, date(2015, 1, 1)), SeasonSettings(min_strength=0.1))
    assert evidence.reason is SeasonReason.INCONSISTENT
    assert evidence.consistency is not None
    assert evidence.consistency < 0.8


def test_no_data() -> None:
    assert season_evidence(_series([None] * 30)).reason is SeasonReason.NO_DATA
    assert season_evidence(_series([100.0] * 10)).reason is SeasonReason.NO_DATA
