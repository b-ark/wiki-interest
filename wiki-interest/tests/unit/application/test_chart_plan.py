"""Chart plan: which charts, with which data, and when a chart is left out."""

from __future__ import annotations

from datetime import date

from wiki_interest.application.analysis import AnalysisResult, PairAnalysis, PairFindings
from wiki_interest.application.chart_plan import ChartPlanner
from wiki_interest.domain.findings import Anomaly, EditionComparison, SeasonalProfile
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
    WikiProject,
)
from wiki_interest.domain.seasonality import SeasonEvidence, SeasonReason
from wiki_interest.i18n import Translator

UK, CS = WikiProject("uk"), WikiProject("cs")


def _monthly(values: list[float | None]) -> Series:
    points = tuple(Point(date(2024 + i // 12, i % 12 + 1, 1), v) for i, v in enumerate(values))
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, points)


def _pair(
    project: WikiProject,
    views: list[float | None] | None,
    *,
    findings: PairFindings | None = None,
    daily: Series | None = None,
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
        edition_total=_monthly([1e6] * 24),
        daily=daily,
        metrics=None,
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


def test_the_main_chart_is_the_share_across_the_page_with_an_explanation() -> None:
    chart = _planner().main([_pair(UK, [10.0] * 24), _pair(CS, [20.0] * 24)], normalised=True)
    assert chart is not None
    assert (chart.id, chart.kind, chart.size) == ("share", "lines", "wide")
    assert chart.title == "How visible the topic is inside each Wikipedia"
    assert chart.subtitle is not None
    assert "per million" in chart.subtitle


def test_one_audience_gets_its_share_with_a_trend_line() -> None:
    chart = _planner().main([_pair(UK, [10.0] * 24)], normalised=True)
    assert chart is not None
    assert (chart.kind, chart.size, chart.id) == ("trend", "wide", "share-topic-uk")
    assert chart.trend_y is not None
    absolute = _planner().main([_pair(UK, [10.0] * 24)], normalised=False)
    assert absolute is not None
    assert (absolute.id, absolute.subtitle) == ("views-topic-uk", None)


def test_views_on_a_log_axis_when_editions_differ_by_orders_of_magnitude() -> None:
    big = _pair(UK, [100_000.0] * 24)
    small = _pair(CS, [1_000.0] * 24)
    chart = _planner().main([big, small], normalised=False)
    assert chart is not None
    assert chart.log_y
    assert "log" in chart.y_label
    near = _planner().main([big, _pair(CS, [50_000.0] * 24)], normalised=False)
    assert near is not None
    assert not near.log_y


def test_a_lone_chart_is_widened_with_its_footnote() -> None:
    planner = _planner()
    chart = planner.against_edition(_pair(UK, [10.0] * 24))
    assert chart is not None
    assert (chart.size, chart.footnote) == ("half", None)
    wide = planner.widen(chart)
    assert (wide.size, wide.footnote) == ("wide", "Source · Period")


def test_bursts_are_shaded_in_monthly_and_daily_charts() -> None:
    burst = Anomaly(date(2024, 3, 30), date(2024, 4, 1), date(2024, 3, 31), 900.0, 90.0, 10.0, 0.2)
    days = Series(
        Granularity.DAILY,
        SeriesUnit.VIEWS,
        tuple(Point(date.fromordinal(date(2024, 3, 1).toordinal() + i), 5.0) for i in range(40)),
    )
    pair = _pair(UK, [10.0] * 24, findings=PairFindings(anomalies=(burst,)), daily=days)
    monthly = _planner().main([pair], normalised=True)
    assert monthly is not None
    assert monthly.highlight_x == ["2024-03", "2024-04"]
    daily = _planner().daily(pair)
    assert daily is not None
    assert daily.highlight_x == ["2024-03-30", "2024-03-31", "2024-04-01"]


def test_charts_without_data_are_left_out() -> None:
    planner = _planner()
    empty = _pair(UK, None)
    assert planner.main([empty], normalised=True) is None
    assert planner.main([empty, empty], normalised=True) is None
    assert planner.main([empty, empty], normalised=False) is None
    assert planner.against_edition(empty) is None
    assert planner.daily(empty) is None
    assert planner.edition_growth([empty]) is None
    assert planner.season_lines([empty]) is None
    assert planner.ranking(AnalysisResult(pairs=(), ranking=())) is None
    zero_base = _pair(UK, [0.0] * 24)
    assert planner.against_edition(zero_base) is None


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


def test_edition_growth_uses_short_labels_and_states_mixed_bases() -> None:
    yoy = PairFindings(edition=EditionComparison("yoy", 0.1, 0.0, 0.1))
    halves = PairFindings(edition=EditionComparison("halves", -0.1, 0.0, -0.1))
    chart = _planner().edition_growth(
        [_pair(UK, [1.0] * 24, findings=yoy), _pair(CS, [1.0] * 24, findings=halves)]
    )
    assert chart is not None
    assert chart.series[0].x == ["uk", "cs"]
    assert chart.series[0].y == [10.0, -10.0]
