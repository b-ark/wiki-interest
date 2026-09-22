"""Series algebra: alignment, weighted combination, resampling and normalisation."""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st
from series_factory import daily, monthly

from wiki_interest.domain.models import Granularity, Series, SeriesUnit, Window
from wiki_interest.domain.series import (
    align,
    combine,
    observed_pairs,
    per_million,
    to_monthly,
)

optional_views = st.one_of(st.none(), st.floats(min_value=0, max_value=1e9))
value_lists = st.lists(optional_views, min_size=1, max_size=12)


class TestObservedPairs:
    def test_keeps_positions_across_gaps(self) -> None:
        assert observed_pairs(monthly([5, None, 7])) == ((0, 5), (2, 7))

    def test_empty_for_all_missing(self) -> None:
        assert observed_pairs(monthly([None, None])) == ()


class TestAlign:
    def test_fills_missing_buckets_and_drops_outside_points(self) -> None:
        series = monthly([1, 2, 3], start=date(2023, 1, 1))
        window = Window(Granularity.MONTHLY, date(2023, 2, 1), date(2023, 5, 1))
        aligned = align(series, window)
        assert aligned.periods == window.buckets()
        assert aligned.values == (2, 3, None, None)

    def test_keeps_unit(self) -> None:
        series = monthly([1.0], unit=SeriesUnit.PER_MILLION)
        window = Window(Granularity.MONTHLY, date(2023, 1, 1), date(2023, 1, 1))
        assert align(series, window).unit is SeriesUnit.PER_MILLION

    def test_rejects_granularity_mismatch(self) -> None:
        window = Window(Granularity.MONTHLY, date(2024, 1, 1), date(2024, 2, 1))
        with pytest.raises(ValueError, match="Cannot align"):
            align(daily([1, 2]), window)

    @given(value_lists, st.integers(min_value=0, max_value=3))
    def test_preserves_values_of_buckets_inside_window(
        self, values: list[float | None], shift: int
    ) -> None:
        series = monthly(values)
        window = Window(Granularity.MONTHLY, date(2023, 1 + shift, 1), date(2024, 6, 1))
        aligned = align(series, window)
        original = dict(zip(series.periods, series.values, strict=True))
        for point in aligned:
            assert point.value == original.get(point.period)


class TestCombine:
    def test_weighted_sum(self) -> None:
        combined = combine([(monthly([10, 20]), 1.0), (monthly([2, 4]), 0.5)])
        assert combined.values == (11, 22)

    def test_missing_part_does_not_erase_the_others(self) -> None:
        main = monthly([100, 100, None])
        redirect = monthly([None, 5, None])
        assert combine([(main, 1.0), (redirect, 1.0)]).values == (100, 105, None)

    def test_single_part_with_weight_one_is_identity(self) -> None:
        series = monthly([1, None, 3])
        assert combine([(series, 1.0)]).values == series.values

    def test_rejects_empty_parts(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            combine([])

    @pytest.mark.parametrize(
        ("other", "message"),
        [
            (monthly([1, 2], start=date(2023, 2, 1)), "same periods"),
            (monthly([1, 2], unit=SeriesUnit.PER_MILLION), "same unit"),
            (daily([1, 2]), "same granularity"),
        ],
    )
    def test_rejects_misaligned_parts(self, other: Series, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            combine([(monthly([1, 2]), 1.0), (other, 1.0)])

    @given(
        st.lists(
            st.tuples(value_lists, st.floats(min_value=0, max_value=10)),
            min_size=2,
            max_size=5,
        )
    )
    def test_is_order_independent(self, parts: list[tuple[list[float | None], float]]) -> None:
        length = min(len(values) for values, _ in parts)
        series_parts = [(monthly(values[:length]), weight) for values, weight in parts]
        forward = combine(series_parts).values
        backward = combine(list(reversed(series_parts))).values
        for a, b in zip(forward, backward, strict=True):
            assert (a is None) == (b is None)
            if a is not None and b is not None:
                assert a == pytest.approx(b)


class TestToMonthly:
    def test_sums_days_into_months(self) -> None:
        series = daily([1] * 31 + [2] * 29, start=date(2024, 1, 1))
        result = to_monthly(series)
        assert result.granularity is Granularity.MONTHLY
        assert result.periods == (date(2024, 1, 1), date(2024, 2, 1))
        assert result.values == (31, 58)

    def test_month_is_none_only_when_every_day_is_none(self) -> None:
        series = daily([None] * 31 + [None] * 28 + [3.0], start=date(2024, 1, 1))
        assert to_monthly(series).values == (None, 3.0)

    def test_partial_month_keeps_partial_sum(self) -> None:
        series = daily([None, 4.0, None], start=date(2024, 3, 30))
        assert to_monthly(series).values == (4.0, None)

    def test_rejects_monthly_input(self) -> None:
        with pytest.raises(ValueError, match="daily"):
            to_monthly(monthly([1]))


class TestPerMillion:
    def test_scales_to_views_per_million_project_views(self) -> None:
        result = per_million(monthly([50, 10]), monthly([1_000_000, 5_000_000]))
        assert result.unit is SeriesUnit.PER_MILLION
        assert result.values == (50.0, 2.0)

    def test_none_where_either_side_missing_or_total_zero(self) -> None:
        article = monthly([None, 5, 5, 5])
        total = monthly([100, None, 0, 100])
        assert per_million(article, total).values == (None, None, None, 50_000.0)

    def test_rejects_period_mismatch(self) -> None:
        with pytest.raises(ValueError, match="same periods"):
            per_million(monthly([1, 2]), monthly([1, 2, 3]))

    def test_rejects_granularity_mismatch(self) -> None:
        with pytest.raises(ValueError, match="same granularity"):
            per_million(monthly([1]), daily([1]))

    @given(
        st.lists(st.floats(min_value=0, max_value=1e6), min_size=1, max_size=8),
        st.lists(st.floats(min_value=1, max_value=1e9), min_size=8, max_size=8),
        st.floats(min_value=0.01, max_value=1000),
    )
    def test_is_invariant_to_scaling_both_inputs(
        self, article: list[float], totals: list[float], factor: float
    ) -> None:
        totals = totals[: len(article)]
        base = per_million(monthly(article), monthly(totals)).values
        scaled = per_million(
            monthly([a * factor for a in article]), monthly([t * factor for t in totals])
        ).values
        for a, b in zip(base, scaled, strict=True):
            assert a is not None
            assert b == pytest.approx(a, rel=1e-9)
