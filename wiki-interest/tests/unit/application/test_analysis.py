"""Analysis step: pairs, normalisation switch, bundle-vs-main check, ranking."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pytest

from wiki_interest.application.analysis import AnalysisSettings, analyse
from wiki_interest.application.loading import LoadedSeries
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.domain.models import (
    ArticleRef,
    ArticleRole,
    BundleStatus,
    CheckStatus,
    Granularity,
    Point,
    RankingWeights,
    ReliabilityLevel,
    ReliabilityThresholds,
    ResolutionSource,
    Series,
    SeriesUnit,
    TopicBundle,
    TrendDirection,
    WikiProject,
)

UK = WikiProject("uk")
CS = WikiProject("cs")
WEIGHTS = RankingWeights()


def _month(index: int) -> date:
    return date(2024 + index // 12, index % 12 + 1, 1)


def _series(values: Sequence[float | None]) -> Series:
    points = tuple(Point(_month(i), v) for i, v in enumerate(values))
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, points)


def _rising(n: int = 24, base: float = 1000.0, step: float = 50.0) -> Series:
    return _series([base + step * i for i in range(n)])


def _flat(n: int = 24, level: float = 1000.0) -> Series:
    return _series([level + (5.0 if i % 2 else -5.0) for i in range(n)])


def _total(n: int = 24, level: float = 1e6) -> Series:
    return _series([level] * n)


def _bundle(project: WikiProject, *, related: bool = True) -> TopicBundle:
    main = ArticleRef(project, "Main", ArticleRole.MAIN, ResolutionSource.SITELINK, qid="Q1")
    articles: list[ArticleRef] = [main]
    if related:
        articles.append(
            ArticleRef(project, "Related", ArticleRole.RELATED, ResolutionSource.LEAD_LINK, 0.5)
        )
    return TopicBundle("topic", project, BundleStatus.FOUND, tuple(articles))


def _topic(*bundles: TopicBundle) -> ResolvedTopic:
    return ResolvedTopic("topic", "topic", "Q1", "topic", bundles)


def _loaded(
    project: WikiProject,
    bundle_views: Series | None,
    main_views: Series | None,
    total: Series | None = None,
) -> LoadedSeries:
    return LoadedSeries("topic", project, bundle_views, main_views, total or _total(), None, None)


class TestPairs:
    def test_rising_bundle_is_detected_with_normalised_metrics(self) -> None:
        result = analyse(
            [_topic(_bundle(UK))], [_loaded(UK, _rising(), _rising())], weights=WEIGHTS
        )
        pair = result.pair("topic", UK)
        assert pair.metrics is not None
        assert pair.metrics.trend_direction is TrendDirection.RISING
        assert pair.metrics.per_million_avg is not None
        assert pair.bundle_per_million is not None
        assert pair.bundle_per_million.unit is SeriesUnit.PER_MILLION
        assert pair.main_metrics is not None  # the bundle has a related article
        assert pair.reliability.level in {ReliabilityLevel.HIGH, ReliabilityLevel.MEDIUM}

    def test_absolute_mode_skips_normalisation(self) -> None:
        settings = AnalysisSettings(normalise=False)
        result = analyse(
            [_topic(_bundle(UK))],
            [_loaded(UK, _rising(), _rising())],
            weights=WEIGHTS,
            settings=settings,
        )
        pair = result.pair("topic", UK)
        assert pair.bundle_per_million is None
        assert pair.main_per_million is None
        assert pair.metrics is not None
        assert pair.metrics.per_million_avg is None

    def test_main_only_bundle_has_no_bundle_consistency_check(self) -> None:
        result = analyse(
            [_topic(_bundle(UK, related=False))],
            [_loaded(UK, _rising(), _rising())],
            weights=WEIGHTS,
        )
        pair = result.pair("topic", UK)
        assert pair.main_metrics is None
        assert not pair.has_related_articles
        assert "bundle" not in {c.name for c in pair.reliability.checks}

    def test_diverging_main_and_bundle_is_flagged(self) -> None:
        result = analyse(
            [_topic(_bundle(UK))],
            [_loaded(UK, _rising(), _flat())],
            weights=WEIGHTS,
        )
        pair = result.pair("topic", UK)
        check = next(c for c in pair.reliability.checks if c.name == "bundle")
        assert check.status is CheckStatus.WARN
        assert check.reason_key == "bundle.diverges"

    def test_not_found_pair_has_low_reliability_and_no_metrics(self) -> None:
        empty = TopicBundle("topic", CS, BundleStatus.NOT_FOUND)
        result = analyse(
            [_topic(_bundle(UK), empty)],
            [_loaded(UK, _rising(), _rising()), _loaded(CS, None, None)],
            weights=WEIGHTS,
        )
        pair = result.pair("topic", CS)
        assert pair.metrics is None
        assert pair.reliability.level is ReliabilityLevel.LOW
        assert [c.reason_key for c in pair.reliability.checks] == ["resolution.not_found"]

    def test_unknown_pair_raises(self) -> None:
        result = analyse(
            [_topic(_bundle(UK))], [_loaded(UK, _rising(), _rising())], weights=WEIGHTS
        )
        with pytest.raises(KeyError):
            result.pair("topic", CS)


class TestRanking:
    def test_ranking_prefers_the_growing_edition(self) -> None:
        result = analyse(
            [_topic(_bundle(UK), _bundle(CS))],
            [_loaded(UK, _rising(), _rising()), _loaded(CS, _flat(), _flat())],
            weights=WEIGHTS,
        )
        assert [r.project for r in result.ranking] == [UK, CS]
        assert result.ranking[0].score > result.ranking[1].score

    def test_settings_from_thresholds_align_alpha(self) -> None:
        thresholds = ReliabilityThresholds(trend_p_value=0.01)
        settings = AnalysisSettings.from_thresholds(thresholds, normalise=False)
        assert settings.metrics.alpha == 0.01
        assert settings.thresholds is thresholds
        assert settings.normalise is False
