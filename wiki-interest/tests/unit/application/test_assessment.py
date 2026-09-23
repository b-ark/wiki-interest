"""Assessing pairs (size, momentum, edition, evidence) and concluding a run."""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest

from wiki_interest.application.analysis import AnalysisResult, PairAnalysis, PairFindings
from wiki_interest.application.assessment import (
    Evidence,
    assess,
    conclude,
    headline_growth,
)
from wiki_interest.domain.assessment import EditionRelation, Momentum, RelativeSize, Robustness
from wiki_interest.domain.findings import EditionComparison, RecentChange
from wiki_interest.domain.models import (
    ArticleRef,
    ArticleRole,
    BundleStatus,
    Check,
    CheckStatus,
    Granularity,
    Point,
    Reliability,
    ReliabilityLevel,
    ResolutionSource,
    Series,
    SeriesUnit,
    SubstituteKind,
    TopicBundle,
    TrendDirection,
    TrendMetrics,
    WikiProject,
)

RU, UK, PL = WikiProject("ru"), WikiProject("uk"), WikiProject("pl")
EMPTY = Series(Granularity.MONTHLY, SeriesUnit.VIEWS, (Point(date(2025, 1, 1), 1.0),))
CLEAN = (
    Check("window_length", CheckStatus.PASS, "window_length.ok", {"months": 36}),
    Check("completeness", CheckStatus.PASS, "completeness.ok", {"missing_months": 0}),
    Check("spikes", CheckStatus.PASS, "spikes.low", {"share": 0.004}),
    Check("trend", CheckStatus.PASS, "trend.significant", {"p_value": 0.001}),
    Check("automated", CheckStatus.INFO, "automated.unavailable"),
)


def _metrics(
    share: float | None,
    growth: float | None,
    direction: TrendDirection,
    views: float = 1000.0,
) -> TrendMetrics:
    return TrendMetrics(
        periods=36,
        completeness=1.0,
        views_total=views * 36,
        views_avg=views,
        per_million_avg=share,
        growth_yoy=growth,
        growth_halves=None,
        slope_per_year=None,
        trend_p_value=0.01,
        trend_direction=direction,
        seasonality_strength=None,
        spike_share=0.004,
        volatility_cv=0.1,
        automated_share=None,
    )


def _pair(
    project: WikiProject,
    share: float | None = 30.0,
    growth: float | None = -0.2,
    direction: TrendDirection = TrendDirection.FALLING,
    *,
    edition: EditionComparison | None = None,
    checks: tuple[Check, ...] = CLEAN,
    level: ReliabilityLevel = ReliabilityLevel.HIGH,
    substitute: SubstituteKind | None = None,
    measured: bool = True,
) -> PairAnalysis:
    if not measured:
        bundle = TopicBundle("chess", project, BundleStatus.NOT_FOUND)
        reliability = Reliability(ReliabilityLevel.LOW, ())
        return PairAnalysis("chess", project, bundle, None, None, EMPTY, None, None, reliability)
    source = ResolutionSource.SUBSTITUTE if substitute else ResolutionSource.SITELINK
    main = ArticleRef(project, "Chess", ArticleRole.MAIN, source)
    status = BundleStatus.SUBSTITUTE if substitute else BundleStatus.FOUND
    bundle = TopicBundle("chess", project, status, (main,), substitute_kind=substitute)
    return PairAnalysis(
        topic_id="chess",
        project=project,
        bundle=bundle,
        views=EMPTY,
        per_million=EMPTY,
        edition_total=EMPTY,
        daily=None,
        metrics=_metrics(share, growth, direction),
        reliability=Reliability(level, checks),
        findings=PairFindings(edition=edition),
    )


def _result(*pairs: PairAnalysis) -> AnalysisResult:
    return AnalysisResult(pairs=pairs, ranking=())


class TestAssess:
    def test_the_chess_example_reads_as_the_review_asked(self) -> None:
        ru = _pair(RU, 39.3, -0.17, edition=EditionComparison("yoy", -0.36, -0.22, -0.17))
        uk = _pair(UK, 28.6, -0.22, edition=EditionComparison("yoy", -0.42, -0.25, -0.22))
        first, second = assess(_result(ru, uk), normalised=True)
        assert (first.size, first.momentum, first.outcome) == (
            RelativeSize.LARGEST,
            Momentum.DECLINING,
            "large_declining",
        )
        assert (second.size, second.outcome) == (RelativeSize.SMALLER, "small_declining")
        assert first.relation is EditionRelation.LOSING
        assert (first.article_change, first.edition_change) == (-0.36, -0.22)

    def test_one_audience_has_no_size_class(self) -> None:
        (only,) = assess(_result(_pair(RU)), normalised=True)
        assert only.size is None
        assert only.outcome == "single_declining"

    def test_views_decide_the_size_without_normalisation(self) -> None:
        small_share = _pair(RU, 5.0)
        big_share = replace(
            _pair(UK, 50.0), metrics=_metrics(50.0, -0.2, TrendDirection.FALLING, views=10.0)
        )
        first, second = assess(_result(small_share, big_share), normalised=False)
        assert (first.size, second.size) == (RelativeSize.LARGEST, RelativeSize.SMALLER)

    def test_missing_article_and_substitutes_never_lead(self) -> None:
        gap = _pair(PL, measured=False)
        broader = _pair(UK, 500.0, substitute=SubstituteKind.BROADER)
        ru = _pair(RU, 30.0)
        missing, other, measured = assess(_result(gap, broader, ru), normalised=True)
        assert (missing.measured, missing.outcome) == (False, "no_article")
        assert (other.size, other.outcome) == (None, "substitute")
        assert measured.size is None  # nothing else measures the topic

    def test_evidence_is_plain_data_facts_with_concerns_first(self) -> None:
        noisy = (*CLEAN, Check("volume", CheckStatus.WARN, "volume.low", {"views_avg": 90.0}))
        (item,) = assess(_result(_pair(RU, checks=noisy)), normalised=True)
        assert [e.key for e in item.evidence] == [
            "volume.low",
            "evidence.months",
            "evidence.no_gaps",
            "evidence.spikes_ok",
        ]
        assert item.evidence[0].concern
        assert not any(e.key.startswith("trend") for e in item.evidence)

    def test_heavy_bursts_are_a_concern_with_their_share(self) -> None:
        spiky = (Check("spikes", CheckStatus.WARN, "spikes.notable", {"share": 0.3}),)
        (item,) = assess(_result(_pair(RU, checks=spiky)), normalised=True)
        assert item.evidence == (Evidence("evidence.spikes_high", {"share": 0.3}, concern=True),)


