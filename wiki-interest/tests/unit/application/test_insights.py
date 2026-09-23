"""Choosing findings: per edition, grouped across editions, unmeasured editions, seasons."""

from __future__ import annotations

from datetime import date

import pytest

from wiki_interest.application.analysis import AnalysisResult, PairAnalysis, PairFindings
from wiki_interest.application.insights import (
    InsightSettings,
    SeasonVisibility,
    season_visibility,
    select_insights,
)
from wiki_interest.domain.findings import (
    Anomaly,
    LevelShift,
    RecentChange,
    SeasonalProfile,
)
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
    SubstituteKind,
    TopicBundle,
    TrendDirection,
    TrendMetrics,
    WikiProject,
)

UK, CS, PL = WikiProject("uk"), WikiProject("cs"), WikiProject("pl")
EMPTY = Series(Granularity.MONTHLY, SeriesUnit.VIEWS, (Point(date(2025, 1, 1), 1.0),))


def _months(count: int) -> Series:
    points = tuple(Point(date(2020 + i // 12, i % 12 + 1, 1), 100.0) for i in range(count))
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, points)


def _metrics() -> TrendMetrics:
    return TrendMetrics(
        periods=24,
        completeness=1.0,
        views_total=24_000.0,
        views_avg=1000.0,
        per_million_avg=10.0,
        growth_yoy=0.0,
        growth_halves=0.0,
        slope_per_year=0.0,
        trend_p_value=0.5,
        trend_direction=TrendDirection.FLAT,
        seasonality_strength=0.1,
        spike_share=0.01,
        volatility_cv=0.1,
        automated_share=0.01,
    )


def _pair(
    project: WikiProject,
    *,
    findings: PairFindings | None = None,
    substitute: SubstituteKind | None = None,
    measured: bool = True,
    views: Series = EMPTY,
) -> PairAnalysis:
    if not measured:
        bundle = TopicBundle("topic", project, BundleStatus.NOT_FOUND)
        reliability = Reliability(ReliabilityLevel.LOW, ())
        return PairAnalysis("topic", project, bundle, None, None, EMPTY, None, None, reliability)
    source = ResolutionSource.SUBSTITUTE if substitute else ResolutionSource.SITELINK
    main = ArticleRef(project, "Main", ArticleRole.MAIN, source)
    status = BundleStatus.SUBSTITUTE if substitute else BundleStatus.FOUND
    bundle = TopicBundle("topic", project, status, (main,), substitute_kind=substitute)
    return PairAnalysis(
        topic_id="topic",
        project=project,
        bundle=bundle,
        views=views,
        per_million=views,
        edition_total=EMPTY,
        daily=None,
        metrics=_metrics(),
        reliability=Reliability(ReliabilityLevel.HIGH, ()),
        findings=findings or PairFindings(),
    )


def _result(*pairs: PairAnalysis) -> AnalysisResult:
    return AnalysisResult(pairs=pairs, ranking=())


def _season(peak: int, trough: int) -> SeasonalProfile:
    effects = [0.0] * 12
    effects[peak - 1] = 0.4
    effects[trough - 1] = -0.3
    return SeasonalProfile(tuple(effects), peak, trough)


def _seasonal(strength: float) -> PairFindings:
    return PairFindings(seasonality=_season(9, 7), seasonality_strength=strength)


class TestPerEdition:
    def test_every_detector_contributes_and_the_strongest_lead(self) -> None:
        findings = PairFindings(
            level_shift=LevelShift(date(2025, 3, 1), 10.0, 16.0, 0.6, 12),
            anomalies=(
                Anomaly(
                    date(2025, 5, 1), date(2025, 5, 1), date(2025, 5, 1), 900.0, 90.0, 10.0, 0.1
                ),
            ),
            recent=RecentChange(date(2026, 6, 1), date(2026, 8, 1), 3, 150.0, 100.0, 0.5),
            seasonality=_season(9, 7),
            seasonality_strength=0.6,
        )
        settings = InsightSettings(max_per_pair=5)
        pair = _pair(UK, findings=findings, views=_months(72))
        kinds = [i.kind for i in select_insights(_result(pair), settings)]
        assert kinds[0] == "level_shift"
        assert set(kinds) == {"level_shift", "burst_day", "season"}

    def test_weak_or_small_patterns_stay_out(self) -> None:
        findings = PairFindings(
            seasonality=_season(9, 7),
            seasonality_strength=0.1,
        )
        assert select_insights(_result(_pair(UK, findings=findings))) == ()

    def test_multi_day_burst_and_no_recent_line(self) -> None:
        """The last months are the robustness line's job, not a finding's."""
        findings = PairFindings(
            anomalies=(
                Anomaly(
                    date(2025, 5, 1), date(2025, 5, 3), date(2025, 5, 2), 900.0, 90.0, 10.0, 0.1
                ),
            ),
            recent=RecentChange(date(2026, 6, 1), date(2026, 8, 1), 3, 150.0, 100.0, 0.5),
            recent_edition=RecentChange(date(2026, 6, 1), date(2026, 8, 1), 3, 95.0, 100.0, -0.05),
        )
        kinds = {i.kind for i in select_insights(_result(_pair(UK, findings=findings)))}
        assert kinds == {"burst"}


class TestSeasons:
    @pytest.mark.parametrize(
        ("strength", "months", "requested", "expected"),
        [
            (0.1, 72, False, SeasonVisibility.HIDDEN),
            (0.4, 36, False, SeasonVisibility.TENTATIVE),
            (0.4, 72, False, SeasonVisibility.STATED),
            (0.6, 72, False, SeasonVisibility.CHART),
            (0.6, 36, False, SeasonVisibility.TENTATIVE),
            (0.1, 36, True, SeasonVisibility.CHART),
        ],
    )
    def test_shown_when_material_and_reliable_or_asked_for(
        self, strength: float, months: int, requested: bool, expected: SeasonVisibility
    ) -> None:
        pair = _pair(UK, findings=_seasonal(strength), views=_months(months))
        assert season_visibility(pair, requested=requested) is expected

    def test_without_a_profile_nothing_is_shown(self) -> None:
        assert season_visibility(_pair(UK), requested=True) is SeasonVisibility.HIDDEN

    def test_three_years_give_only_signs_of_a_season(self) -> None:
        pair = _pair(UK, findings=_seasonal(0.6), views=_months(36))
        (found,) = select_insights(_result(pair))
        assert found.kind == "season_tentative"

    def test_a_requested_season_survives_the_cut_with_its_caveat(self) -> None:
        findings = PairFindings(
            level_shift=LevelShift(date(2025, 3, 1), 10.0, 16.0, 0.6, 12),
            recent=RecentChange(date(2026, 6, 1), date(2026, 8, 1), 3, 150.0, 100.0, 0.5),
            seasonality=_season(9, 7),
            seasonality_strength=0.05,
        )
        pair = _pair(UK, findings=findings, views=_months(36))
        settings = InsightSettings(max_per_pair=1)
        found = select_insights(_result(pair), settings, season_requested=True)
        assert [i.kind for i in found] == ["season_tentative", "level_shift"]

    def test_signs_in_several_editions_become_one_line(self) -> None:
        pairs = [_pair(p, findings=_seasonal(0.6), views=_months(36)) for p in (UK, CS)]
        (group,) = select_insights(_result(*pairs))
        assert group.kind == "group.season_tentative"
        assert [m.project for m in group.members] == [UK, CS]


class TestUnmeasured:
    def test_missing_article_and_other_subject_come_first(self) -> None:
        gap = _pair(PL, measured=False)
        broader = _pair(CS, substitute=SubstituteKind.BROADER)
        recent = RecentChange(date(2026, 6, 1), date(2026, 8, 1), 3, 150.0, 100.0, 0.5)
        uk = _pair(UK, findings=PairFindings(recent=recent))
        found = select_insights(_result(uk, gap, broader))
        assert [(i.kind, i.project) for i in found[:2]] == [("no_article", PL), ("substitute", CS)]
        assert found[1].params == {"title": "Main", "substitute": "broader"}

    def test_redirect_substitute_still_measures_the_topic(self) -> None:
        redirect = _pair(PL, substitute=SubstituteKind.REDIRECT)
        assert all(i.kind != "substitute" for i in select_insights(_result(redirect)))
