"""Series loading: fetch planning, deduplication, the measured article and its context."""

from __future__ import annotations

from datetime import date

import pytest

from fakes import FakePageviews
from wiki_interest.application.loading import LoadSettings, SeriesLoader
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.contracts.request import EARLIEST_MONTH, Period
from wiki_interest.domain.models import (
    Access,
    Agent,
    ArticleRef,
    ArticleRole,
    BundleStatus,
    Granularity,
    ResolutionSource,
    Series,
    TopicBundle,
    WikiProject,
    Window,
)
from wiki_interest.errors import UpstreamError

UK = WikiProject("uk")
PERIOD = Period.model_validate({"start": "2025-01", "end": "2025-03"})
MONTHS = (date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1))


def _bundle() -> TopicBundle:
    main = ArticleRef(
        UK,
        "Астрономія",
        ArticleRole.MAIN,
        ResolutionSource.SITELINK,
        qid="Q333",
        redirects=("Astronomy",),
    )
    related = ArticleRef(UK, "Телескоп", ArticleRole.RELATED, ResolutionSource.LEAD_LINK)
    return TopicBundle("astronomy", UK, BundleStatus.FOUND, (main, related))


def _topic(bundle: TopicBundle) -> ResolvedTopic:
    return ResolvedTopic("astronomy", "astronomy", "Q333", "astronomy", (bundle,))


def _source() -> FakePageviews:
    source = FakePageviews()
    source.set_article(UK, "Астрономія", dict(zip(MONTHS, [100.0, 200.0, 300.0], strict=True)))
    source.set_article(UK, "Astronomy", dict(zip(MONTHS, [10.0, 20.0, 30.0], strict=True)))
    source.set_article(UK, "Телескоп", dict(zip(MONTHS, [50.0, 50.0, 50.0], strict=True)))
    source.set_aggregate(UK, dict(zip(MONTHS, [1e6, 1e6, 2e6], strict=True)))
    source.set_article(
        UK,
        "Астрономія",
        {date(2025, 1, 1): 5.0, date(2025, 3, 31): 7.0},
        granularity=Granularity.DAILY,
    )
    source.set_article(UK, "Астрономія", {date(2025, 2, 1): 40.0}, agent=Agent.AUTOMATED)
    return source


class TestAssembly:
    def test_main_article_is_summed_with_its_redirects_and_related_ones_stay_apart(self) -> None:
        loaded = SeriesLoader(_source()).load([_topic(_bundle())], PERIOD)
        assert len(loaded) == 1
        item = loaded[0]
        assert item.main_views is not None
        assert item.main_views.values == (110.0, 220.0, 330.0)
        assert item.project_total.values == (1e6, 1e6, 2e6)
        (context,) = item.context
        assert context.article.title == "Телескоп"
        assert context.views.values == (50.0, 50.0, 50.0)

    def test_daily_window_covers_the_whole_last_month(self) -> None:
        source = _source()
        item = SeriesLoader(source).load([_topic(_bundle())], PERIOD)[0]
        assert item.main_daily is not None
        assert item.main_daily.start == date(2025, 1, 1)
        assert item.main_daily.end == date(2025, 3, 31)
        assert item.main_daily.observed == (5.0, 7.0)

    def test_automated_series_is_fetched_for_user_agent_only(self) -> None:
        with_user = SeriesLoader(_source()).load([_topic(_bundle())], PERIOD)[0]
        assert with_user.main_automated is not None
        assert with_user.main_automated.values == (None, 40.0, None)
        assert with_user.main_user_for_automated is not None
        assert with_user.main_user_for_automated.values == (100.0, 200.0, 300.0)
        settings = LoadSettings(agent=Agent.ALL, fetch_daily=False)
        with_all = SeriesLoader(_source(), settings=settings).load([_topic(_bundle())], PERIOD)[0]
        assert with_all.main_automated is None
        assert with_all.main_user_for_automated is None
        assert with_all.main_daily is None

    def test_not_found_bundle_yields_no_article_series_but_a_total(self) -> None:
        empty = TopicBundle("astronomy", UK, BundleStatus.NOT_FOUND)
        item = SeriesLoader(_source()).load([_topic(empty)], PERIOD)[0]
        assert item.main_views is None
        assert item.context == ()
        assert item.main_daily is None
        assert item.project_total.values == (1e6, 1e6, 2e6)

    def test_unknown_article_becomes_gaps_not_errors(self) -> None:
        source = _source()
        source.articles.pop((UK.domain, "Телескоп", Granularity.MONTHLY, Agent.USER, Access.ALL))
        item = SeriesLoader(source).load([_topic(_bundle())], PERIOD)[0]
        assert item.main_views is not None
        assert item.main_views.values == (110.0, 220.0, 330.0)
        # The related article is missing entirely: its context series is all gaps.
        assert item.context[0].views.values == (None, None, None)


def _window(call: tuple[str, tuple[object, ...]]) -> Window:
    window = call[1][2]
    assert isinstance(window, Window)
    return window


class TestPlanning:
    def test_shared_titles_are_fetched_once(self) -> None:
        source = _source()
        topic_a = _topic(_bundle())
        topic_b = ResolvedTopic("b", "b", "Q333", "b", (_bundle(),))
        SeriesLoader(source).load([topic_a, topic_b], PERIOD)
        monthly = [
            call
            for call in source.calls
            if call[0] == "per_article"
            and isinstance(call[1][2], Window)
            and call[1][2].granularity is Granularity.MONTHLY
            and call[1][4] is Agent.USER
        ]
        in_period = [
            c for c in monthly if _window(c).start == PERIOD.start and c[1][3] is Access.ALL
        ]
        assert len(in_period) == 3  # Астрономія, Astronomy, Телескоп
        history = [c for c in monthly if _window(c).start == EARLIEST_MONTH]
        assert [c[1][1] for c in history] == ["Астрономія"]  # the main title, once
        split = {c[1][3] for c in monthly if c[1][3] is not Access.ALL}
        assert split == {Access.DESKTOP, Access.MOBILE_WEB, Access.MOBILE_APP}
        assert len([c for c in monthly if c[1][3] is not Access.ALL]) == 3
        assert len([c for c in source.calls if c[0] == "aggregate"]) == 1

    def test_history_and_access_split_reach_the_loaded_series(self) -> None:
        (loaded,) = SeriesLoader(_source()).load([_topic(_bundle())], PERIOD)
        assert loaded.main_history is not None
        assert loaded.main_history.points[0].period == EARLIEST_MONTH
        assert [a for a, _ in loaded.main_by_access] == [
            Access.DESKTOP,
            Access.MOBILE_WEB,
            Access.MOBILE_APP,
        ]

    def test_no_split_when_one_access_method_is_analysed(self) -> None:
        settings = LoadSettings(access=Access.DESKTOP)
        (loaded,) = SeriesLoader(_source(), settings=settings).load([_topic(_bundle())], PERIOD)
        assert loaded.main_by_access == ()

    def test_upstream_failure_fails_the_whole_load(self) -> None:
        class Failing(FakePageviews):
            def aggregate(
                self, project: WikiProject, window: Window, *, access: Access, agent: Agent
            ) -> Series:
                raise UpstreamError("boom", retryable=True)

        with pytest.raises(UpstreamError):
            SeriesLoader(Failing()).load([_topic(_bundle())], PERIOD)
