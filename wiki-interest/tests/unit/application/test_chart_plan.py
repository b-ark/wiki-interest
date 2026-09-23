"""Chart plan: which charts, with which data, and when a chart is left out."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pytest

from wiki_interest.application.analysis import MonthFinding, PairAnalysis, PairFindings
from wiki_interest.application.chart_plan import ChartPlanner
from wiki_interest.contracts.charts import ChartSpec
from wiki_interest.domain.findings import SeasonalProfile
from wiki_interest.domain.models import (
    ArticleRef,
    ArticleRole,
    BundleStatus,
    Granularity,
    Point,
    Reliability,
    ReliabilityLevel,
    ResolutionSource,
    Series,
    SeriesUnit,
    TopicBundle,
    TrendDirection,
    TrendMetrics,
    WikiProject,
)
from wiki_interest.domain.seasonality import SeasonEvidence, SeasonReason
from wiki_interest.i18n import Translator

UK, CS, PL, DE, FR = (WikiProject(c) for c in ("uk", "cs", "pl", "de", "fr"))


def _monthly(values: Sequence[float | None]) -> Series:
    points = tuple(Point(date(2024 + i // 12, i % 12 + 1, 1), v) for i, v in enumerate(values))
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, points)


def _pair(
    project: WikiProject,
    views: Sequence[float | None] | None,
    *,
    findings: PairFindings | None = None,
    daily: Series | None = None,
    metrics: TrendMetrics | None = None,
    edition: Sequence[float | None] | None = None,
) -> PairAnalysis:
    main = ArticleRef(project, "Main", ArticleRole.MAIN, ResolutionSource.SITELINK)
    bundle = TopicBundle("topic", project, BundleStatus.FOUND, (main,))
    series = _monthly(views) if views is not None else None
    return PairAnalysis(
        topic_id="topic",
        project=project,
        bundle=bundle,
        views=series,
        per_million=series,
        edition_total=_monthly(edition or [1e6] * len(views or [0] * 24)),
        daily=daily,
        metrics=metrics,
        reliability=Reliability(ReliabilityLevel.HIGH, ()),
        findings=findings or PairFindings(),
    )


def _strong_season(pair: PairAnalysis) -> bool:
    season = pair.findings.season
    return season is not None and season.solid


def _planner() -> ChartPlanner:
    return ChartPlanner(
        Translator("en"),
        lambda _topic, project: project.domain,
        "Source · Period",
        lambda _topic, project: project.language,
        show_season=_strong_season,
    )


def _metrics(share: float, change: float) -> TrendMetrics:
    return TrendMetrics(
        periods=24,
        completeness=1.0,
        views_total=24_000.0,
        views_avg=1000.0,
        per_million_avg=share,
        growth_yoy=change,
        growth_halves=None,
        slope_per_year=None,
        trend_p_value=0.01,
        trend_direction=TrendDirection.RISING,
        seasonality_strength=None,
        spike_share=None,
        volatility_cv=None,
        automated_share=None,
    )


def _ids(charts: list[ChartSpec]) -> list[str]:
    return [c.id for c in charts]


class TestMainChart:
    def test_one_panel_per_edition_article_against_edition_as_indexes(self) -> None:
        rising = [100.0 + 5 * i for i in range(24)]
        chart = _planner().main([_pair(UK, rising), _pair(CS, [50.0] * 24)])
        assert chart is not None
        assert (chart.kind, chart.size, chart.reference_y) == ("panels", "wide", 100.0)
        assert [p.title for p in chart.panels] == ["uk.wikipedia", "cs.wikipedia"]
        assert chart.subtitle is not None
        assert "loses attention share" in chart.subtitle
        points, smooth, edition = chart.panels[0].series
        assert (points.style, smooth.style, edition.style) == ("points", "line", "dashed")
        assert points.color == smooth.color != edition.color
        # The first year averages 100; three-month averages start in the third month.
        first_year = [v for v in points.y[:12] if v is not None]
        assert sum(first_year) / 12 == pytest.approx(100.0, abs=0.1)
        assert smooth.y[:2] == [None, None]
        assert edition.y[2] == 100.0

    def test_months_that_stand_out_are_labelled(self) -> None:
        spike = MonthFinding(
            date(2025, 5, 1),
            (("article_views", 1.9), ("attention_share", 1.85)),
            "possible_bot",
            in_change=True,
            in_recent=False,
            change_without=-0.1,
        )
        pair = _pair(UK, [10.0] * 24, findings=PairFindings(months=(spike,)))
        chart = _planner().main([pair])
        assert chart is not None
        (note,) = chart.panels[0].notes
        assert (note.x, note.text) == ("2025-05", "2025-05 ×1.9, possibly bots")

    def test_editions_without_data_are_left_out(self) -> None:
        assert _planner().main([_pair(UK, None)]) is None
        assert _planner().plan([_pair(UK, None)], normalised=True, single_topic=True) == []


class TestSecondChart:
    def test_one_topic_in_two_editions_gets_the_change_month_by_month(self) -> None:
        rising = [100.0 * 1.02**i for i in range(24)]
        charts = _planner().plan(
            [_pair(UK, rising), _pair(CS, [50.0] * 24)], normalised=True, single_topic=True
        )
        assert _ids(charts) == ["main", "change"]
        change = charts[1]
        assert change.kind == "lines"
        assert change.reference_y == 0.0
        uk, cs = change.series
        assert uk.x[0] == "2025-03"  # 3 months against the same 3 a year earlier
        assert uk.y[0] == pytest.approx((1.02**12 - 1) * 100, abs=0.2)
        assert set(cs.y) == {0.0}
        assert change.title.startswith("Attention share")

    def test_up_to_four_audiences_get_before_and_after(self) -> None:
        pairs = [_pair(p, [10.0] * 12 + [12.0] * 12) for p in (UK, CS, PL)]
        charts = _planner().plan(pairs, normalised=True, single_topic=True)
        assert _ids(charts) == ["main", "before-after"]
        before, after = charts[1].series
        assert before.x == ["uk", "cs", "pl"]
        assert (before.y, after.y) == ([10.0] * 3, [12.0] * 3)
        assert before.label == "previous 12 months"
        assert charts[1].x_label == "article views per million edition views"

    def test_two_topics_in_one_edition_are_compared_before_and_after(self) -> None:
        pairs = [_pair(UK, [10.0] * 24), _pair(CS, [20.0] * 24)]
        charts = _planner().plan(pairs, normalised=True, single_topic=False)
        assert _ids(charts) == ["main", "before-after"]

    def test_a_short_period_compares_halves(self) -> None:
        chart = _planner().before_after([_pair(UK, [10.0] * 8 + [20.0] * 8)], normalised=True)
        assert chart is not None
        assert chart.series[0].label == "first half"
        assert chart.series[1].y == [20.0]

    def test_five_or_more_audiences_get_size_against_change(self) -> None:
        pairs = [
            _pair(p, [10.0] * 24, metrics=_metrics(share, change))
            for p, share, change in (
                (UK, 40.0, 0.2),
                (CS, 10.0, -0.1),
                (PL, 5.0, 0.0),
                (DE, 2.0, 0.05),
                (FR, 1.0, -0.3),
            )
        ]
        charts = _planner().plan(pairs, normalised=True, single_topic=True)
        assert _ids(charts) == ["main", "size-change"]
        scatter = charts[1]
        assert (scatter.kind, scatter.log_x) == ("scatter", True)
        first = scatter.points[0]
        assert (first.label, first.x, first.y) == ("uk", 40.0, 20.0)

    def test_raw_views_when_not_normalised(self) -> None:
        pairs = [_pair(p, [10.0] * 12 + [12.0] * 12) for p in (UK, CS, PL)]
        chart = _planner().before_after(pairs, normalised=False)
        assert chart is not None
        assert chart.title.startswith("Article views")


def test_season_is_drawn_only_when_the_calendar_matters() -> None:
    profile = SeasonalProfile(tuple([0.1] * 6 + [-0.1] * 6), 1, 7)

    def season(strength: float, reason: SeasonReason) -> PairFindings:
        start, end = date(2018, 1, 1), date(2026, 8, 1)
        return PairFindings(season=SeasonEvidence(profile, strength, 8, 0.9, start, end, reason))

    weak = _pair(UK, [10.0] * 24, findings=season(0.1, SeasonReason.WEAK))
    strong = _pair(CS, [10.0] * 24, findings=season(0.6, SeasonReason.SOLID))
    planner = _planner()
    assert planner.season_bars(weak) is None
    assert planner.season_bars(strong) is not None
    lines = planner.season_lines([weak, strong])
    assert lines is not None
    assert [s.label for s in lines.series] == ["cs.wikipedia"]
