"""One shared HTTP client for every Wikimedia API: caching, retries and provenance counters.

All three upstream adapters (Pageviews, Wikidata, MediaWiki) issue idempotent JSON ``GET``
requests, so the transport concerns live here once:

* **Cache first.** The key is the full URL with sorted query parameters; the value is the raw
  response body, so the cache never needs to know about formats. A 404 is cached too (as a
  marker that can never be valid JSON) because for the Pageviews API a 404 *is* the answer
  ("no data") and repeating it on every run would be wasteful.
* **Retries only for transient failures.** Connection errors, timeouts, 429 and 5xx are
  retried with exponential backoff and jitter, honouring ``Retry-After`` when the server sends
  one. Any other 4xx is a bug in our request and is raised at once as a non-retryable
  :class:`~wiki_interest.errors.UpstreamError`.
* **Thread safety.** ``httpx.Client`` is safe to share across threads; the statistics counter
  is guarded by a lock; a fresh tenacity controller is built per call.

Callers decide what a 404 means: the client raises :class:`HttpNotFoundError` (an internal
signal, never shown to users) and the adapter maps it to "no data" or "missing page".
"""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from http import HTTPStatus
from typing import Any, Self

import httpx
from tenacity import (
    RetryCallState,
    RetryError,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from wiki_interest.config import Settings
from wiki_interest.errors import UpstreamError
from wiki_interest.ports.cache import Cache

__all__ = [
    "HttpJsonClient",
    "HttpNotFoundError",
    "HttpStats",
    "HttpStatsSnapshot",
    "as_array",
    "as_object",
    "build_cache_key",
]

type QueryParams = Mapping[str, str | int]

_NOT_FOUND_MARKER = b"\x00not-found"
"""Cached stand-in for a 404 body; a NUL byte can never start a JSON document."""

_BACKOFF_INITIAL_S = 0.5
_BACKOFF_MAX_S = 30.0
_BACKOFF_JITTER_S = 1.0
_RETRY_AFTER_CAP_S = 60.0
"""Longest we honour a ``Retry-After`` header; beyond this the run should fail fast instead."""
_SHAPE_HINT = "The API response shape changed; update the adapter or report this with the URL."


class HttpNotFoundError(Exception):
    """The upstream answered 404 for ``url``.

    Deliberately not a :class:`~wiki_interest.errors.WikiInterestError`: it is a control-flow
    signal between the client and its adapters, which translate it into domain semantics
    (an all-``None`` series, a missing page). If it ever escapes, that is a programming error.
    """

    def __init__(self, url: str) -> None:
        super().__init__(f"404 Not Found: {url}")
        self.url = url


class _RetryableStatusError(Exception):
    """Internal: a 429 or 5xx response that tenacity should retry."""

    def __init__(self, status: int, url: str, retry_after_s: float | None) -> None:
        super().__init__(f"HTTP {status} from {url}")
        self.status = status
        self.url = url
        self.retry_after_s = retry_after_s


@dataclass(frozen=True, slots=True)
class HttpStatsSnapshot:
    """Point-in-time copy of :class:`HttpStats`, suitable for ``provenance``."""

    requests_made: int
    cache_hits: int
    retries: int


class HttpStats:
    """Thread-safe counters of what the client did, for the report's provenance section.

    ``requests_made`` counts attempts that reached the network (so retries are included);
    ``cache_hits`` counts calls answered from the cache; ``retries`` counts the sleeps before a
    repeated attempt.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests_made = 0
        self._cache_hits = 0
        self._retries = 0

    def record_request(self) -> None:
        """Count one network attempt."""
        with self._lock:
            self._requests_made += 1

    def record_cache_hit(self) -> None:
        """Count one call answered from the cache."""
        with self._lock:
            self._cache_hits += 1

    def record_retry(self) -> None:
        """Count one retry (a sleep followed by a new attempt)."""
        with self._lock:
            self._retries += 1

    def snapshot(self) -> HttpStatsSnapshot:
        """Return a consistent copy of all counters."""
        with self._lock:
            return HttpStatsSnapshot(self._requests_made, self._cache_hits, self._retries)


class HttpJsonClient:
    """Cached, retrying JSON ``GET`` client shared by all upstream adapters.

    Args:
        settings: Supplies the User-Agent, timeout and retry budget.
        cache: Where response bodies are stored; keyed by the full URL.
        client: An ``httpx.Client`` to reuse (tests inject a mocked one). When omitted, one is
            created and owned by this object; call :meth:`close` or use it as a context manager.
        sleep: Function used to wait between retries; tests inject a recorder so no real time
            passes.
    """

    def __init__(
        self,
        settings: Settings,
        cache: Cache,
        client: httpx.Client | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._settings = settings
        self._cache = cache
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=settings.http_timeout_s, follow_redirects=True
        )
        self._sleep = sleep
        self._stats = HttpStats()
        self._backoff = wait_exponential_jitter(
            initial=_BACKOFF_INITIAL_S, max=_BACKOFF_MAX_S, jitter=_BACKOFF_JITTER_S
        )

    @property
    def settings(self) -> Settings:
        """The settings this client was built with; adapters read base URLs and TTLs from it."""
        return self._settings

    @property
    def stats(self) -> HttpStats:
        """Live counters; take a :meth:`HttpStats.snapshot` for provenance."""
        return self._stats

    def close(self) -> None:
        """Release the underlying connection pool if this object created it."""
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def get_json(
        self, url: str, params: QueryParams | None = None, *, ttl_seconds: int | None
    ) -> Any:
        """Fetch ``url`` (plus ``params``) as parsed JSON, via the cache.

        Args:
            url: Absolute URL without a query string.
            params: Query parameters; sorted by name to make the cache key canonical.
            ttl_seconds: How long to keep the body; ``None`` keeps it forever.

        Returns:
            The decoded JSON document (any JSON type).

        Raises:
            HttpNotFoundError: The server answered 404 (possibly from the cache).
            UpstreamError: Non-retryable 4xx, retries exhausted, or a body that is not JSON.
        """
        full_url = build_cache_key(url, params)
        body = self._cache.get(full_url)
        if body is None:
            body = self._fetch_with_retries(full_url)
            self._cache.set(full_url, body, ttl_seconds=ttl_seconds)
        else:
            self._stats.record_cache_hit()
        if body == _NOT_FOUND_MARKER:
            raise HttpNotFoundError(full_url)
        return _decode_json(body, full_url)

    def _fetch_with_retries(self, full_url: str) -> bytes:
        retrying = Retrying(
            stop=stop_after_attempt(self._settings.max_retries + 1),
            wait=self._wait,
            retry=retry_if_exception_type((httpx.TransportError, _RetryableStatusError)),
            sleep=self._sleep,
            before_sleep=lambda _state: self._stats.record_retry(),
        )
        try:
            return retrying(self._fetch_once, full_url)
        except RetryError as exc:
            cause = exc.last_attempt.exception()
            attempts = self._settings.max_retries + 1
            msg = f"Gave up on {full_url} after {attempts} attempts: {cause}"
            raise UpstreamError(
                msg,
                retryable=True,
                hint="The Wikimedia service is slow or rate limiting; retry in a few minutes.",
            ) from cause

    def _fetch_once(self, full_url: str) -> bytes:
        """One attempt: classify the status into body, 404 marker, retryable or fatal."""
        self._stats.record_request()
        response = self._client.get(full_url, headers=self._headers())
        status = response.status_code
        if response.is_success:
            return response.content
        if status == HTTPStatus.NOT_FOUND:
            return _NOT_FOUND_MARKER
        if status == HTTPStatus.TOO_MANY_REQUESTS or status >= HTTPStatus.INTERNAL_SERVER_ERROR:
            raise _RetryableStatusError(status, full_url, _retry_after_seconds(response))
        msg = f"HTTP {status} from {full_url}: {response.text[:200]}"
        raise UpstreamError(
            msg,
            retryable=False,
            hint="The request was rejected upstream; check the title, project and period.",
        )

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self._settings.user_agent, "Accept": "application/json"}

    def _wait(self, retry_state: RetryCallState) -> float:
        """Prefer the server's ``Retry-After``; otherwise exponential backoff with jitter."""
        outcome = retry_state.outcome
        exc = outcome.exception() if outcome is not None else None
        if isinstance(exc, _RetryableStatusError) and exc.retry_after_s is not None:
            return min(exc.retry_after_s, _RETRY_AFTER_CAP_S)
        return self._backoff(retry_state)


def build_cache_key(url: str, params: QueryParams | None) -> str:
    """Return the canonical full URL used both for the request and as the cache key."""
    if not params:
        return url
    ordered = [(name, str(value)) for name, value in sorted(params.items())]
    return str(httpx.URL(url, params=ordered))


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse ``Retry-After`` given either as seconds or as an HTTP date; ``None`` if absent."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    if raw.strip().isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    return max(0.0, when.timestamp() - time.time())


def _decode_json(body: bytes, full_url: str) -> Any:
    try:
        return json.loads(body)
    except ValueError as exc:
        msg = f"Response from {full_url} is not valid JSON: {exc}"
        raise UpstreamError(
            msg,
            retryable=False,
            hint="The service returned an unexpected document; report this with the URL.",
        ) from exc


def as_object(value: Any, context: str) -> dict[str, Any]:
    """Narrow a decoded JSON value to an object, or fail as a non-retryable upstream error.

    Adapters call this at every level they descend into a response, so a changed API shape
    produces one clear error naming the URL instead of a ``KeyError`` deep in the pipeline.
    """
    if isinstance(value, dict):
        return value
    msg = f"Expected a JSON object in the response from {context}, got {type(value).__name__}"
    raise UpstreamError(msg, retryable=False, hint=_SHAPE_HINT)


def as_array(value: Any, context: str) -> list[Any]:
    """Narrow a decoded JSON value to an array; see :func:`as_object`."""
    if isinstance(value, list):
        return value
    msg = f"Expected a JSON array in the response from {context}, got {type(value).__name__}"
    raise UpstreamError(msg, retryable=False, hint=_SHAPE_HINT)
