"""Metric definitions on synthetic series with known answers."""

from __future__ import annotations

import math
from datetime import date

import numpy as np
import pytest
from series_factory import daily, monthly

from wiki_interest.domain.metrics import MetricsSettings, compute_automated_share, compute_metrics
from wiki_interest.domain.models import SeriesUnit, TrendDirection


def _linear(n: int, start: float = 1_000.0, step: float = 50.0) -> list[float | None]:
    return [start + step * i for i in range(n)]


def _noise(n: int, seed: int = 11, level: float = 1_000.0, sd: float = 20.0) -> list[float | None]:
    rng = np.random.default_rng(seed)
    return [float(v) for v in rng.normal(level, sd, size=n)]


class TestVolume:
    def test_total_and_average_over_observed_views(self) -> None:
        m = compute_metrics(monthly([100, None, 300]))
        assert m.periods == 3
        assert m.completeness == pytest.approx(2 / 3)
        assert m.views_total == 400
        assert m.views_avg == 200

    def test_empty_observations_give_zero_not_error(self) -> None:
        m = compute_metrics(monthly([None, None]))
        assert m.views_total == 0
        assert m.views_avg == 0.0
        assert m.trend_direction is TrendDirection.UNKNOWN

    def test_per_million_average_only_with_normalised_series(self) -> None:
        views = monthly([100, 200])
        assert compute_metrics(views).per_million_avg is None
        normalised = monthly([1.0, 3.0], unit=SeriesUnit.PER_MILLION)
        assert compute_metrics(views, per_million=normalised).per_million_avg == 2.0


class TestGrowth:
    def test_year_over_year_compares_last_twelve_with_previous_twelve(self) -> None:
        values = [100.0] * 12 + [150.0] * 12
        assert compute_metrics(monthly(values)).growth_yoy == pytest.approx(0.5)

    def test_year_over_year_needs_twenty_four_periods(self) -> None:
        assert compute_metrics(monthly(_linear(23))).growth_yoy is None

    def test_year_over_year_none_when_a_half_is_too_incomplete(self) -> None:
        values: list[float | None] = [100.0] * 12 + [150.0] * 8 + [None] * 4
        assert compute_metrics(monthly(values)).growth_yoy is None

    def test_year_over_year_none_when_the_base_half_is_too_incomplete(self) -> None:
        values: list[float | None] = [None] * 4 + [100.0] * 8 + [150.0] * 12
        assert compute_metrics(monthly(values)).growth_yoy is None

    def test_year_over_year_tolerates_a_few_gaps(self) -> None:
        values: list[float | None] = [100.0] * 12 + [150.0] * 9 + [None] * 3
        assert compute_metrics(monthly(values)).growth_yoy == pytest.approx(0.5)

    @pytest.mark.parametrize("missing_first", [True, False])
    def test_gaps_do_not_create_growth_or_decline(self, missing_first: bool) -> None:
        complete: list[float | None] = [100.0] * 12
        incomplete: list[float | None] = [100.0] * 9 + [None] * 3
        values = incomplete + complete if missing_first else complete + incomplete
        metrics = compute_metrics(monthly(values))
        assert metrics.growth_yoy == pytest.approx(0.0)
        assert metrics.growth_halves == pytest.approx(0.0)

    def test_year_over_year_matches_seasons_despite_asymmetric_gaps(self) -> None:
        before: list[float | None] = [None, 20.0, 30.0, *([100.0] * 9)]
        after: list[float | None] = [15.0, None, 45.0, *([150.0] * 9)]
        assert compute_metrics(monthly(before + after)).growth_yoy == pytest.approx(0.5)

    def test_separately_complete_halves_need_enough_shared_months(self) -> None:
        before: list[float | None] = [None] * 3 + [100.0] * 9
        after: list[float | None] = [100.0] * 9 + [None] * 3
        metrics = compute_metrics(monthly(before + after))
        assert metrics.growth_yoy is None
        assert metrics.growth_halves is None

    def test_growth_needs_positive_base_in_matched_months(self) -> None:
        before: list[float | None] = [*([100.0] * 3), *([0.0] * 9)]
        after: list[float | None] = [None] * 3 + [10.0] * 9
        assert compute_metrics(monthly(before + after)).growth_yoy is None

    def test_year_over_year_none_when_base_is_zero(self) -> None:
        values = [0.0] * 12 + [10.0] * 12
        assert compute_metrics(monthly(values)).growth_yoy is None

    def test_halves_compare_second_half_with_first(self) -> None:
        assert compute_metrics(monthly([10, 10, 20, 20])).growth_halves == pytest.approx(1.0)

    def test_halves_exclude_middle_bucket_of_odd_window(self) -> None:
        m = compute_metrics(monthly([10, 10, 999, 30, 30]))
        assert m.growth_halves == pytest.approx(2.0)

    @pytest.mark.parametrize("months", range(4, 26))
    def test_constant_interest_has_zero_growth_for_even_and_odd_windows(self, months: int) -> None:
        assert compute_metrics(monthly([100.0] * months)).growth_halves == pytest.approx(0.0)

    def test_halves_match_observations_around_excluded_middle_month(self) -> None:
        values: list[float | None] = [100, None, 100, 100, 999, 150, 150, 150, 150]
        assert compute_metrics(monthly(values)).growth_halves == pytest.approx(0.5)

    def test_halves_need_four_periods(self) -> None:
        assert compute_metrics(monthly([1, 2, 3])).growth_halves is None

    def test_growth_uses_per_million_when_given(self) -> None:
        views = monthly([100.0] * 24)
        normalised = monthly([1.0] * 12 + [2.0] * 12, unit=SeriesUnit.PER_MILLION)
        assert compute_metrics(views, per_million=normalised).growth_yoy == pytest.approx(1.0)


