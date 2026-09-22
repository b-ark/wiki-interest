"""Trend statistics, cross-checked against pymannkendall and scipy."""

from __future__ import annotations

import math

import numpy as np
import pymannkendall as pmk
import pytest
from hypothesis import given
from hypothesis import strategies as st
from scipy.stats import theilslopes

from wiki_interest.domain.trend_tests import (
    MIN_MANN_KENDALL_VALUES,
    detrend,
    mann_kendall,
    pairwise_median_slope,
    seasonal_strength,
    theil_sen_slope,
)


def _seeded_series(seed: int, n: int = 36) -> list[float]:
    """Deterministic mix of trend, noise and integer rounding so ties occur."""
    rng = np.random.default_rng(seed)
    slope = rng.uniform(-3, 3)
    noise = rng.normal(0, 10, size=n)
    values = 100 + slope * np.arange(n) + noise
    return [float(round(v)) for v in values]


SEEDS = [1, 7, 42, 2024, 99_991]


class TestMannKendall:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_matches_pymannkendall(self, seed: int) -> None:
        values = _seeded_series(seed)
        ours = mann_kendall(values)
        reference = pmk.original_test(values)
        assert ours.statistic_s == int(reference.s)
        assert ours.variance == pytest.approx(float(reference.var_s))
        assert ours.z == pytest.approx(float(reference.z))
        assert ours.p_value == pytest.approx(float(reference.p))

    def test_matches_pymannkendall_with_heavy_ties(self) -> None:
        values = [1.0, 2.0, 2.0, 2.0, 3.0, 1.0, 3.0, 3.0, 4.0, 2.0, 4.0, 4.0]
        ours = mann_kendall(values)
        reference = pmk.original_test(values)
        assert ours.variance == pytest.approx(float(reference.var_s))
        assert ours.p_value == pytest.approx(float(reference.p))

    def test_rising_series_is_significant(self) -> None:
        result = mann_kendall([float(i) for i in range(12)])
        assert result.statistic_s == 66
        assert result.p_value < 0.001

    def test_constant_series_has_no_trend(self) -> None:
        result = mann_kendall([5.0] * 10)
        assert result.statistic_s == 0
        assert result.variance == 0.0
        assert result.z == 0.0
        assert result.p_value == 1.0

    def test_rejects_too_few_values(self) -> None:
        with pytest.raises(ValueError, match="at least"):
            mann_kendall([1.0] * (MIN_MANN_KENDALL_VALUES - 1))

    @given(st.lists(st.floats(min_value=-1e6, max_value=1e6), min_size=4, max_size=30))
    def test_p_value_is_a_probability(self, values: list[float]) -> None:
        assert 0.0 <= mann_kendall(values).p_value <= 1.0


class TestTheilSen:
    @pytest.mark.parametrize("seed", SEEDS)
    def test_matches_scipy(self, seed: int) -> None:
        values = _seeded_series(seed)
        assert theil_sen_slope(values) == pytest.approx(float(theilslopes(values).slope))

    def test_ignores_a_single_outlier(self) -> None:
        values = [float(i) for i in range(20)]
        values[10] = 1_000.0
        assert theil_sen_slope(values) == pytest.approx(1.0)

    def test_rejects_single_value(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            theil_sen_slope([1.0])

    def test_pairwise_slope_with_gaps_matches_scipy_with_explicit_x(self) -> None:
        xs = [0.0, 1.0, 2.0, 5.0, 6.0, 9.0, 10.0]
        ys = [3.0, 5.0, 4.5, 11.0, 12.5, 18.0, 21.0]
        expected = float(theilslopes(ys, xs).slope)
        assert pairwise_median_slope(list(zip(xs, ys, strict=True))) == pytest.approx(expected)

    def test_pairwise_slope_rejects_single_point(self) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            pairwise_median_slope([(0.0, 1.0)])


class TestDetrend:
    def test_perfect_line_leaves_zero_residuals(self) -> None:
        residuals = detrend([2.0 + 3 * i for i in range(10)])
        assert all(r == pytest.approx(0.0, abs=1e-9) for r in residuals if r is not None)

    def test_keeps_gaps_in_place(self) -> None:
        residuals = detrend([1.0, None, 3.0, 4.0])
        assert residuals[1] is None
        assert len(residuals) == 4

    def test_fewer_than_two_observations_are_returned_unchanged(self) -> None:
        assert detrend([None, 7.0, None]) == (None, 7.0, None)


class TestSeasonalStrength:
    def test_strong_seasonal_signal_scores_high(self) -> None:
        values = [100 + 50 * math.sin(2 * math.pi * i / 12) + 2 * i for i in range(36)]
        strength = seasonal_strength(values)
        assert strength is not None
        assert strength > 0.9

    def test_noise_scores_low(self) -> None:
        rng = np.random.default_rng(3)
        values = [float(v) for v in rng.normal(100, 10, size=120)]
        strength = seasonal_strength(values)
        assert strength is not None
        assert strength < 0.3

    def test_none_with_fewer_than_two_cycles(self) -> None:
        assert seasonal_strength([float(i % 12) for i in range(23)]) is None

    def test_none_when_a_position_is_observed_only_once(self) -> None:
        values: list[float | None] = [float(i % 12) + i for i in range(24)]
        values[12] = None
        assert seasonal_strength(values) is None

    def test_none_for_a_perfect_line(self) -> None:
        assert seasonal_strength([float(i) for i in range(24)]) is None

    def test_custom_period(self) -> None:
        values = [float(i % 4) for i in range(16)]
        strength = seasonal_strength(values, period=4)
        assert strength is not None
        assert strength > 0.9

    def test_rejects_period_below_two(self) -> None:
        with pytest.raises(ValueError, match="period"):
            seasonal_strength([1.0] * 10, period=1)

    @given(st.lists(st.floats(min_value=0, max_value=1e4), min_size=24, max_size=48))
    def test_is_within_unit_interval_when_computable(self, values: list[float]) -> None:
        strength = seasonal_strength(values)
        assert strength is None or 0.0 <= strength <= 1.0
