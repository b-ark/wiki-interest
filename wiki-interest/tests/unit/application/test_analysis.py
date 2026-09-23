"""Analysis step: pairs, normalisation switch, context articles, findings, ranking."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date

import pytest

from wiki_interest.application.analysis import AnalysisSettings, analyse
from wiki_interest.application.loading import ContextSeries, LoadedSeries
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
            ArticleRef(project, "Related", ArticleRole.RELATED, ResolutionSource.LEAD_LINK)
        )
    return TopicBundle("topic", project, BundleStatus.FOUND, tuple(articles))


def _topic(*bundles: TopicBundle) -> ResolvedTopic:
    return ResolvedTopic("topic", "topic", "Q1", "topic", bundles)


def _loaded(
    project: WikiProject,
    main_views: Series | None,
    total: Series | None = None,
    *,
    context: tuple[ContextSeries, ...] = (),
    daily: Series | None = None,
) -> LoadedSeries:
    return LoadedSeries(
        "topic", project, main_views, total or _total(), daily, None, context=context
    )


class TestPairs:
    @pytest.mark.parametrize("volume", [1000.0, 100_000.0])
    def test_automated_check_uses_the_main_title_for_both_traffic_classes(
        self, volume: float
    ) -> None:
        # Main views include redirects; the automated share compares the canonical title only.
        loaded = replace(
            _loaded(UK, _total(level=volume)),
            main_automated=_total(level=100.0),
            main_user_for_automated=_total(level=100.0),
        )
        pair = analyse([_topic(_bundle(UK))], [loaded], weights=WEIGHTS).pair("topic", UK)
        assert pair.metrics is not None
        assert pair.metrics.automated_share == pytest.approx(0.5)
        check = next(c for c in pair.reliability.checks if c.name == "automated")
        assert check.status is CheckStatus.WARN

    def test_automated_check_is_unavailable_without_matching_user_traffic(self) -> None:
        loaded = replace(_loaded(UK, _rising()), main_automated=_total(level=100.0))
        pair = analyse([_topic(_bundle(UK))], [loaded], weights=WEIGHTS).pair("topic", UK)
        assert pair.metrics is not None
        assert pair.metrics.automated_share is None
        check = next(c for c in pair.reliability.checks if c.name == "automated")
        assert check.reason_key == "automated.unavailable"

    def test_rising_main_article_is_detected_with_normalised_metrics(self) -> None:
        result = analyse([_topic(_bundle(UK))], [_loaded(UK, _rising())], weights=WEIGHTS)
        pair = result.pair("topic", UK)
        assert pair.metrics is not None
        assert pair.metrics.trend_direction is TrendDirection.RISING
        assert pair.metrics.per_million_avg is not None
        assert pair.per_million is not None
        assert pair.per_million.unit is SeriesUnit.PER_MILLION
        assert pair.reliability.level in {ReliabilityLevel.HIGH, ReliabilityLevel.MEDIUM}

    def test_absolute_mode_skips_normalisation(self) -> None:
        settings = AnalysisSettings(normalise=False)
        result = analyse(
            [_topic(_bundle(UK))], [_loaded(UK, _rising())], weights=WEIGHTS, settings=settings
        )
        pair = result.pair("topic", UK)
        assert pair.per_million is None
        assert pair.metrics is not None
        assert pair.metrics.per_million_avg is None

    def test_related_articles_are_context_with_their_own_numbers(self) -> None:
        related = ArticleRef(UK, "Related", ArticleRole.RELATED, ResolutionSource.LEAD_LINK)
        context = (ContextSeries(related, _rising(base=5000.0)),)
        result = analyse(
            [_topic(_bundle(UK))], [_loaded(UK, _flat(), context=context)], weights=WEIGHTS
        )
        pair = result.pair("topic", UK)
        assert pair.metrics is not None
        # A rising neighbour never leaks into the topic's own numbers.
        assert pair.metrics.views_avg == pytest.approx(1000.0)
        (item,) = pair.context
        assert item.title == "Related"
        assert item.views_avg == pytest.approx(5000.0 + 50.0 * 23 / 2)
        assert item.growth is not None
        assert item.growth > 0

    def test_findings_compare_the_article_with_its_edition(self) -> None:
        shrinking_edition = _series([1e6 - 10_000.0 * i for i in range(24)])
        result = analyse(
            [_topic(_bundle(UK))],
            [_loaded(UK, _flat(), shrinking_edition)],
            weights=WEIGHTS,
        )
        edition = result.pair("topic", UK).findings.edition
        assert edition is not None
        assert edition.basis == "yoy"
        assert edition.article_change == pytest.approx(0.0, abs=0.01)
        assert edition.edition_change < -0.1
        assert edition.share_change > 0.1

    def test_findings_date_a_burst_in_daily_views(self) -> None:
        days = [date(2025, 1, 1).toordinal() + i for i in range(120)]
        values = [100.0] * 120
        values[60] = 900.0
        daily = Series(
            Granularity.DAILY,
            SeriesUnit.VIEWS,
            tuple(Point(date.fromordinal(d), v) for d, v in zip(days, values, strict=True)),
        )
        result = analyse(
            [_topic(_bundle(UK))], [_loaded(UK, _flat(), daily=daily)], weights=WEIGHTS
        )
        (burst,) = result.pair("topic", UK).findings.anomalies
        assert burst.peak_day == date.fromordinal(days[60])

    def test_not_found_pair_has_low_reliability_and_no_metrics(self) -> None:
        empty = TopicBundle("topic", CS, BundleStatus.NOT_FOUND)
        result = analyse(
            [_topic(_bundle(UK), empty)],
            [_loaded(UK, _rising()), _loaded(CS, None)],
            weights=WEIGHTS,
        )
        pair = result.pair("topic", CS)
        assert pair.metrics is None
        assert pair.views is None
        assert pair.reliability.level is ReliabilityLevel.LOW
        assert [c.reason_key for c in pair.reliability.checks] == ["resolution.not_found"]

    def test_unknown_pair_raises(self) -> None:
        result = analyse([_topic(_bundle(UK))], [_loaded(UK, _rising())], weights=WEIGHTS)
        with pytest.raises(KeyError):
            result.pair("topic", CS)


class TestRanking:
    def test_ranking_prefers_the_growing_edition(self) -> None:
        result = analyse(
            [_topic(_bundle(UK), _bundle(CS))],
            [_loaded(UK, _rising()), _loaded(CS, _flat())],
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
