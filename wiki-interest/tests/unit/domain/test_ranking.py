"""Ranking: normalisation, weighting, profiles, ties and missing data."""

from __future__ import annotations

import math

import pytest
from series_factory import healthy_metrics

from wiki_interest.domain.models import (
    AudienceProfile,
    RankingWeights,
    ReliabilityLevel,
    TrendMetrics,
    WikiProject,
)
from wiki_interest.domain.ranking import ProfileThresholds, RankingInput, rank_audiences

UK, CS, PL = WikiProject("uk"), WikiProject("cs"), WikiProject("pl")
EQUAL = RankingWeights(1, 1, 1, 1)


def audience(
    project: WikiProject,
    metrics: TrendMetrics | None,
    reliability: ReliabilityLevel = ReliabilityLevel.HIGH,
    topic_id: str = "t",
) -> RankingInput:
    return RankingInput(topic_id, project, metrics, reliability)


class TestOrderingAndScore:
    def test_best_growth_volume_and_stability_wins(self) -> None:
        strong = healthy_metrics(growth_yoy=0.5, views_avg=10_000, volatility_cv=0.1)
        weak = healthy_metrics(growth_yoy=0.0, views_avg=100, volatility_cv=1.0)
        ranked = rank_audiences([audience(CS, weak), audience(UK, strong)], EQUAL)
        assert [r.project for r in ranked] == [UK, CS]
        assert ranked[0].score == pytest.approx(1.0)
        assert ranked[1].score == pytest.approx(0.25)

    def test_components_are_normalised_and_keyed(self) -> None:
        ranked = rank_audiences(
            [audience(UK, healthy_metrics(growth_yoy=0.3)), audience(CS, healthy_metrics())],
            EQUAL,
        )
        top = ranked[0]
        assert set(top.components) == {"growth", "volume", "stability", "reliability"}
        assert top.components == {
            "growth": 1.0,
            "volume": 0.5,
            "stability": 0.5,
            "reliability": 1.0,
        }

    def test_weights_are_normalised_before_use(self) -> None:
        inputs = [audience(UK, healthy_metrics(growth_yoy=0.5)), audience(CS, healthy_metrics())]
        heavy = rank_audiences(inputs, RankingWeights(4, 3, 2, 1))
        light = rank_audiences(inputs, RankingWeights(0.4, 0.3, 0.2, 0.1))
        assert [r.score for r in heavy] == pytest.approx([r.score for r in light])

    def test_all_equal_component_is_neutral(self) -> None:
        ranked = rank_audiences(
            [audience(UK, healthy_metrics()), audience(CS, healthy_metrics())], EQUAL
        )
        for r in ranked:
            assert r.components["growth"] == 0.5
            assert r.components["volume"] == 0.5
            assert r.components["stability"] == 0.5

    def test_ties_are_broken_by_project_code(self) -> None:
        ranked = rank_audiences([audience(p, healthy_metrics()) for p in (UK, PL, CS)], EQUAL)
        assert [r.project for r in ranked] == [CS, PL, UK]

    def test_single_input_scores_its_reliability_only(self) -> None:
        (only,) = rank_audiences([audience(UK, healthy_metrics())], EQUAL)
        assert only.score == pytest.approx(0.25 * (0.5 + 0.5 + 0.5 + 1.0))


class TestMissingData:
    def test_missing_metrics_is_insufficient_with_zero_score(self) -> None:
        ranked = rank_audiences([audience(UK, None), audience(CS, healthy_metrics())], EQUAL)
        last = ranked[-1]
        assert last.project == UK
        assert last.score == 0.0
        assert last.profile is AudienceProfile.INSUFFICIENT_DATA
        assert last.components["growth"] == 0.5

    def test_missing_growth_is_insufficient_with_zero_score(self) -> None:
        no_growth = healthy_metrics(growth_yoy=None, growth_halves=None, slope_per_year=None)
        (only,) = rank_audiences([audience(UK, no_growth)], EQUAL)
        assert only.score == 0.0
        assert only.profile is AudienceProfile.INSUFFICIENT_DATA

    def test_growth_falls_back_to_halves_then_slope(self) -> None:
        halves = healthy_metrics(growth_yoy=None, growth_halves=0.5, slope_per_year=-0.5)
        slope = healthy_metrics(growth_yoy=None, growth_halves=None, slope_per_year=0.5)
        ranked = rank_audiences([audience(UK, halves), audience(CS, slope)], EQUAL)
        assert ranked[0].components["growth"] == ranked[1].components["growth"] == 0.5

    def test_unknown_volatility_is_neutral_not_extreme(self) -> None:
        unknown = healthy_metrics(volatility_cv=None)
        stable = healthy_metrics(volatility_cv=0.0)
        shaky = healthy_metrics(volatility_cv=3.0)
        ranked = rank_audiences(
            [audience(UK, unknown), audience(CS, stable), audience(PL, shaky)], EQUAL
        )
        by_project = {r.project: r.components["stability"] for r in ranked}
        assert by_project == {UK: 0.5, CS: 1.0, PL: 0.0}


