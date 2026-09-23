"""Decision rules: momentum, relative size, the edition, and the size x momentum outcome."""

from __future__ import annotations

import pytest

from wiki_interest.domain.assessment import (
    AssessmentSettings,
    EditionRelation,
    Momentum,
    RelativeSize,
    Robustness,
    divergence,
    edition_relation,
    momentum,
    outcome,
    relative_size,
    robustness,
)
from wiki_interest.domain.models import TrendDirection


class TestMomentum:
    @pytest.mark.parametrize(
        ("growth", "direction", "expected"),
        [
            (0.2, TrendDirection.RISING, Momentum.GROWING),
            (-0.17, TrendDirection.FALLING, Momentum.DECLINING),
            (-0.02, TrendDirection.FALLING, Momentum.FLAT),  # significant but negligible
            (-0.3, TrendDirection.FLAT, Momentum.FLAT),  # large but not significant
            (0.2, TrendDirection.FALLING, Momentum.FLAT),  # the test contradicts the change
            (None, TrendDirection.RISING, Momentum.UNKNOWN),
            (0.2, TrendDirection.UNKNOWN, Momentum.UNKNOWN),
        ],
    )
    def test_growth_and_decline_need_both_the_test_and_the_size(
        self, growth: float | None, direction: TrendDirection, expected: Momentum
    ) -> None:
        assert momentum(growth, direction) is expected

    def test_the_cut_off_is_a_setting(self) -> None:
        settings = AssessmentSettings(min_momentum=0.01)
        assert momentum(-0.02, TrendDirection.FALLING, settings) is Momentum.DECLINING


class TestRelativeSize:
    @pytest.mark.parametrize(
        ("value", "largest", "expected"),
        [
            (39.3, 39.3, RelativeSize.LARGEST),
            (35.0, 39.3, RelativeSize.SIMILAR),
            (28.6, 39.3, RelativeSize.SMALLER),
            (None, 39.3, None),
            (10.0, None, None),
            (0.0, 39.3, None),
        ],
    )
    def test_size_is_only_ever_relative(
        self, value: float | None, largest: float | None, expected: RelativeSize | None
    ) -> None:
        assert relative_size(value, largest) is expected


class TestEditionRelation:
    @pytest.mark.parametrize(
        ("share_change", "expected"),
        [
            (0.1, EditionRelation.GAINING),
            (-0.18, EditionRelation.LOSING),
            (0.02, EditionRelation.IN_LINE),
            (None, None),
        ],
    )
    def test_share_change_decides(
        self, share_change: float | None, expected: EditionRelation | None
    ) -> None:
        assert edition_relation(share_change) is expected


class TestOutcome:
    @pytest.mark.parametrize(
        ("size", "trend", "expected"),
        [
            (RelativeSize.LARGEST, Momentum.GROWING, "large_growing"),
            (RelativeSize.SIMILAR, Momentum.DECLINING, "large_declining"),
            (RelativeSize.SMALLER, Momentum.GROWING, "small_growing"),
            (RelativeSize.SMALLER, Momentum.FLAT, "small_flat"),
            (None, Momentum.DECLINING, "single_declining"),
            (None, Momentum.UNKNOWN, "unknown"),
        ],
    )
    def test_size_times_momentum(
        self, size: RelativeSize | None, trend: Momentum, expected: str
    ) -> None:
        assert outcome(size, trend, trusted=True) == expected

    def test_missing_trust_or_another_subject_overrides(self) -> None:
        assert outcome(RelativeSize.LARGEST, Momentum.GROWING, trusted=False) == "low_trust"
        assert (
            outcome(RelativeSize.LARGEST, Momentum.GROWING, trusted=True, measures_topic=False)
            == "substitute"
        )


class TestRobustness:
    @pytest.mark.parametrize(
        ("trend", "recent", "expected"),
        [
            (Momentum.DECLINING, -0.2, Robustness.CONFIRMED),
            (Momentum.DECLINING, 0.04, Robustness.MIXED),
            (Momentum.DECLINING, 0.1, Robustness.REVERSING),
            (Momentum.GROWING, 0.1, Robustness.CONFIRMED),
            (Momentum.GROWING, -0.1, Robustness.REVERSING),
            (Momentum.FLAT, 0.01, Robustness.CONFIRMED),
            (Momentum.FLAT, -0.2, Robustness.MIXED),
            (Momentum.UNKNOWN, -0.2, Robustness.UNKNOWN),
            (Momentum.DECLINING, None, Robustness.UNKNOWN),
        ],
    )
    def test_recent_months_against_the_trend(
        self, trend: Momentum, recent: float | None, expected: Robustness
    ) -> None:
        assert robustness(trend, recent, reliable=True, views_avg=1000.0) is expected

    def test_weak_data_or_a_tiny_audience_cannot_be_judged(self) -> None:
        declining = Momentum.DECLINING
        assert robustness(declining, -0.2, reliable=False, views_avg=1000.0) is Robustness.UNKNOWN
        assert robustness(declining, -0.2, reliable=True, views_avg=50.0) is Robustness.UNKNOWN


@pytest.mark.parametrize(
    ("article", "share", "expected"),
    [
        (0.20, -0.10, "views_up_share_down"),
        (-0.30, 0.10, "views_down_share_up"),
        (0.20, 0.10, None),
        (-0.30, -0.20, None),
        (0.02, -0.10, None),
        (None, -0.10, None),
    ],
)
def test_readers_and_share_moving_apart(
    article: float | None, share: float | None, expected: str | None
) -> None:
    assert divergence(article, share) == expected
