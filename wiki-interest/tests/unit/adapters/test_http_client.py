"""Retry, cache and error policy of the shared HTTP client (no real network, no real sleeping)."""

from __future__ import annotations

import time
from email.utils import formatdate

import httpx
import pytest
import respx

from wiki_interest.adapters.http import HttpJsonClient, HttpNotFoundError, build_cache_key
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.config import Settings
from wiki_interest.errors import UpstreamError

URL = "https://api.example.org/v1/thing"


def test_sends_user_agent_and_accept_headers(
    respx_mock: respx.MockRouter, http: HttpJsonClient, settings: Settings
) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, json={"ok": True}))
    assert http.get_json(URL, ttl_seconds=10) == {"ok": True}
    request = route.calls.last.request
    assert request.headers["User-Agent"] == settings.user_agent
    assert request.headers["Accept"] == "application/json"


def test_second_call_is_served_from_cache(
    respx_mock: respx.MockRouter, http: HttpJsonClient
) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, json=[1, 2]))
    assert http.get_json(URL, ttl_seconds=10) == [1, 2]
    assert http.get_json(URL, ttl_seconds=10) == [1, 2]
    assert route.call_count == 1
    stats = http.stats.snapshot()
    assert (stats.requests_made, stats.cache_hits, stats.retries) == (1, 1, 0)


def test_cache_key_sorts_params_and_is_the_request_url(
    respx_mock: respx.MockRouter, http: HttpJsonClient, cache: InMemoryCache
) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(200, json={}))
    http.get_json(URL, {"zeta": 1, "alpha": "x y"}, ttl_seconds=10)
    key = build_cache_key(URL, {"zeta": 1, "alpha": "x y"})
    assert key == f"{URL}?alpha=x+y&zeta=1"
    assert str(route.calls.last.request.url) == key
    assert cache.get(key) == b"{}"


def test_build_cache_key_without_params_is_the_url() -> None:
    assert build_cache_key(URL, None) == URL
    assert build_cache_key(URL, {}) == URL


def test_ttl_is_passed_to_the_cache(respx_mock: respx.MockRouter, settings: Settings) -> None:
    recorded: list[int | None] = []

    class SpyCache(InMemoryCache):
        def set(self, key: str, value: bytes, *, ttl_seconds: int | None) -> None:
            recorded.append(ttl_seconds)
            super().set(key, value, ttl_seconds=ttl_seconds)

    respx_mock.get(URL).mock(return_value=httpx.Response(200, json={}))
    with HttpJsonClient(settings, SpyCache(), httpx.Client()) as client:
        client.get_json(URL, ttl_seconds=None)
        client.get_json(URL + "?x=1", ttl_seconds=42)
    assert recorded == [None, 42]


def test_404_raises_not_found_and_is_cached(
    respx_mock: respx.MockRouter, http: HttpJsonClient
) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(404, json={"title": "Not Found"}))
    with pytest.raises(HttpNotFoundError):
        http.get_json(URL, ttl_seconds=10)
    with pytest.raises(HttpNotFoundError):
        http.get_json(URL, ttl_seconds=10)
    assert route.call_count == 1, "a 404 is an answer and must not be re-fetched"
    assert http.stats.snapshot().cache_hits == 1


def test_429_honours_retry_after_seconds(
    respx_mock: respx.MockRouter, http: HttpJsonClient, sleeps: list[float]
) -> None:
    route = respx_mock.get(URL).mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "3"}),
            httpx.Response(200, json={"ok": 1}),
        ]
    )
    assert http.get_json(URL, ttl_seconds=10) == {"ok": 1}
    assert route.call_count == 2
    assert sleeps == [3.0]
    assert http.stats.snapshot().retries == 1


def test_retry_after_http_date_is_converted_and_capped(
    respx_mock: respx.MockRouter, http: HttpJsonClient, sleeps: list[float]
) -> None:
    far_future = formatdate(time.time() + 3600, usegmt=True)
    respx_mock.get(URL).mock(
        side_effect=[
            httpx.Response(503, headers={"Retry-After": far_future}),
            httpx.Response(200, json={}),
        ]
    )
    http.get_json(URL, ttl_seconds=10)
    assert sleeps == [60.0], "Retry-After is capped so a run never hangs for an hour"