class TestSlope:
    def test_exponential_growth_yields_its_yearly_rate(self) -> None:
        monthly_rate = 0.02
        values: list[float | None] = [1000 * (1 + monthly_rate) ** i for i in range(24)]
        expected = (1 + monthly_rate) ** 12 - 1
        assert compute_metrics(monthly(values)).slope_per_year == pytest.approx(expected)

    def test_needs_six_positive_observations(self) -> None:
        values: list[float | None] = [10, 20, 30, 40, 50, 0.0, None]
        assert compute_metrics(monthly(values)).slope_per_year is None

    def test_non_positive_values_are_skipped_not_logged(self) -> None:
        values: list[float | None] = [0.0, *_linear(7)]
        m = compute_metrics(monthly(values))
        assert m.slope_per_year is not None
        assert math.isfinite(m.slope_per_year)


class TestTrend:
    def test_linear_rise_is_rising_and_significant(self) -> None:
        m = compute_metrics(monthly(_linear(24)))
        assert m.trend_direction is TrendDirection.RISING
        assert m.trend_p_value is not None
        assert m.trend_p_value < 0.05

    def test_linear_fall_is_falling(self) -> None:
        m = compute_metrics(monthly(_linear(24, start=3_000, step=-50)))
        assert m.trend_direction is TrendDirection.FALLING

    def test_noise_is_flat(self) -> None:
        m = compute_metrics(monthly(_noise(24)))
        assert m.trend_direction is TrendDirection.FLAT
        assert m.trend_p_value is not None
        assert m.trend_p_value >= 0.05

    def test_too_few_observations_is_unknown(self) -> None:
        m = compute_metrics(monthly(_linear(7)))
        assert m.trend_direction is TrendDirection.UNKNOWN
        assert m.trend_p_value is None

    def test_significant_step_with_zero_median_slope_is_flat(self) -> None:
        # Mann-Kendall sees a significant shift, but with this many ties the Theil-Sen
        # median slope is exactly zero, so no direction can honestly be stated.
        values = [0.0] * 12 + [1.0] * 4
        m = compute_metrics(monthly(values))
        assert m.trend_p_value is not None
        assert m.trend_p_value < 0.05
        assert m.trend_direction is TrendDirection.FLAT

    def test_alpha_is_configurable(self) -> None:
        strict = MetricsSettings(alpha=1e-12)
        m = compute_metrics(monthly(_linear(8)), settings=strict)
        assert m.trend_direction is TrendDirection.FLAT


