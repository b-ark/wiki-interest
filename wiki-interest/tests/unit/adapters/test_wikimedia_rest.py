"""URL building, timestamp mapping, gap alignment and TTL policy of the Pageviews adapter."""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest
import respx

from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.adapters.wikimedia_rest import WikimediaRestPageviews, encode_title
from wiki_interest.config import Settings
from wiki_interest.domain.models import Access, Agent, Granularity, SeriesUnit, WikiProject, Window
from wiki_interest.errors import DataUnavailableError, UpstreamError

BASE = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
UK = WikiProject("uk")
MONTHLY_Q1 = Window(Granularity.MONTHLY, date(2024, 1, 1), date(2024, 3, 1))
DAILY_MARCH = Window(Granularity.DAILY, date(2024, 3, 1), date(2024, 3, 31))


class FixedClock:
    def __init__(self, today: date) -> None:
        self._today = today

    def today(self) -> date:
        return self._today


def _item(timestamp: str, views: int) -> dict[str, Any]:
    return {
        "project": "uk.wikipedia",
        "article": "Астрономія",
        "granularity": "monthly",
        "timestamp": timestamp,
        "access": "all-access",
        "agent": "user",
        "views": views,
    }


@pytest.fixture
def source(http: HttpJsonClient) -> WikimediaRestPageviews:
    return WikimediaRestPageviews(http, FixedClock(date(2026, 9, 22)))


@pytest.mark.parametrize(
    ("title", "encoded"),
    [
        ("AC/DC", "AC%2FDC"),
        ("What?", "What%3F"),
        ("Астрономія", "%D0%90%D1%81%D1%82%D1%80%D0%BE%D0%BD%D0%BE%D0%BC%D1%96%D1%8F"),
        ("Post przerywany", "Post_przerywany"),
        ("C++ (programming language)", "C%2B%2B_%28programming_language%29"),
    ],
)
def test_encode_title_makes_titles_safe_for_path_segments(title: str, encoded: str) -> None:
    assert encode_title(title) == encoded


