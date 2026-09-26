"""Chart plan: which charts, with which data, and when a chart is left out."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import date

from wiki_interest.application.analysis import PairAnalysis, PairFindings
from wiki_interest.application.chart_plan import (
    ChartPlanner,
    audience_years_data,
    audience_years_spec,
    round_significant,
    share_years_data,
    share_years_spec,
)
from wiki_interest.application.window import read_trends
from wiki_interest.contracts.charts import AudienceYears, ChartSpec, ShareYears
from wiki_interest.contracts.request import Period
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
from wiki_interest.domain.observations import PairHistory, SeasonProfile, observe, season_profile
from wiki_interest.domain.seasonality import SeasonEvidence, SeasonReason
from wiki_interest.domain.trust import WindowTrend
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


def _planner(seasons: Mapping[tuple[str, str], SeasonProfile] | None = None) -> ChartPlanner:
    return ChartPlanner(
        Translator("en"),
        lambda _topic, project: project.domain,
        lambda _topic, project: project.language,
        show_season=_strong_season,
        seasons=seasons,
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


def _history(
    views: Callable[[int], float | None],
    *,
    topic: str = "astronomy",
    project: str = "uk.wikipedia",
    edition: float = 1e8,
    substitute: str | None = None,
) -> PairHistory:
    """72 months from 2020-09 to 2026-08: full calendar years 2021–2025 and a partial 2026."""
    months = tuple(date(2020 + (8 + k) // 12, (8 + k) % 12 + 1, 1) for k in range(72))
    return PairHistory(
        topic_id=topic,
        topic=topic,
        project=project,
        months=months,
        views=tuple(views(k) for k in range(72)),
        edition=tuple(edition for _ in range(72)),
        substitute=substitute,
    )


def _level(views: float) -> Callable[[int], float]:
    return lambda _k: views


WINDOW = Period(start=date(2024, 9, 1), end=date(2026, 8, 1))
CONTEXT = Period(start=date(2021, 1, 1), end=date(2026, 8, 1))


def _trends(histories: Sequence[PairHistory]) -> dict[str, WindowTrend]:
    return read_trends(histories, WINDOW.start)


def _data(*histories: PairHistory, absolute: bool = False) -> ShareYears:
    data = share_years_data(
        histories,
        observe(histories, window_start=WINDOW.start, trends=_trends(histories)),
        window=WINDOW,
        context=CONTEXT,
        trends=_trends(histories),
        absolute=absolute,
        topic_labels={"astronomy": "astronomy", "telescope": "telescope"},
    )
    assert data is not None
    return data


class TestMainChart:
    def test_the_history_is_context_and_the_window_has_its_trend(self) -> None:
        data = _data(_history(lambda _k: 5_000.0))
        (line,) = data.lines
        assert line.label == "uk"
        assert line.x[0] == "2021-01"  # the context starts at the first January
        # Only whole years before the window are drawn as context.
        assert [s.year for s in line.years] == [2021, 2022, 2023]
        assert {s.value for s in line.years} == {50.0}  # per million, rounded as statements do
        assert line.trend is not None
        assert (line.trend.start, line.trend.end) == ("2024-09", "2026-08")
        assert (line.trend.value_start, line.trend.value_end) == (50.0, 50.0)
        assert line.trend.verdict == "stable"
        assert (data.window_start, data.window_end) == ("2024-09", "2026-08")
        assert data.recent_months == 0

    def test_raw_views_draw_views_a_month_and_no_trend(self) -> None:
        data = _data(_history(lambda _k: 5_000.0), absolute=True)
        assert {s.value for s in data.lines[0].years} == {5_000.0}
        assert data.lines[0].trend is None

    def test_steps_and_bursts_carry_the_observation_that_found_them(self) -> None:
        def shape(k: int) -> float:
            return (6_000.0 if k < 50 else 2_500.0) * (8 if k == 56 else 1)

        data = _data(_history(shape))
        marks = {(m.kind, m.x, m.observation) for m in data.marks}
        assert ("step", "2024-11", "step:2024-11:astronomy/uk") in marks
        assert ("spike", "2025-05", "spike:astronomy/uk") in marks

    def test_lines_are_named_by_the_topic_when_one_edition_has_several(self) -> None:
        data = _data(
            _history(lambda _k: 5_000.0),
            _history(lambda _k: 1_000.0, topic="telescope"),
        )
        assert [line.label for line in data.lines] == ["astronomy", "telescope"]

    def test_an_edition_measured_through_another_article_names_it(self) -> None:
        histories = (
            _history(_level(5_000.0)),
            _history(_level(9_000.0), project="pl.wikipedia", substitute="Post"),
        )
        assert [line.label for line in _data(*histories).lines] == ["uk", "pl (Post)"]
        assert [line.label for line in _audience(*histories).lines] == ["uk", "pl (Post)"]

    def test_more_than_three_audiences_keep_the_three_largest(self) -> None:
        histories = [
            _history(_level(views), project=f"{code}.wikipedia")
            for code, views in (("uk", 1_000.0), ("cs", 4_000.0), ("pl", 3_000.0), ("de", 2_000.0))
        ]
        assert [line.label for line in _data(*histories).lines] == ["cs", "pl", "de"]

    def test_the_spec_speaks_the_report_language_and_marks_every_step(self) -> None:
        def shape(k: int) -> float:
            return 6_000.0 if k < 50 else 2_500.0

        data = _data(_history(shape))
        t = Translator("de")
        t.override({"chart.share.title": "Aufmerksamkeitsanteil"})
        spec = share_years_spec(data, t, cited=set())
        assert spec.title == "Aufmerksamkeitsanteil"
        # A step is marked whether the text cites it or not: it explains the verdict.
        assert spec.mark_labels == ["Nov 2024"]
        assert spec.year_labels[0] == "2021"
        assert spec.year_labels[-1] == "2026 (Jan – Aug)"
        assert spec.legend == [
            "average over a calendar year (context)",
            "each month",
            "trend line over the analysis period",
            "analysis period",
        ]


def _audience(*histories: PairHistory) -> AudienceYears:
    data = audience_years_data(
        histories, trends=_trends(histories), topic_labels={"astronomy": "astronomy"}
    )
    assert data is not None
    return data


class TestAudienceChart:
    def test_the_last_twelve_months_are_set_against_the_twelve_before(self) -> None:
        (line,) = _audience(_history(lambda k: 10_000.0 * 0.6 ** (k / 12))).lines
        assert line.label == "uk"
        first, last = line.years
        assert (first.start, first.end) == ("2024-09", "2025-08")
        assert (last.start, last.end) == ("2025-09", "2026-08")
        assert (first.change, first.move) == (None, None)
        # The change is computed from the shown values: the reader can check it.
        assert last.change == round((last.views / first.views - 1) * 100)
        assert last.move == "lost"

    def test_views_are_shown_to_three_significant_digits(self) -> None:
        (line,) = _audience(_history(lambda _k: 4_321.0)).lines
        assert {y.views for y in line.years} == {4_320.0}
        assert line.years[-1].move == "held"
        assert round_significant(10_473.0) == 10_500.0
        assert round_significant(552.4) == 552.0

    def test_it_shows_the_audiences_of_the_main_chart(self) -> None:
        histories = [
            _history(_level(views), project=f"{code}.wikipedia")
            for code, views in (("uk", 1_000.0), ("cs", 4_000.0), ("pl", 3_000.0), ("de", 2_000.0))
        ]
        labels = [line.label for line in _audience(*histories).lines]
        assert labels == [line.label for line in _data(*histories).lines] == ["cs", "pl", "de"]

    def test_the_spec_names_each_span(self) -> None:
        data = _audience(_history(lambda k: 10_000.0 * 0.6 ** (k / 12)))
        spec = audience_years_spec(data, Translator("de"))
        assert spec.kind == "audience_years"
        assert spec.title == "Average monthly article views"
        assert spec.year_labels == ["Sep 2024 – Aug 2025", "Sep 2025 – Aug 2026"]
        # Ukrainian has its labels written: the agent translates none of them.
        uk = audience_years_spec(data, Translator("uk"))
        assert uk.title == "Середня кількість переглядів статті за місяць"
        assert uk.year_labels[-1] == "Вер 2025 – Сер 2026"  # noqa: RUF001


class TestSecondChart:
    def test_up_to_three_audiences_need_no_second_chart(self) -> None:
        pairs = [_pair(p, [10.0] * 24, metrics=_metrics(10.0, 0.1)) for p in (UK, CS, PL)]
        assert _planner().plan(pairs, normalised=True) == []

    def test_editions_without_data_are_left_out(self) -> None:
        assert _planner().plan([_pair(UK, None)], normalised=True) == []

    def test_four_or_more_audiences_get_size_against_change(self) -> None:
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
        charts = _planner().plan(pairs, normalised=True)
        assert _ids(charts) == ["size-change"]
        scatter = charts[0]
        assert (scatter.kind, scatter.log_x) == ("scatter", True)
        first = scatter.points[0]
        assert (first.label, first.x, first.y) == ("uk", 40.0, 20.0)
        raw = _planner().plan(pairs, normalised=False)
        assert raw[0].title.startswith("Article views")


def test_season_is_drawn_only_when_the_calendar_matters() -> None:
    profile = SeasonalProfile(tuple([0.1] * 6 + [-0.1] * 6), 1, 7)

    def season(strength: float, reason: SeasonReason) -> PairFindings:
        start, end = date(2018, 1, 1), date(2026, 8, 1)
        return PairFindings(season=SeasonEvidence(profile, strength, 8, 0.9, start, end, reason))

    weak = _pair(UK, [10.0] * 24, findings=season(0.1, SeasonReason.WEAK))
    strong = _pair(CS, [10.0] * 24, findings=season(0.6, SeasonReason.SOLID))
    drawn = SeasonProfile(tuple([10.0] * 6 + [-10.0] * 6), date(2020, 9, 1), date(2026, 8, 1))
    planner = _planner({(p.topic_id, p.project.domain): drawn for p in (weak, strong)})
    assert planner.season_bars(weak) is None
    bars = planner.season_bars(strong)
    assert bars is not None
    assert bars.series[0].y == list(drawn.percents)
    assert bars.subtitle == "Computed on 2020-09 – 2026-08."
    lines = planner.season_lines([weak, strong])
    assert lines is not None
    assert [s.label for s in lines.series] == ["cs.wikipedia"]
    # Without the profile the text reads, there is no season chart.
    assert _planner().season_bars(strong) is None


def test_the_season_chart_draws_the_profile_the_text_words() -> None:
    """A burst in one March once made the chart's March +95 % while the text said October."""

    def shape(k: int) -> float:
        month = (8 + k) % 12 + 1
        return 5_000.0 * (1.3 if month == 10 else 1.0) * (8 if k == 30 else 1)

    profile = season_profile(_history(shape))
    assert profile is not None
    percents = dict(enumerate(profile.percents, start=1))
    assert max(percents, key=lambda m: percents[m]) == 10
    assert percents[3] < 10
