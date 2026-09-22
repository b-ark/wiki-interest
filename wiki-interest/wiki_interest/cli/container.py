"""Composition root: builds adapters and use-cases from settings.

This is the only place that knows which concrete adapter implements which port. Everything
else receives its collaborators through constructors, which keeps the use-cases testable with
in-memory fakes and lets a future data source (dumps, a different API) be swapped here alone.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Self

from wiki_interest.adapters.clock import SystemClock
from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.mediawiki import MediaWikiApi
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.adapters.sqlite_cache import SqliteCache
from wiki_interest.adapters.wikidata import WikidataApi
from wiki_interest.adapters.wikimedia_rest import WikimediaRestPageviews
from wiki_interest.application.analysis import AnalysisSettings
from wiki_interest.application.loading import LoadSettings, SeriesLoader
from wiki_interest.application.resolution import TopicResolver
from wiki_interest.config import Settings
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.domain.models import Access, Agent
from wiki_interest.ports import Clock, MediaWikiGateway, PageviewsSource, WikidataGateway

__all__ = ["Container"]


@dataclass
class Container:
    """Wired collaborators for one process.

    Build it with :meth:`build` (real adapters) or construct it directly with fakes in tests.
    Use it as a context manager so the HTTP client and the cache are closed.
    """

    settings: Settings
    clock: Clock
    http: HttpJsonClient
    pageviews: PageviewsSource
    wikidata: WikidataGateway
    mediawiki: MediaWikiGateway
    closeables: list[Callable[[], None]] = field(default_factory=list)

    @classmethod
    def build(cls, settings: Settings | None = None, *, persistent_cache: bool = True) -> Self:
        """Create real adapters.

        Args:
            settings: Configuration; loaded from the environment when omitted.
            persistent_cache: Use the SQLite cache at ``settings.cache_path``; ``False`` keeps
                responses in memory for the lifetime of the process (tests, one-off checks).
        """
        settings = settings or Settings()
        closeables: list[Callable[[], None]] = []
        if persistent_cache:
            sqlite_cache = SqliteCache(settings.cache_path)
            closeables.append(sqlite_cache.close)
            http = HttpJsonClient(settings, sqlite_cache)
        else:
            http = HttpJsonClient(settings, InMemoryCache())
        closeables.append(http.close)
        clock = SystemClock()
        return cls(
            settings=settings,
            clock=clock,
            http=http,
            pageviews=WikimediaRestPageviews(http, clock),
            wikidata=WikidataApi(http, settings.resolution_ttl_s),
            mediawiki=MediaWikiApi(http, settings.resolution_ttl_s),
            closeables=closeables,
        )

    def resolver(self) -> TopicResolver:
        """Topic resolver over the wired gateways."""
        return TopicResolver(self.wikidata, self.mediawiki)

    def loader(self, request: AnalysisRequest) -> SeriesLoader:
        """Series loader configured from the request's traffic filters."""
        load_settings = LoadSettings(
            access=Access(request.access),
            agent=Agent(request.agent),
            max_workers=self.settings.max_concurrency,
        )
        return SeriesLoader(self.pageviews, settings=load_settings)

    def analysis_settings(self, request: AnalysisRequest) -> AnalysisSettings:
        """Analysis thresholds from settings, normalisation switch from the request."""
        return AnalysisSettings.from_thresholds(
            self.settings.reliability_thresholds(),
            normalise=request.normalization == "per_million",
        )

    def close(self) -> None:
        """Release the HTTP client and the cache; safe to call more than once."""
        while self.closeables:
            self.closeables.pop()()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