class TestSeasonality:
    def test_seasonal_signal_scores_high(self) -> None:
        values: list[float | None] = [
            1000 + 400 * math.sin(2 * math.pi * i / 12) for i in range(36)
        ]
        m = compute_metrics(monthly(values))
        assert m.seasonality_strength is not None
        assert m.seasonality_strength > 0.9

    def test_short_window_has_no_seasonality(self) -> None:
        assert compute_metrics(monthly(_linear(12))).seasonality_strength is None


class TestSpikeShare:
    def test_single_spike_dominates(self) -> None:
        values: list[float | None] = [100.0] * 60
        values[30] = 10_000.0
        m = compute_metrics(monthly(_linear(3)), daily_views=daily(values))
        assert m.spike_share is not None
        assert m.spike_share == pytest.approx(9_900 / 15_900)

    def test_flat_daily_series_has_no_spikes(self) -> None:
        m = compute_metrics(monthly(_linear(3)), daily_views=daily(_noise(90, sd=5)))
        assert m.spike_share == 0.0

    def test_needs_thirty_observed_days(self) -> None:
        values: list[float | None] = [100.0] * 29
        assert compute_metrics(monthly(_linear(3)), daily_views=daily(values)).spike_share is None

    def test_none_without_daily_data(self) -> None:
        assert compute_metrics(monthly(_linear(3))).spike_share is None

    def test_all_zero_days_give_zero_share(self) -> None:
        values: list[float | None] = [0.0] * 40
        assert compute_metrics(monthly(_linear(3)), daily_views=daily(values)).spike_share == 0.0

    def test_small_wobble_on_tiny_spread_is_not_a_spike(self) -> None:
        values: list[float | None] = [100.0] * 40
        values[5] = 150.0
        assert compute_metrics(monthly(_linear(3)), daily_views=daily(values)).spike_share == 0.0


class TestVolatility:
    def test_perfect_line_has_zero_volatility(self) -> None:
        m = compute_metrics(monthly(_linear(12)))
        assert m.volatility_cv == pytest.approx(0.0, abs=1e-9)

    def test_noise_has_volatility_near_its_relative_spread(self) -> None:
        m = compute_metrics(monthly(_noise(120, level=1000, sd=100)))
        assert m.volatility_cv is not None
        assert 0.07 < m.volatility_cv < 0.13

    def test_needs_six_observations(self) -> None:
        assert compute_metrics(monthly(_linear(5))).volatility_cv is None

    def test_none_when_level_is_not_positive(self) -> None:
        values: list[float | None] = [0.0] * 8
        assert compute_metrics(monthly(values)).volatility_cv is None


class TestAutomatedShare:
    def test_missing_user_diagnostic_cannot_be_replaced_with_bundle_traffic(self) -> None:
        assert compute_automated_share(None, monthly([100.0] * 4)) is None

    def test_share_over_buckets_observed_in_both(self) -> None:
        user = monthly([100, 100, None, 100])
        automated = monthly([50, None, 50, 100])
        assert compute_metrics(user, automated_views=automated).automated_share == pytest.approx(
            150 / 350
        )

    def test_matches_buckets_by_period_not_position(self) -> None:
        user = monthly([100, 100], start=date(2023, 1, 1))
        automated = monthly([300, 100], start=date(2023, 2, 1))
        assert compute_metrics(user, automated_views=automated).automated_share == pytest.approx(
            300 / 400
        )

    def test_none_without_series_or_overlap_or_traffic(self) -> None:
        user = monthly([100, None])
        assert compute_metrics(user).automated_share is None
        assert compute_metrics(user, automated_views=monthly([None, 5])).automated_share is None
        zero = monthly([0.0, 0.0])
        assert compute_metrics(zero, automated_views=zero).automated_share is None