def test_unparseable_retry_after_falls_back_to_backoff(
    respx_mock: respx.MockRouter, http: HttpJsonClient, sleeps: list[float]
) -> None:
    respx_mock.get(URL).mock(
        side_effect=[
            httpx.Response(503, headers={"Retry-After": "soon"}),
            httpx.Response(200, json={}),
        ]
    )
    http.get_json(URL, ttl_seconds=10)
    assert len(sleeps) == 1
    assert 0 <= sleeps[0] <= 31.0


def test_5xx_is_retried_with_backoff_until_success(
    respx_mock: respx.MockRouter, http: HttpJsonClient, sleeps: list[float]
) -> None:
    route = respx_mock.get(URL).mock(
        side_effect=[httpx.Response(503), httpx.Response(502), httpx.Response(200, json=1)]
    )
    assert http.get_json(URL, ttl_seconds=10) == 1
    assert route.call_count == 3
    assert len(sleeps) == 2
    assert all(0 <= s <= 31.0 for s in sleeps)
    assert http.stats.snapshot().requests_made == 3


def test_exhausted_retries_raise_retryable_upstream_error(
    respx_mock: respx.MockRouter, http: HttpJsonClient, settings: Settings
) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(UpstreamError) as info:
        http.get_json(URL, ttl_seconds=10)
    assert info.value.retryable is True
    assert info.value.hint
    assert route.call_count == settings.max_retries + 1


def test_connection_errors_and_timeouts_are_retried(
    respx_mock: respx.MockRouter, http: HttpJsonClient
) -> None:
    route = respx_mock.get(URL).mock(
        side_effect=[
            httpx.ConnectError("refused"),
            httpx.ReadTimeout("slow"),
            httpx.Response(200, json="fine"),
        ]
    )
    assert http.get_json(URL, ttl_seconds=10) == "fine"
    assert route.call_count == 3


def test_persistent_connection_error_raises_retryable_upstream_error(
    respx_mock: respx.MockRouter, http: HttpJsonClient
) -> None:
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("refused"))
    with pytest.raises(UpstreamError) as info:
        http.get_json(URL, ttl_seconds=10)
    assert info.value.retryable is True
    assert isinstance(info.value.__cause__, httpx.ConnectError)


def test_other_4xx_is_not_retried_and_not_retryable(
    respx_mock: respx.MockRouter, http: HttpJsonClient, sleeps: list[float]
) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(400, text="bad title"))
    with pytest.raises(UpstreamError) as info:
        http.get_json(URL, ttl_seconds=10)
    assert info.value.retryable is False
    assert "bad title" in str(info.value)
    assert route.call_count == 1
    assert sleeps == []


def test_invalid_json_body_is_a_non_retryable_upstream_error(
    respx_mock: respx.MockRouter, http: HttpJsonClient
) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(UpstreamError) as info:
        http.get_json(URL, ttl_seconds=10)
    assert info.value.retryable is False


def test_zero_retries_means_a_single_attempt(
    respx_mock: respx.MockRouter, cache: InMemoryCache
) -> None:
    route = respx_mock.get(URL).mock(return_value=httpx.Response(500))
    settings = Settings(max_retries=0)
    with (
        HttpJsonClient(settings, cache, httpx.Client(), sleep=lambda _s: None) as client,
        pytest.raises(UpstreamError),
    ):
        client.get_json(URL, ttl_seconds=10)
    assert route.call_count == 1


def test_owned_client_is_closed_on_exit(settings: Settings, cache: InMemoryCache) -> None:
    with HttpJsonClient(settings, cache) as client:
        assert client.settings is settings
    with pytest.raises(RuntimeError):
        client.get_json(URL, ttl_seconds=10)


def test_injected_client_is_left_open(
    respx_mock: respx.MockRouter, settings: Settings, cache: InMemoryCache
) -> None:
    respx_mock.get(URL).mock(return_value=httpx.Response(200, json={}))
    injected = httpx.Client()
    with HttpJsonClient(settings, cache, injected):
        pass
    assert injected.get(URL).status_code == 200
    injected.close()
