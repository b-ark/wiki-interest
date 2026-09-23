"""Invariants of the domain value objects."""

from datetime import date

import pytest

from wiki_interest.domain.models import (
    ArticleRef,
    ArticleRole,
    BundleStatus,
    Granularity,
    Point,
    RankingWeights,
    ResolutionSource,
    Series,
    SeriesUnit,
    TopicBundle,
    WikiProject,
    Window,
)


class TestWikiProject:
    @pytest.mark.parametrize(
        "spelling",
        ["uk", "UK", " uk ", "uk.wikipedia", "uk.wikipedia.org", "ukwiki", "UK.Wikipedia"],
    )
    def test_parse_accepts_every_known_spelling(self, spelling: str) -> None:
        assert WikiProject.parse(spelling) == WikiProject("uk")

    def test_derived_names(self) -> None:
        project = WikiProject("be-tarask")
        assert project.domain == "be-tarask.wikipedia"
        assert project.host == "be-tarask.wikipedia.org"
        assert project.site_id == "be_taraskwiki"

    @pytest.mark.parametrize("bad", ["", "  ", "1uk", "uk wiki", "uk.wikipedia.com!"])
    def test_rejects_invalid_codes(self, bad: str) -> None:
        with pytest.raises(ValueError, match="Invalid Wikipedia language code"):
            WikiProject.parse(bad)

    def test_is_orderable_and_hashable(self) -> None:
        assert sorted({WikiProject("uk"), WikiProject("cs")}) == [
            WikiProject("cs"),
            WikiProject("uk"),
        ]


def _article(title: str = "Astronomy", role: ArticleRole = ArticleRole.MAIN) -> ArticleRef:
    return ArticleRef(
        project=WikiProject("uk"), title=title, role=role, source=ResolutionSource.SITELINK
    )


class TestArticleRef:
    def test_rejects_empty_title(self) -> None:
        with pytest.raises(ValueError, match="title"):
            _article(title="  ")


class TestTopicBundle:
    def test_main_is_the_single_main_article(self) -> None:
        bundle = TopicBundle(
            topic_id="astronomy",
            project=WikiProject("uk"),
            status=BundleStatus.FOUND,
            articles=(_article(), _article("Telescope", ArticleRole.RELATED)),
        )
        assert bundle.main is not None
        assert bundle.main.title == "Astronomy"

    def test_rejects_two_main_articles(self) -> None:
        with pytest.raises(ValueError, match="at most one main"):
            TopicBundle(
                topic_id="t",
                project=WikiProject("uk"),
                status=BundleStatus.FOUND,
                articles=(_article("A"), _article("B")),
            )

    def test_not_found_bundle_has_no_articles_and_no_main(self) -> None:
        bundle = TopicBundle(topic_id="t", project=WikiProject("pl"), status=BundleStatus.NOT_FOUND)
        assert bundle.main is None
        with pytest.raises(ValueError, match="NOT_FOUND"):
            TopicBundle(
                topic_id="t",
                project=WikiProject("pl"),
                status=BundleStatus.NOT_FOUND,
                articles=(_article(),),
            )

    def test_found_bundle_needs_articles(self) -> None:
        with pytest.raises(ValueError, match="at least one article"):
            TopicBundle(topic_id="t", project=WikiProject("pl"), status=BundleStatus.FOUND)


def _monthly(*values: float | None, start: date = date(2024, 1, 1)) -> Series:
    points = tuple(
        Point(date(start.year + (start.month - 1 + i) // 12, (start.month - 1 + i) % 12 + 1, 1), v)
        for i, v in enumerate(values)
    )
    return Series(Granularity.MONTHLY, SeriesUnit.VIEWS, points)


class TestSeries:
    def test_properties_reflect_gaps(self) -> None:
        series = _monthly(10, None, 30, 40)
        expected_values: tuple[float | None, ...] = (10, None, 30, 40)
        expected_observed: tuple[float, ...] = (10, 30, 40)
        assert len(series) == 4
        assert series.values == expected_values
        assert series.observed == expected_observed
        assert series.completeness == pytest.approx(0.75)
        assert series.start == date(2024, 1, 1)
        assert series.end == date(2024, 4, 1)

    def test_empty_series_is_safe(self) -> None:
        series = Series(Granularity.MONTHLY, SeriesUnit.VIEWS, ())
        assert series.completeness == 0.0
        assert series.start is None
        assert series.end is None

    def test_rejects_unsorted_periods(self) -> None:
        with pytest.raises(ValueError, match="sorted"):
            Series(
                Granularity.DAILY,
                SeriesUnit.VIEWS,
                (Point(date(2024, 1, 2), 1.0), Point(date(2024, 1, 1), 1.0)),
            )

    def test_rejects_duplicate_periods(self) -> None:
        with pytest.raises(ValueError, match="unique"):
            Series(
                Granularity.DAILY,
                SeriesUnit.VIEWS,
                (Point(date(2024, 1, 1), 1.0), Point(date(2024, 1, 1), 2.0)),
            )

    def test_monthly_periods_must_be_first_of_month(self) -> None:
        with pytest.raises(ValueError, match="first day"):
            Series(Granularity.MONTHLY, SeriesUnit.VIEWS, (Point(date(2024, 1, 15), 1.0),))


class TestWindow:
    def test_monthly_buckets_span_year_boundary(self) -> None:
        window = Window(Granularity.MONTHLY, date(2025, 11, 1), date(2026, 2, 1))
        assert window.buckets() == (
            date(2025, 11, 1),
            date(2025, 12, 1),
            date(2026, 1, 1),
            date(2026, 2, 1),
        )
        assert window.count == 4

    def test_daily_buckets_are_consecutive_days(self) -> None:
        window = Window(Granularity.DAILY, date(2024, 2, 28), date(2024, 3, 1))
        assert window.buckets() == (date(2024, 2, 28), date(2024, 2, 29), date(2024, 3, 1))

    def test_single_bucket_window(self) -> None:
        assert Window(Granularity.MONTHLY, date(2024, 5, 1), date(2024, 5, 1)).count == 1

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(ValueError, match="before start"):
            Window(Granularity.DAILY, date(2024, 1, 2), date(2024, 1, 1))

    def test_monthly_bounds_must_be_first_of_month(self) -> None:
        with pytest.raises(ValueError, match="first day"):
            Window(Granularity.MONTHLY, date(2024, 1, 15), date(2024, 3, 1))


class TestRankingWeights:
    def test_normalised_sums_to_one(self) -> None:
        weights = RankingWeights(growth=2, volume=1, stability=1, reliability=0).normalised()
        assert weights.growth + weights.volume + weights.stability + weights.reliability == (
            pytest.approx(1.0)
        )
        assert weights.growth == pytest.approx(0.5)

    def test_rejects_all_zero_or_negative(self) -> None:
        with pytest.raises(ValueError, match="weights"):
            RankingWeights(growth=0, volume=0, stability=0, reliability=0)
        with pytest.raises(ValueError, match="weights"):
            RankingWeights(growth=-1)
