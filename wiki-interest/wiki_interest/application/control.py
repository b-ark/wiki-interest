"""Use-case: the control basket of an edition, and the move log of an article.

A topic's attention share can move because the topic did, or because the edition changed how
it counts or reaches readers (a new app, bot filtering, a redesign). The control basket tells
them apart: about a hundred popular articles of the same edition, drawn at random with a
fixed seed from a month's top list. What they all do in a month, the edition did.

Building a basket: the top list of the reference month (the last complete month when it is
built), without the main page, special pages and other namespaces; ``control_candidates``
drawn from its first ``control_top`` with a fixed seed; each candidate's monthly views over
the two years before; left out: articles younger than that and those whose reference month
was a burst (over ``control_spike_multiple`` times their median of the twelve months before).
The first ``control_sample`` left are kept. The basket is stored with the day it was built
and reused for ``control_ttl_days``.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from statistics import median

from wiki_interest.domain.models import Access, Agent, Granularity, Series, WikiProject, Window
from wiki_interest.domain.trust import TrustSettings
from wiki_interest.ports.clock import Clock
from wiki_interest.ports.control import BasketStore, ControlBasket
from wiki_interest.ports.mediawiki import MediaWikiGateway
from wiki_interest.ports.pageviews import PageviewsSource

__all__ = ["ControlBaskets", "RenameLog"]

_YEAR = 12
_HISTORY_MONTHS = 25
"""The reference month and the two years before it: a candidate needs them to be judged."""
_MIN_KNOWN = 18
"""Months of those a candidate needs with data: younger articles are left out."""
_MAIN_PAGE_LEAD = 3.0
"""The first of the top list is the main page when it has this many times the second's views."""
_MAX_REDIRECTS = 10
"""Redirects of an article whose move log is read (one request each)."""


def _shift(month: date, months: int) -> date:
    total = month.year * _YEAR + month.month - 1 + months
    return date(total // _YEAR, total % _YEAR + 1, 1)


class ControlBaskets:
    """Builds, keeps and reads the control basket of each edition.

    Args:
        pageviews: The pageview source (top lists, per-article series).
        store: Where the baskets are kept between runs.
        clock: Today: the reference month and the basket's age.
        settings: The basket's size, seed and age limit.
        access: Access method filter, as the analysis uses.
        agent: Traffic class filter, as the analysis uses.
        max_workers: Parallel requests when a basket's series are fetched.
    """

    def __init__(  # noqa: PLR0913 -- the collaborators and the filters of the analysis
        self,
        pageviews: PageviewsSource,
        store: BasketStore,
        clock: Clock,
        settings: TrustSettings | None = None,
        *,
        access: Access = Access.ALL,
        agent: Agent = Agent.USER,
        max_workers: int = 8,
    ) -> None:
        self._pageviews = pageviews
        self._store = store
        self._clock = clock
        self._settings = settings or TrustSettings()
        self._access = access
        self._agent = agent
        self._workers = max_workers

    def basket(self, project: WikiProject) -> ControlBasket | None:
        """The edition's basket: the stored one while fresh, else a new one; ``None`` if none."""
        stored = self._store.load(project.domain)
        today = self._clock.today()
        if stored is not None and today - stored.built <= timedelta(
            days=self._settings.control_ttl_days
        ):
            return stored
        built = self._build(project, today)
        if built is not None:
            self._store.save(built)
        return built

    def shares(
        self, project: WikiProject, months: Sequence[date], edition: Sequence[float | None]
    ) -> list[tuple[float | None, ...]]:
        """Each control article's monthly share (per million), aligned with ``months``.

        Args:
            project: The edition.
            months: The months to read (first days, oldest first, consecutive).
            edition: The edition's monthly views over the same months.
        """
        basket = self.basket(project)
        if basket is None or not months:
            return []
        window = Window(Granularity.MONTHLY, months[0], months[-1])
        out = []
        for series in self._fetch(project, basket.titles, window):
            out.append(
                tuple(
                    v / e * 1e6 if v is not None and e else None
                    for v, e in zip(series.values, edition, strict=False)
                )
            )
        return out

    def _build(self, project: WikiProject, today: date) -> ControlBasket | None:
        s = self._settings
        reference = _shift(today.replace(day=1), -1)
        top = [
            (title, views)
            for title, views in self._pageviews.top(project, reference, access=self._access)
            if ":" not in title and title.strip() not in ("", "-")
        ][: s.control_top]
        if len(top) > 1 and top[0][1] > _MAIN_PAGE_LEAD * top[1][1]:
            top = top[1:]
        titles = [title for title, _ in top]
        if not titles:
            return None
        rng = random.Random(s.control_seed)
        drawn = rng.sample(titles, min(s.control_candidates, len(titles)))
        window = Window(Granularity.MONTHLY, _shift(reference, 1 - _HISTORY_MONTHS), reference)
        kept = [
            title
            for title, series in zip(drawn, self._fetch(project, drawn, window), strict=True)
            if _usual(series.values, s.control_spike_multiple)
        ][: s.control_sample]
        return ControlBasket(
            project=project.domain,
            reference_month=reference,
            built=today,
            seed=s.control_seed,
            titles=tuple(kept),
        )

    def _fetch(self, project: WikiProject, titles: Sequence[str], window: Window) -> list[Series]:
        def one(title: str) -> Series:
            return self._pageviews.per_article(
                project, title, window, access=self._access, agent=self._agent
            )

        with ThreadPoolExecutor(max_workers=self._workers) as pool:
            return list(pool.map(one, titles))


def _usual(values: Sequence[float | None], multiple: float) -> bool:
    """Old enough, and its last month no burst against the twelve before."""
    known = [v for v in values if v is not None]
    if len(known) < _MIN_KNOWN or values[-1] is None:
        return False
    before = [v for v in values[-_YEAR - 1 : -1] if v is not None]
    return bool(before) and values[-1] <= multiple * median(before)


class RenameLog:
    """The days an article (or a title that now redirects to it) was moved.

    Args:
        mediawiki: The MediaWiki gateway.
    """

    def __init__(self, mediawiki: MediaWikiGateway) -> None:
        self._mediawiki = mediawiki

    def moves(self, project: WikiProject, title: str, redirects: Sequence[str]) -> list[date]:
        """Moves of ``title`` and of up to ten of its redirects, oldest first.

        A move leaves the old title behind as a redirect, so the move log of the redirects
        tells when the article was renamed; one request per title, so long lists are cut.
        """
        days: set[date] = set()
        for name in (title, *redirects[:_MAX_REDIRECTS]):
            days.update(self._mediawiki.moves(project, name))
        return sorted(days)