def test_per_article_monthly_url_covers_whole_end_month(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    route = respx_mock.get(
        f"{BASE}/per-article/uk.wikipedia/all-access/user/AC%2FDC/monthly/20240101/20240331"
    ).mock(return_value=httpx.Response(200, json={"items": []}))
    source.per_article(UK, "AC/DC", MONTHLY_Q1, access=Access.ALL, agent=Agent.USER)
    assert route.called


def test_per_article_daily_url_uses_inclusive_end_date(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    route = respx_mock.get(
        f"{BASE}/per-article/uk.wikipedia/desktop/spider/X/daily/20240301/20240331"
    ).mock(return_value=httpx.Response(200, json={"items": []}))
    source.per_article(UK, "X", DAILY_MARCH, access=Access.DESKTOP, agent=Agent.SPIDER)
    assert route.called


def test_aggregate_url_uses_hourly_suffix(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    route = respx_mock.get(
        f"{BASE}/aggregate/uk.wikipedia/all-access/all-agents/monthly/2024010100/2024033100"
    ).mock(return_value=httpx.Response(200, json={"items": []}))
    source.aggregate(UK, MONTHLY_Q1, access=Access.ALL, agent=Agent.ALL)
    assert route.called


def test_monthly_timestamps_map_to_first_of_month_and_gaps_are_none(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    respx_mock.get(url__regex=r".*/per-article/.*").mock(
        return_value=httpx.Response(
            200, json={"items": [_item("2024010100", 3700), _item("2024030100", 3200)]}
        )
    )
    series = source.per_article(UK, "Астрономія", MONTHLY_Q1, access=Access.ALL, agent=Agent.USER)
    assert series.granularity is Granularity.MONTHLY
    assert series.unit is SeriesUnit.VIEWS
    assert series.periods == (date(2024, 1, 1), date(2024, 2, 1), date(2024, 3, 1))
    assert series.values == (3700.0, None, 3200.0)
    assert series.completeness == pytest.approx(2 / 3)


def test_daily_series_is_aligned_to_every_day_of_the_window(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    respx_mock.get(url__regex=r".*/per-article/.*").mock(
        return_value=httpx.Response(
            200, json={"items": [_item("2024030200", 65), _item("2024033100", 70)]}
        )
    )
    series = source.per_article(UK, "X", DAILY_MARCH, access=Access.ALL, agent=Agent.USER)
    assert len(series) == 31
    assert series.values[0] is None
    assert series.values[1] == 65.0
    assert series.values[-1] == 70.0


def test_items_outside_the_window_are_ignored(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    respx_mock.get(url__regex=r".*/aggregate/.*").mock(
        return_value=httpx.Response(200, json={"items": [_item("2023120100", 1)]})
    )
    series = source.aggregate(UK, MONTHLY_Q1, access=Access.ALL, agent=Agent.USER)
    assert series.values == (None, None, None)


def test_404_means_no_data_not_an_error(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    respx_mock.get(url__regex=r".*/per-article/.*").mock(
        return_value=httpx.Response(404, json={"title": "Not Found"})
    )
    series = source.per_article(
        UK, "Post przerywany", MONTHLY_Q1, access=Access.ALL, agent=Agent.AUTOMATED
    )
    assert series.values == (None, None, None)
    assert series.completeness == 0.0


def test_window_before_api_history_raises_data_unavailable(
    source: WikimediaRestPageviews,
) -> None:
    window = Window(Granularity.MONTHLY, date(2015, 1, 1), date(2015, 12, 1))
    with pytest.raises(DataUnavailableError) as info:
        source.per_article(UK, "X", window, access=Access.ALL, agent=Agent.USER)
    assert info.value.hint is not None
    assert "2015-07" in info.value.hint
    with pytest.raises(DataUnavailableError):
        source.aggregate(UK, window, access=Access.ALL, agent=Agent.USER)


def test_unexpected_payload_shape_is_an_upstream_error(
    respx_mock: respx.MockRouter, source: WikimediaRestPageviews
) -> None:
    respx_mock.get(url__regex=r".*/per-article/.*").mock(
        return_value=httpx.Response(200, json={"items": {"not": "a list"}})
    )
    with pytest.raises(UpstreamError) as info:
        source.per_article(UK, "X", MONTHLY_Q1, access=Access.ALL, agent=Agent.USER)
    assert info.value.retryable is False


class TestTtlPolicy:
    @pytest.fixture
    def ttls(self, respx_mock: respx.MockRouter, settings: Settings) -> list[int | None]:
        recorded: list[int | None] = []

        class SpyCache(InMemoryCache):
            def set(self, key: str, value: bytes, *, ttl_seconds: int | None) -> None:
                recorded.append(ttl_seconds)
                super().set(key, value, ttl_seconds=ttl_seconds)

        respx_mock.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={"items": []}))
        self.http = HttpJsonClient(settings, SpyCache(), httpx.Client())
        return recorded

    def test_closed_window_uses_closed_period_ttl(
        self, ttls: list[int | None], settings: Settings
    ) -> None:
        source = WikimediaRestPageviews(self.http, FixedClock(date(2026, 9, 22)))
        source.per_article(UK, "X", MONTHLY_Q1, access=Access.ALL, agent=Agent.USER)
        assert ttls == [settings.closed_period_ttl_s]

    def test_window_touching_current_month_uses_open_period_ttl(
        self, ttls: list[int | None], settings: Settings
    ) -> None:
        source = WikimediaRestPageviews(self.http, FixedClock(date(2024, 3, 15)))
        source.per_article(UK, "X", MONTHLY_Q1, access=Access.ALL, agent=Agent.USER)
        assert ttls == [settings.open_period_ttl_s]

    def test_daily_window_ending_in_current_month_uses_open_period_ttl(
        self, ttls: list[int | None], settings: Settings
    ) -> None:
        source = WikimediaRestPageviews(self.http, FixedClock(date(2024, 3, 2)))
        source.aggregate(UK, DAILY_MARCH, access=Access.ALL, agent=Agent.USER)
        assert ttls == [settings.open_period_ttl_s]
