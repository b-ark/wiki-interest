"""Use-case: fetch every pageview series an analysis needs, in parallel, and assemble bundles.

For each resolved bundle the loader fetches monthly views of every article and its redirects,
the edition's monthly total (for normalisation), daily views of the main article (for spike
detection) and, when the analysis filters on human traffic, the main article's automated
traffic (for bot suspicion). Requests are independent, so they run on a thread pool; the
adapter is responsible for caching and rate limiting.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date

from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.contracts.request import Period
from wiki_interest.domain.models import (
    Access,
    Agent,
    ArticleRef,
    Granularity,
    Series,
    TopicBundle,
    WikiProject,
    Window,
)
from wiki_interest.domain.series import combine
from wiki_interest.ports.pageviews import PageviewsSource

__all__ = ["LoadSettings", "LoadedSeries", "SeriesLoader"]


@dataclass(frozen=True, slots=True)
class LoadSettings:
    """What to fetch and how.

    Attributes:
        access: Access method filter passed to the Pageviews API.
        agent: Traffic class filter. Automated traffic is fetched for comparison only when
            this is ``USER``; otherwise the share is meaningless.
        fetch_daily: Whether to fetch daily views of the main article for spike detection.
        max_workers: Size of the thread pool; keep it well below the API's rate limit.
    """

    access: Access = Access.ALL
    agent: Agent = Agent.USER
    fetch_daily: bool = True
    max_workers: int = 8


_DEFAULT_SETTINGS = LoadSettings()


@dataclass(frozen=True, slots=True)
class LoadedSeries:
    """All series fetched for one (topic, edition) pair, aligned to the analysis window.

    ``bundle_views`` and ``main_views`` are ``None`` for a bundle with no articles; the other
    fields are ``None`` when they were not requested.
    """

    topic_id: str
    project: WikiProject
    bundle_views: Series | None
    main_views: Series | None
    project_total: Series
    main_daily: Series | None
    main_automated: Series | None
    main_user_for_automated: Series | None = None
    """Canonical main-title user traffic, excluding redirects, matching ``main_automated``."""


@dataclass(frozen=True, slots=True)
class _FetchPlan:
    """Unique fetch tasks keyed so that duplicates across bundles are fetched once."""

    tasks: dict[tuple[str, ...], Callable[[], Series]]

    def add(self, key: tuple[str, ...], task: Callable[[], Series]) -> None:
        self.tasks.setdefault(key, task)


class SeriesLoader:
    """Fetches and assembles the series for resolved topics."""

    def __init__(
        self, pageviews: PageviewsSource, *, settings: LoadSettings = _DEFAULT_SETTINGS
    ) -> None:
        self._pageviews = pageviews
        self._settings = settings

    def load(self, topics: Sequence[ResolvedTopic], period: Period) -> tuple[LoadedSeries, ...]:
        """Fetch everything for ``topics`` over ``period``.

        Returns:
            One :class:`LoadedSeries` per (topic, edition), in request order.

        Raises:
            UpstreamError: If any request fails after the adapter's retries. A partial result
                would silently bias comparisons, so the whole load fails instead.
        """
        monthly = Window(Granularity.MONTHLY, period.start, period.end)
        daily = Window(Granularity.DAILY, period.start, _last_day_of_month(period.end))
        plan = _FetchPlan(tasks={})
        for topic in topics:
            for bundle in topic.bundles:
                self._plan_bundle(plan, bundle, monthly, daily)
        results = self._execute(plan)
        return tuple(
            self._assemble(bundle, topic.topic_id, results)
            for topic in topics
            for bundle in topic.bundles
        )

    # -- planning -------------------------------------------------------------------------

    def _plan_bundle(
        self, plan: _FetchPlan, bundle: TopicBundle, monthly: Window, daily: Window
    ) -> None:
        settings = self._settings
        project = bundle.project
        plan.add(
            ("aggregate", project.domain),
            lambda: self._pageviews.aggregate(
                project, monthly, access=settings.access, agent=settings.agent
            ),
        )
        for article in bundle.articles:
            for title in (article.title, *article.redirects):
                plan.add(
                    ("monthly", project.domain, title),
                    self._article_task(project, title, monthly, settings.agent),
                )
        main = bundle.main
        if main is None:
            return
        if settings.fetch_daily:
            plan.add(
                ("daily", project.domain, main.title),
                self._article_task(project, main.title, daily, settings.agent),
            )
        if settings.agent is Agent.USER:
            plan.add(
                ("automated", project.domain, main.title),
                self._article_task(project, main.title, monthly, Agent.AUTOMATED),
            )

    def _article_task(
        self, project: WikiProject, title: str, window: Window, agent: Agent
    ) -> Callable[[], Series]:
        access = self._settings.access
        return lambda: self._pageviews.per_article(
            project, title, window, access=access, agent=agent
        )

    # -- execution ------------------------------------------------------------------------

    def _execute(self, plan: _FetchPlan) -> dict[tuple[str, ...], Series]:
        keys = list(plan.tasks)
        with ThreadPoolExecutor(max_workers=self._settings.max_workers) as pool:
            series = list(pool.map(lambda key: plan.tasks[key](), keys))
        return dict(zip(keys, series, strict=True))

    # -- assembly -------------------------------------------------------------------------

    def _assemble(
        self, bundle: TopicBundle, topic_id: str, results: dict[tuple[str, ...], Series]
    ) -> LoadedSeries:
        project = bundle.project
        total = results[("aggregate", project.domain)]
        if not bundle.articles:
            return LoadedSeries(topic_id, project, None, None, total, None, None)

        def article_views(article: ArticleRef) -> Series:
            parts = [
                (results[("monthly", project.domain, title)], 1.0)
                for title in (article.title, *article.redirects)
            ]
            return combine(parts)

        bundle_views = combine([(article_views(a), a.weight) for a in bundle.articles])
        main = bundle.main
        main_views = article_views(main) if main is not None else None
        main_daily = results.get(("daily", project.domain, main.title)) if main else None
        main_automated = results.get(("automated", project.domain, main.title)) if main else None
        main_user = (
            results[("monthly", project.domain, main.title)]
            if main is not None and main_automated is not None
            else None
        )
        return LoadedSeries(
            topic_id,
            project,
            bundle_views,
            main_views,
            total,
            main_daily,
            main_automated,
            main_user,
        )


def _last_day_of_month(first_of_month: date) -> date:
    """Return the last calendar day of the month that starts on ``first_of_month``."""
    days = calendar.monthrange(first_of_month.year, first_of_month.month)[1]
    return first_of_month.replace(day=days)
