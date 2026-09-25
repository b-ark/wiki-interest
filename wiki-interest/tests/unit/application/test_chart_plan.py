"""Chart plan: which charts, with which data, and when a chart is left out."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date

from wiki_interest.application.analysis import PairAnalysis, PairFindings
from wiki_interest.application.chart_plan import (
    ChartPlanner,
    audience_years_data,
    audience_years_spec,
    share_years_data,
    share_years_spec,
)
from wiki_interest.contracts.charts import AudienceYears, ChartSpec, ShareYears
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
from wiki_interest.domain.observations import PairHistory, observe
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


def _history(
    views: Callable[[int], float | None],
    *,
    topic: str = "astronomy",
    project: str = "uk.wikipedia",
    edition: float = 1e8,
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
    )


def _level(views: float) -> Callable[[int], float]:
    return lambda _k: views


def _data(*histories: PairHistory, absolute: bool = False) -> ShareYears:
    data = share_years_data(
        histories,
        observe(histories),
        trend_start=None,
        absolute=absolute,
        topic_labels={"astronomy": "astronomy", "telescope": "telescope"},
    )
    assert data is not None
    return data


class TestMainChart:
    def test_the_years_are_the_calendar_years_the_observations_read(self) -> None:
        data = _data(_history(lambda _k: 5_000.0))
        (line,) = data.lines
        assert line.label == "uk"
        assert line.x[0] == "2021-01"  # the cut 2020 is left out, as the observations do
        assert [s.year for s in line.years] == [2021, 2022, 2023, 2024, 2025, 2026]
        last = line.years[-1]
        assert (last.start, last.end, last.partial) == ("2026-01", "2026-08", True)
        assert {s.value for s in line.years} == {50.0}  # per million, rounded as statements do

    def test_raw_views_draw_views_a_month(self) -> None:
        data = _data(_history(lambda _k: 5_000.0), absolute=True)
        assert {s.value for s in data.lines[0].years} == {5_000.0}

    def test_steps_and_bursts_carry_the_observation_that_found_them(self) -> None:
        def shape(k: int) -> float:
            return (6_000.0 if k < 50 else 2_500.0) * (8 if k == 20 else 1)

        data = _data(_history(shape))
        marks = {(m.kind, m.x, m.observation) for m in data.marks}
        assert ("step", "2024-11", "step:astronomy/uk") in marks
        assert ("spike", "2022-05", "spike:astronomy/uk") in marks

    def test_lines_are_named_by_the_topic_when_one_edition_has_several(self) -> None:
        data = _data(
            _history(lambda _k: 5_000.0),
            _history(lambda _k: 1_000.0, topic="telescope"),
        )
        assert [line.label for line in data.lines] == ["astronomy", "telescope"]

    def test_more_than_three_audiences_keep_the_three_largest(self) -> None:
        histories = [
            _history(_level(views), project=f"{code}.wikipedia")
            for code, views in (("uk", 1_000.0), ("cs", 4_000.0), ("pl", 3_000.0), ("de", 2_000.0))
        ]
        assert [line.label for line in _data(*histories).lines] == ["cs", "pl", "de"]

    def test_the_spec_speaks_the_report_language_and_marks_what_the_text_cites(self) -> None:
        def shape(k: int) -> float:
            return 6_000.0 if k < 50 else 2_500.0

        data = _data(_history(shape))
        t = Translator("uk")
        t.override({"chart.share.title": "Частка уваги за роками"})
        spec = share_years_spec(data, t, cited=set())
        assert spec.title == "Частка уваги за роками"
        assert spec.mark_labels == [None]  # the text does not cite the step: no label
        assert spec.year_labels[-1] == "2026 (Jan – Aug)"
        cited = share_years_spec(data, Translator("en"), cited={"step:astronomy/uk"})
        assert cited.mark_labels == ["level changed: Nov 2024"]
        assert cited.title == "Share of Wikipedia views, by year"


def _audience(*histories: PairHistory) -> AudienceYears:
    data = audience_years_data(histories, trend_start=None, topic_labels={"astronomy": "astronomy"})
    assert data is not None
    return data


class TestAudienceChart:
    def test_each_year_is_set_against_the_same_months_a_year_earlier(self) -> None:
        (line,) = _audience(_history(lambda k: 10_000.0 * 0.6 ** (k / 12))).lines
        assert line.label == "uk"
        assert [y.year for y in line.years] == [2021, 2022, 2023, 2024, 2025, 2026]
        first, *rest = line.years
        assert (first.change, first.move) == (None, None)  # no whole year of data before 2021
        # The edition holds still: the article's fall of 40 % a year is its share's too; the
        # partial 2026 against January–August 2025 falls as much.
        assert {(y.change, y.move) for y in rest} == {(-40.0, "lost")}
        assert rest[-1].partial

    def test_views_are_rounded_as_the_text_rounds_them(self) -> None:
        (line,) = _audience(_history(lambda _k: 4_321.0)).lines
        assert {y.views for y in line.years} == {4_300.0}
        assert {y.move for y in line.years[1:]} == {"held"}

    def test_it_shows_the_audiences_of_the_main_chart(self) -> None:
        histories = [
            _history(_level(views), project=f"{code}.wikipedia")
            for code, views in (("uk", 1_000.0), ("cs", 4_000.0), ("pl", 3_000.0), ("de", 2_000.0))
        ]
        labels = [line.label for line in _audience(*histories).lines]
        assert labels == [line.label for line in _data(*histories).lines] == ["cs", "pl", "de"]

    def test_the_spec_says_what_the_partial_year_is_compared_with(self) -> None:
        data = _audience(_history(lambda k: 10_000.0 * 0.6 ** (k / 12)))
        t = Translator("uk")
        t.override({"chart.audience.lost": "▼ втратила частку"})
        spec = audience_years_spec(data, t)
        assert spec.kind == "audience_years"
        assert spec.title == "Average monthly article views, by year"
        assert spec.year_labels[-1] == "2026 (Jan – Aug)"
        assert spec.note == "2026: January–August vs the same months of 2025."
        assert spec.move_labels["lost"] == "▼ втратила частку"
        assert set(spec.move_labels) == {"gained", "held", "lost"}

    def test_full_years_need_no_note(self) -> None:
        full = _history(lambda _k: 5_000.0)
        months = full.months[:64]  # to 2025-12
        data = _audience(
            PairHistory(
                topic_id=full.topic_id,
                topic=full.topic,
                project=full.project,
                months=months,
                views=full.views[:64],
                edition=full.edition[:64],
            )
        )
        assert audience_years_spec(data, Translator("en")).note is None


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
    planner = _planner()
    assert planner.season_bars(weak) is None
    assert planner.season_bars(strong) is not None
    lines = planner.season_lines([weak, strong])
    assert lines is not None
    assert [s.label for s in lines.series] == ["cs.wikipedia"]
