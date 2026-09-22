"""Pageviews adapter over the Wikimedia REST API (``/metrics/pageviews``).

Implements :class:`~wiki_interest.ports.pageviews.PageviewsSource` with the gap semantics the
port promises: every returned series is aligned to ``window.buckets()`` and buckets the API
did not return are ``None``. Two API behaviours drive the design (details and verification
dates in ``references/api-notes.md``):

* A 404 means "no data for this article/agent/period", not "wrong request". It happens for
  articles created after the window, for ``agent=automated`` before that traffic class existed,
  and for dates before 2015-07-01. The adapter returns an all-``None`` series instead of raising.
* Titles go into the path segment and must be percent-encoded with *no* safe characters
  because ``/`` and ``?`` are legal in titles (``AC/DC``, ``What?``).
"""

from __future__ import annotations

import calendar
from datetime import date
from urllib.parse import quote

from wiki_interest.adapters.http import HttpJsonClient, HttpNotFoundError, as_array, as_object
from wiki_interest.contracts.request import EARLIEST_MONTH
from wiki_interest.domain.models import (
    Access,
    Agent,
    Granularity,
    Point,
    Series,
    SeriesUnit,
    WikiProject,
    Window,
)
from wiki_interest.errors import DataUnavailableError
from wiki_interest.ports.clock import Clock

__all__ = ["WikimediaRestPageviews", "encode_title"]

_TIMESTAMP_DATE_LENGTH = 8
"""``YYYYMMDD`` prefix of the API's ``YYYYMMDDHH`` timestamps; the hour is always ``00``."""
_AGGREGATE_HOUR_SUFFIX = "00"


def encode_title(title: str) -> str:
    """Encode a page title for the per-article path segment.

    Spaces become underscores (the canonical MediaWiki form the API expects) and everything
    that is not unreserved is percent-encoded, including ``/`` and ``?`` which would otherwise
    change the URL structure.
    """
    return quote(title.replace(" ", "_"), safe="")


class WikimediaRestPageviews:
    """Pageview series from the Wikimedia REST API with cache TTLs that depend on the window.

    Args:
        http: The shared client; base URL and TTLs are read from ``http.settings``.
        clock: Decides whether a window touches the current month (still being written
            upstream, short TTL) or only closed months (immutable, cached forever).
    """

    def __init__(self, http: HttpJsonClient, clock: Clock) -> None:
        self._http = http
        self._clock = clock
        self._settings = http.settings

    def per_article(
        self,
        project: WikiProject,
        title: str,
        window: Window,
        *,
        access: Access,
        agent: Agent,
    ) -> Series:
        """Views of one article aligned to ``window``; see the port for the contract."""
        _check_window_supported(window)
        url = (
            f"{self._settings.pageviews_base_url}/metrics/pageviews/per-article/"
            f"{project.domain}/{access.value}/{agent.value}/{encode_title(title)}/"
            f"{window.granularity.value}/{_ymd(window.start)}/{_ymd(_window_last_day(window))}"
        )
        return self._fetch_series(url, window)

    def aggregate(
        self,
        project: WikiProject,
        window: Window,
        *,
        access: Access,
        agent: Agent,
    ) -> Series:
        """Total views of a project aligned to ``window``; see the port for the contract."""
        _check_window_supported(window)
        start = _ymd(window.start) + _AGGREGATE_HOUR_SUFFIX
        end = _ymd(_window_last_day(window)) + _AGGREGATE_HOUR_SUFFIX
        url = (
            f"{self._settings.pageviews_base_url}/metrics/pageviews/aggregate/"
            f"{project.domain}/{access.value}/{agent.value}/{window.granularity.value}/"
            f"{start}/{end}"
        )
        return self._fetch_series(url, window)

    def _fetch_series(self, url: str, window: Window) -> Series:
        try:
            payload = self._http.get_json(url, ttl_seconds=self._ttl_for(window))
        except HttpNotFoundError:
            # No data at all for this combination: an honest empty series, not an error.
            return _align({}, window)
        items = as_array(as_object(payload, url).get("items"), url)
        views: dict[date, float] = {}
        for raw_item in items:
            item = as_object(raw_item, url)
            bucket = _bucket_from_timestamp(str(item["timestamp"]), window.granularity)
            views[bucket] = float(item["views"])
        return _align(views, window)

    def _ttl_for(self, window: Window) -> int | None:
        """Short TTL when the window reaches the current month, otherwise the closed-period TTL."""
        today = self._clock.today()
        last = window.end
        if (last.year, last.month) >= (today.year, today.month):
            return self._settings.open_period_ttl_s
        return self._settings.closed_period_ttl_s


def _check_window_supported(window: Window) -> None:
    if window.start < EARLIEST_MONTH:
        msg = (
            f"The Pageviews API has no data before {EARLIEST_MONTH:%Y-%m-%d}; "
            f"the window starts {window.start:%Y-%m-%d}"
        )
        raise DataUnavailableError(
            msg, hint=f"Choose a period starting {EARLIEST_MONTH:%Y-%m} or later."
        )


def _window_last_day(window: Window) -> date:
    """Last calendar day covered by the window.

    For monthly windows the API expects the range to cover whole months, so the end date is
    the last day of the end month rather than its first day as stored in :class:`Window`.
    """
    if window.granularity is Granularity.DAILY:
        return window.end
    last_day = calendar.monthrange(window.end.year, window.end.month)[1]
    return window.end.replace(day=last_day)


def _ymd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _bucket_from_timestamp(timestamp: str, granularity: Granularity) -> date:
    """Map the API's ``YYYYMMDDHH`` timestamp to the bucket start date."""
    day = date.fromisoformat(timestamp[:_TIMESTAMP_DATE_LENGTH])
    return day.replace(day=1) if granularity is Granularity.MONTHLY else day


def _align(views: dict[date, float], window: Window) -> Series:
    """Build a series over every bucket of the window, ``None`` where the API had nothing."""
    points = tuple(Point(bucket, views.get(bucket)) for bucket in window.buckets())
    return Series(granularity=window.granularity, unit=SeriesUnit.VIEWS, points=points)
