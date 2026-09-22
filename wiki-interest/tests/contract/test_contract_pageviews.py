"""Pageviews adapter against recorded Wikimedia REST responses."""

from datetime import date

from wiki_interest.domain.models import Granularity, Series, SeriesUnit

from .conftest import Replay


def test_per_article_monthly_covers_every_month_of_2024(replay: Replay) -> None:
    series = replay("pageviews-per-article-monthly-uk-astronomy")
    assert isinstance(series, Series)
    assert series.granularity is Granularity.MONTHLY
    assert series.unit is SeriesUnit.VIEWS
    assert len(series) == 12
    assert series.completeness == 1.0
    assert series.start == date(2024, 1, 1)
    assert series.end == date(2024, 12, 1)
    assert series.values[0] == 3700.0, "January 2024 views as recorded"
    assert all(v is not None and v > 0 for v in series.values)


def test_per_article_daily_covers_every_day_of_march_2024(replay: Replay) -> None:
    series = replay("pageviews-per-article-daily-uk-astronomy")
    assert isinstance(series, Series)
    assert series.granularity is Granularity.DAILY
    assert len(series) == 31
    assert series.completeness == 1.0
    assert series.periods[0] == date(2024, 3, 1)
    assert series.values[0] == 69.0
    assert series.values[1] == 65.0


def test_aggregate_monthly_is_project_scale(replay: Replay) -> None:
    series = replay("pageviews-aggregate-monthly-uk")
    assert isinstance(series, Series)
    assert len(series) == 12
    assert series.completeness == 1.0
    assert series.values[0] == 115_282_138.0, "uk.wikipedia user views in January 2024"
    assert all(v is not None and v > 10_000_000 for v in series.values)


def test_404_becomes_an_all_none_series(replay: Replay) -> None:
    series = replay("pageviews-per-article-404-pl-automated")
    assert isinstance(series, Series)
    assert len(series) == 3
    assert series.values == (None, None, None)
    assert series.completeness == 0.0