class TestRobustness:
    def _recent(self, article: float, edition: float) -> PairFindings:
        return PairFindings(
            recent=RecentChange(date(2026, 6, 1), date(2026, 8, 1), 3, 83.0, 100.0, article),
            recent_edition=RecentChange(
                date(2026, 6, 1), date(2026, 8, 1), 3, 80.0, 100.0, edition
            ),
        )

    def test_the_chess_example(self) -> None:
        ru = replace(_pair(RU, 39.3, -0.17), findings=self._recent(-0.17, -0.20))
        uk = replace(_pair(UK, 28.8, -0.22), findings=self._recent(-0.31, -0.14))
        first, second = assess(_result(ru, uk), normalised=True)
        assert (first.robustness, second.robustness) == (Robustness.MIXED, Robustness.CONFIRMED)
        assert first.recent_shift == pytest.approx(0.0375)
        assert (first.recent_months, first.recent_article, first.recent_edition) == (3, -0.17, -0.2)

    def test_a_recovery_against_a_decline_is_a_possible_turn(self) -> None:
        pair = replace(_pair(RU), findings=self._recent(0.1, -0.05))
        (item,) = assess(_result(pair), normalised=True)
        assert item.robustness is Robustness.REVERSING

    def test_without_normalisation_the_views_decide(self) -> None:
        pair = replace(_pair(RU), findings=self._recent(-0.1, 0.3))
        (item,) = assess(_result(pair), normalised=False)
        assert (item.robustness, item.recent_shift) == (Robustness.CONFIRMED, -0.1)

    def test_unknown_says_why(self) -> None:
        low = replace(_pair(RU, level=ReliabilityLevel.LOW), findings=self._recent(-0.3, 0.0))
        no_recent = _pair(UK)
        short = replace(_pair(PL, growth=None), findings=self._recent(-0.3, 0.0))
        items = assess(_result(low, no_recent, short), normalised=True)
        assert [(i.robustness, i.robustness_reason) for i in items] == [
            (Robustness.UNKNOWN, "low_trust"),
            (Robustness.UNKNOWN, "no_recent"),
            (Robustness.UNKNOWN, "no_trend"),
        ]

    def test_a_small_audience_is_too_noisy_for_three_months(self) -> None:
        small = replace(
            _pair(RU),
            metrics=_metrics(30.0, -0.2, TrendDirection.FALLING, views=90.0),
            findings=self._recent(-0.3, 0.0),
        )
        (item,) = assess(_result(small), normalised=True)
        assert (item.robustness, item.robustness_reason) == (Robustness.UNKNOWN, "low_volume")


class TestConclude:
    def test_nothing_growing_points_to_the_largest(self) -> None:
        items = assess(_result(_pair(RU, 39.3), _pair(UK, 28.6)), normalised=True)
        conclusion = conclude(items)
        assert conclusion.key == "no_growth"
        assert conclusion.candidate is items[0]

    def test_largest_and_growing_is_strong_smaller_and_growing_is_emerging(self) -> None:
        rising = TrendDirection.RISING
        strong = assess(_result(_pair(RU, 39.3, 0.2, rising), _pair(UK, 28.6)), normalised=True)
        assert conclude(strong).key == "strong"
        emerging = assess(_result(_pair(RU, 39.3), _pair(UK, 20.0, 0.2, rising)), normalised=True)
        assert (conclude(emerging).key, conclude(emerging).candidate) == ("emerging", emerging[1])

    def test_a_ranking_is_followed_and_a_disagreement_names_both(self) -> None:
        items = assess(_result(_pair(RU, 39.3), _pair(UK, 28.6)), normalised=True)
        agreed = conclude(items, [("chess", RU), ("chess", UK)])
        assert (agreed.key, agreed.candidate) == ("no_growth_ranked", items[0])
        split = conclude(items, [("chess", UK), ("chess", RU)])
        assert (split.key, split.candidate, split.largest) == (
            "no_growth_split",
            items[1],
            items[0],
        )

    def test_single_audience_unknown_trend_and_low_trust(self) -> None:
        assert conclude(assess(_result(_pair(RU)), normalised=True)).key == "single_declining"
        unknown = _pair(RU, growth=None)
        assert conclude(assess(_result(unknown), normalised=True)).key == "unknown"
        low = _pair(RU, level=ReliabilityLevel.LOW)
        assert conclude(assess(_result(low), normalised=True)).key == "low_trust"
        gap = _pair(RU, measured=False)
        assert conclude(assess(_result(gap), normalised=True)).key == "none"


def test_headline_growth_falls_back_in_order() -> None:
    yoy = _metrics(1.0, 0.1, TrendDirection.RISING)
    assert headline_growth(yoy) == (0.1, "yoy")
    none = _metrics(1.0, None, TrendDirection.UNKNOWN)
    assert headline_growth(none) == (None, None)