class TestReliability:
    def test_low_reliability_halves_the_score(self) -> None:
        inputs = [
            audience(UK, healthy_metrics(growth_yoy=0.5), ReliabilityLevel.LOW),
            audience(CS, healthy_metrics(growth_yoy=0.5), ReliabilityLevel.HIGH),
        ]
        ranked = rank_audiences(inputs, RankingWeights(1, 0, 0, 0))
        assert ranked[0].project == CS
        assert ranked[1].score == pytest.approx(ranked[0].score / 2)

    def test_penalty_is_configurable(self) -> None:
        inputs = [audience(UK, healthy_metrics(), ReliabilityLevel.LOW)]
        none = rank_audiences(
            inputs, EQUAL, profiles=ProfileThresholds(low_reliability_penalty=1.0)
        )
        assert none[0].score == pytest.approx(0.25 * 1.5)

    def test_reliability_component_maps_levels(self) -> None:
        levels = [ReliabilityLevel.HIGH, ReliabilityLevel.MEDIUM, ReliabilityLevel.LOW]
        ranked = rank_audiences(
            [
                audience(p, healthy_metrics(), lvl)
                for p, lvl in zip((UK, CS, PL), levels, strict=True)
            ],
            EQUAL,
        )
        assert {r.project: r.components["reliability"] for r in ranked} == {
            UK: 1.0,
            CS: 0.5,
            PL: 0.0,
        }


class TestProfiles:
    def test_high_growth_below_median_volume_is_early_niche(self) -> None:
        small = healthy_metrics(growth_yoy=0.5, views_avg=100)
        big = healthy_metrics(growth_yoy=0.5, views_avg=100_000)
        medium = healthy_metrics(growth_yoy=0.0, views_avg=1_000)
        ranked = rank_audiences(
            [audience(UK, small), audience(CS, big), audience(PL, medium)], EQUAL
        )
        profiles = {r.project: r.profile for r in ranked}
        assert profiles[UK] is AudienceProfile.EARLY_NICHE
        assert profiles[CS] is AudienceProfile.GROWTH_MARKET
        assert profiles[PL] is AudienceProfile.MATURE_MARKET

    def test_declining(self) -> None:
        (only,) = rank_audiences([audience(UK, healthy_metrics(growth_yoy=-0.2))], EQUAL)
        assert only.profile is AudienceProfile.DECLINING

    @pytest.mark.parametrize(
        ("growth", "expected"),
        [
            (0.15, AudienceProfile.GROWTH_MARKET),
            (0.149, AudienceProfile.MATURE_MARKET),
            (-0.1, AudienceProfile.DECLINING),
            (-0.099, AudienceProfile.MATURE_MARKET),
        ],
    )
    def test_threshold_boundaries(self, growth: float, expected: AudienceProfile) -> None:
        (only,) = rank_audiences([audience(UK, healthy_metrics(growth_yoy=growth))], EQUAL)
        assert only.profile is expected

    def test_single_audience_at_its_own_median_is_not_a_niche(self) -> None:
        (only,) = rank_audiences([audience(UK, healthy_metrics(growth_yoy=0.5))], EQUAL)
        assert only.profile is AudienceProfile.GROWTH_MARKET

    def test_custom_thresholds(self) -> None:
        lenient = ProfileThresholds(growth_high=0.01, growth_low=-0.5)
        (only,) = rank_audiences(
            [audience(UK, healthy_metrics(growth_yoy=0.05))], EQUAL, profiles=lenient
        )
        assert only.profile is AudienceProfile.GROWTH_MARKET


class TestEmpty:
    def test_no_inputs_gives_no_output(self) -> None:
        assert rank_audiences([], EQUAL) == ()

    def test_scores_are_finite_and_bounded(self) -> None:
        inputs = [
            audience(UK, healthy_metrics(growth_yoy=1e6, views_avg=1e12, volatility_cv=1e6)),
            audience(CS, healthy_metrics(growth_yoy=-1.0, views_avg=0.0, volatility_cv=0.0)),
        ]
        for r in rank_audiences(inputs, EQUAL):
            assert math.isfinite(r.score)
            assert 0.0 <= r.score <= 1.0
