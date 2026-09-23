"""Months that stand out, whether a season explains them, and their probable cause."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date

import pytest

from wiki_interest.domain.findings import SeasonalProfile
from wiki_interest.domain.models import Granularity, Point, Series, SeriesUnit
from wiki_interest.domain.monthly_anomalies import (
    AnomalyNature,
    MonthlyAnomaly,
    anomaly_nature,
    explained_by_season,
    find_monthly_anomalies,
    yoy_without,
)


def _series(values: Sequence[float | None]) -> Series:
    points = tuple(
        Point(date(2024 + i // 12, i % 12 + 1, 1), value) for i, value in enumerate(values)
    )
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, points)


def _noisy(count: int = 24, level: float = 1000.0) -> list[float | None]:
    return [level * (1 + 0.08 * math.sin(i * 2.3)) for i in range(count)]


class TestFind:
    def test_a_doubled_month_stands_out(self) -> None:
        values = _noisy()
        values[10] = 2000.0
        (found,) = find_monthly_anomalies(_series(values))
        assert found.month == date(2024, 11, 1)
        assert found.index == 10
        assert found.multiple == pytest.approx(2.0, rel=0.1)

    def test_a_drop_stands_out_too(self) -> None:
        values = _noisy()
        values[5] = 300.0
        (found,) = find_monthly_anomalies(_series(values))
        assert found.multiple < 1

    def test_a_small_bump_does_not(self) -> None:
        values = _noisy()
        values[10] = 1300.0
        assert find_monthly_anomalies(_series(values)) == ()

    def test_a_trend_is_not_an_anomaly(self) -> None:
        rising = [1000.0 * 1.05**i for i in range(24)]
        assert find_monthly_anomalies(_series(list(rising))) == ()

    def test_a_month_high_every_year_is_a_season(self) -> None:
        values = _noisy(36)
        for i in (8, 20, 32):
            values[i] = 2200.0
        assert find_monthly_anomalies(_series(values)) == ()

    def test_too_few_months(self) -> None:
        assert find_monthly_anomalies(_series([100.0] * 6 + [900.0])) == ()


def _anomaly(multiple: float, month: int = 9, index: int = 10) -> MonthlyAnomaly:
    return MonthlyAnomaly(date(2024, month, 1), index, 1000.0 * multiple, 1000.0, multiple)


def test_a_usual_september_peak_explains_a_high_september() -> None:
    effects = [0.0] * 12
    effects[8] = 1.5
    profile = SeasonalProfile(tuple(effects), 9, 7)
    assert explained_by_season(_anomaly(2.9), profile)
    assert not explained_by_season(_anomaly(2.9, month=4), profile)
    assert not explained_by_season(_anomaly(0.4), profile)  # a drop in a peak month
    assert not explained_by_season(_anomaly(2.9), None)


class TestNature:
    @staticmethod
    def _access(desktop: float, mobile: float, app: float) -> dict[str, Series]:
        def flat_with(value: float) -> Series:
            base = [1000.0] * 24
            base[10] = value
            return _series(list(base))

        return {
            "desktop": flat_with(desktop),
            "mobile-web": flat_with(mobile),
            "mobile-app": flat_with(app),
        }

    def test_one_access_method_suggests_a_bot(self) -> None:
        nature = anomaly_nature(_anomaly(1.9), self._access(1100.0, 3500.0, 1000.0))
        assert nature is AnomalyNature.POSSIBLE_BOT

    def test_several_methods_are_an_event(self) -> None:
        nature = anomaly_nature(_anomaly(2.0), self._access(2000.0, 2200.0, 1100.0))
        assert nature is AnomalyNature.EVENT

    def test_automated_traffic_suggests_a_bot(self) -> None:
        automated = [100.0] * 24
        automated[10] = 900.0
        nature = anomaly_nature(
            _anomaly(2.0), self._access(2000.0, 2200.0, 1100.0), automated=_series(list(automated))
        )
        assert nature is AnomalyNature.POSSIBLE_BOT

    def test_a_burst_of_daily_views_is_an_event(self) -> None:
        assert anomaly_nature(_anomaly(2.0), {}, burst=True) is AnomalyNature.EVENT

    def test_without_a_split_or_for_a_drop_the_cause_is_unknown(self) -> None:
        assert anomaly_nature(_anomaly(2.0), {}) is AnomalyNature.UNKNOWN
        split = self._access(300.0, 300.0, 300.0)
        assert anomaly_nature(_anomaly(0.3), split) is AnomalyNature.UNKNOWN


class TestYoyWithout:
    def test_the_month_and_its_twin_are_left_out(self) -> None:
        values: list[float | None] = [*([100.0] * 12), *([110.0] * 12)]
        values[20] = 330.0  # a spike in the second year
        with_spike = sum(v for v in values[12:] if v) / sum(v for v in values[:12] if v) - 1
        assert with_spike > 0.25
        assert yoy_without(values, 20) == pytest.approx(0.10)
        assert yoy_without(values, 8) == pytest.approx(yoy_without(values, 20) or 0)

    def test_outside_the_window_or_with_gaps(self) -> None:
        values: list[float | None] = [100.0] * 30
        assert yoy_without(values, 2) is None  # before the last 24 months
        assert yoy_without([100.0] * 20, 5) is None
        gappy: list[float | None] = [100.0] * 24
        gappy[3] = None
        assert yoy_without(gappy, 10) is None
