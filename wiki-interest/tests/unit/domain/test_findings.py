"""Detectors: level shifts, dated bursts, recent change, seasonal profile, article vs edition."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import date, timedelta

import pytest

from wiki_interest.domain.findings import (
    FindingsSettings,
    compare_with_edition,
    detect_level_shift,
    find_anomalies,
    recent_change,
    seasonal_profile,
)
from wiki_interest.domain.models import Granularity, Point, Series, SeriesUnit


def monthly(values: Sequence[float | None], start: date = date(2023, 1, 1)) -> Series:
    points = []
    for i, value in enumerate(values):
        year, month = divmod(start.month - 1 + i, 12)
        points.append(Point(date(start.year + year, month + 1, 1), value))
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, tuple(points))


def daily(values: Sequence[float | None], start: date = date(2025, 1, 1)) -> Series:
    points = tuple(Point(start + timedelta(days=i), v) for i, v in enumerate(values))
    return Series(Granularity.DAILY, SeriesUnit.VIEWS, points)


def wobble(i: int, amplitude: float = 0.03) -> float:
    """Deterministic noise of a few percent, so series are never perfectly flat."""
    return 1 + amplitude * math.sin(i * 1.7)


class TestLevelShift:
    def test_step_up_is_dated_and_sized(self) -> None:
        values = [100 * wobble(i) for i in range(12)] + [160 * wobble(i) for i in range(12, 24)]
        shift = detect_level_shift(monthly(values))
        assert shift is not None
        assert shift.start == date(2024, 1, 1)
        assert shift.change == pytest.approx(0.6, abs=0.05)
        assert shift.months_after == 12
        assert shift.before == pytest.approx(100, rel=0.05)
        assert shift.after == pytest.approx(160, rel=0.05)

    def test_steady_trend_is_not_an_event(self) -> None:
        values = [100 * 1.03**i * wobble(i) for i in range(24)]
        assert detect_level_shift(monthly(values)) is None

    def test_small_step_is_ignored(self) -> None:
        values = [100 * wobble(i) for i in range(12)] + [110 * wobble(i) for i in range(12, 24)]
        assert detect_level_shift(monthly(values)) is None

    def test_noisy_series_needs_a_clear_difference(self) -> None:
        values = [100 * wobble(i, 0.5) for i in range(12)] + [
            130 * wobble(i, 0.5) for i in range(12, 24)
        ]
        assert detect_level_shift(monthly(values)) is None

    def test_short_series_is_not_examined(self) -> None:
        values = [100.0] * 6 + [300.0] * 6
        assert detect_level_shift(monthly(values)) is None

    def test_gaps_and_zeros_are_skipped(self) -> None:
        values: list[float | None] = [100 * wobble(i) for i in range(12)]
        values += [200 * wobble(i) for i in range(12, 24)]
        values[3] = None
        values[5] = 0.0
        shift = detect_level_shift(monthly(values))
        assert shift is not None
        assert shift.change > 0.8


class TestAnomalies:
    def test_one_day_burst_is_dated_against_its_local_baseline(self) -> None:
        values = [100.0 + (i % 7) for i in range(120)]
        values[70] = 700.0
        (burst,) = find_anomalies(daily(values))
        assert burst.start == burst.end == burst.peak_day == date(2025, 1, 1) + timedelta(70)
        assert burst.peak_views == 700.0
        assert burst.multiple == pytest.approx(700.0 / burst.baseline)
        assert 0 < burst.share < 0.1

    def test_neighbouring_days_form_one_episode(self) -> None:
        values = [100.0] * 120
        values[40:43] = [500.0, 800.0, 400.0]
        (burst,) = find_anomalies(daily(values))
        start = date(2025, 1, 1)
        assert (burst.start, burst.end, burst.peak_day) == (
            start + timedelta(40),
            start + timedelta(42),
            start + timedelta(41),
        )

    def test_burst_at_the_start_of_the_period_is_found(self) -> None:
        # Two weeks of attention at the very start must not fill their own baseline window.
        values = [400.0 - 20 * i for i in range(14)] + [40.0 + (i % 5) for i in range(200)]
        bursts = find_anomalies(daily(values))
        assert bursts
        assert bursts[0].peak_day == date(2025, 1, 1)

    def test_growth_is_not_a_burst(self) -> None:
        values = [100.0 * 1.004**i for i in range(365)]
        assert find_anomalies(daily(values)) == ()

    def test_small_absolute_excess_is_ignored(self) -> None:
        values = [3.0] * 100
        values[50] = 30.0  # ten times the usual, but only 27 extra views
        assert find_anomalies(daily(values)) == ()

    def test_cap_and_order_by_size(self) -> None:
        values = [100.0] * 300
        for day, peak in ((30, 400.0), (100, 900.0), (170, 600.0), (240, 500.0)):
            values[day] = peak
        bursts = find_anomalies(daily(values))
        assert [b.peak_views for b in bursts] == [900.0, 600.0, 500.0]

    def test_too_few_days_or_no_views_give_nothing(self) -> None:
        assert find_anomalies(daily([100.0] * 20)) == ()
        assert find_anomalies(daily([0.0] * 100)) == ()

    def test_monthly_series_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="daily"):
            find_anomalies(monthly([1.0] * 24))


class TestRecentChange:
    def test_same_months_a_year_apart(self) -> None:
        values = [100.0] * 12 + [100.0] * 9 + [150.0] * 3
        recent = recent_change(monthly(values))
        assert recent is not None
        assert recent.change == pytest.approx(0.5)
        assert (recent.start, recent.end, recent.months) == (
            date(2024, 10, 1),
            date(2024, 12, 1),
            3,
        )

    def test_needs_complete_months_and_a_base(self) -> None:
        assert recent_change(monthly([100.0] * 14)) is None
        gaps: list[float | None] = [100.0] * 24
        gaps[-1] = None
        assert recent_change(monthly(gaps)) is None
        zeros = [0.0] * 12 + [5.0] * 12
        assert recent_change(monthly(zeros)) is None


class TestSeasonalProfile:
    def test_peak_and_trough_months_on_a_trend(self) -> None:
        values = [
            1000 * 1.02**i * (1.5 if i % 12 == 8 else 0.7 if i % 12 == 6 else 1.0)
            for i in range(36)
        ]
        profile = seasonal_profile(monthly(values))
        assert profile is not None
        assert profile.peak_month == 9
        assert profile.trough_month == 7
        assert profile.peak > 0.3
        assert profile.trough < -0.2
        assert sum(e for e in profile.effects if e is not None) == pytest.approx(0, abs=1e-9)

    def test_needs_every_month_twice(self) -> None:
        assert seasonal_profile(monthly([100.0] * 18)) is None
        values: list[float | None] = [100.0] * 24
        values[2] = None
        values[14] = None
        assert seasonal_profile(monthly(values)) is None


class TestEditionComparison:
    def test_share_rises_when_the_edition_shrinks_faster(self) -> None:
        article = monthly([100.0] * 12 + [90.0] * 12)
        edition = monthly([1e6] * 12 + [0.8e6] * 12)
        result = compare_with_edition(article, edition)
        assert result is not None
        assert result.basis == "yoy"
        assert result.article_change == pytest.approx(-0.1)
        assert result.edition_change == pytest.approx(-0.2)
        assert result.share_change == pytest.approx(0.9 / 0.8 - 1)

    def test_measured_share_series_is_used_when_given(self) -> None:
        article = monthly([100.0] * 12 + [90.0] * 12)
        edition = monthly([1e6] * 12 + [0.8e6] * 12)
        share = monthly([10.0] * 12 + [11.0] * 12)
        result = compare_with_edition(article, edition, share=share)
        assert result is not None
        assert result.share_change == pytest.approx(0.1)

    def test_short_period_uses_halves(self) -> None:
        result = compare_with_edition(monthly([10.0, 10.0, 20.0, 20.0]), monthly([1.0] * 4))
        assert result is not None
        assert result.basis == "halves"
        assert result.article_change == pytest.approx(1.0)

    def test_nothing_to_compare(self) -> None:
        assert compare_with_edition(monthly([None, None, None, None]), monthly([1.0] * 4)) is None
        assert compare_with_edition(monthly([1.0, 2.0]), monthly([1.0, 2.0])) is None


def test_settings_are_honoured() -> None:
    values = [100 * wobble(i) for i in range(12)] + [115 * wobble(i) for i in range(12, 24)]
    loose = FindingsSettings(min_shift_change=0.1, min_shift_t=2.0)
    assert detect_level_shift(monthly(values)) is None
    assert detect_level_shift(monthly(values), loose) is not None
