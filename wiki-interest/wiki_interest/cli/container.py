"""Composition root: builds adapters and use-cases from settings.

This is the only place that knows which concrete adapter implements which port. Everything
else receives its collaborators through constructors, which keeps the use-cases testable with
in-memory fakes and lets a future data source (dumps, a different API) be swapped here alone.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Self

from wiki_interest import __version__
from wiki_interest.adapters.agent_summary import AgentSummaryRenderer
from wiki_interest.adapters.clock import SystemClock
from wiki_interest.adapters.fpdf_report import FpdfReportRenderer
from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.matplotlib_charts import MatplotlibChartRenderer
from wiki_interest.adapters.mediawiki import MediaWikiApi
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.adapters.method_report import MethodReportRenderer
from wiki_interest.adapters.sqlite_cache import SqliteCache
from wiki_interest.adapters.wikidata import WikidataApi
from wiki_interest.adapters.wikimedia_rest import WikimediaRestPageviews
from wiki_interest.application.analysis import AnalysisSettings
from wiki_interest.application.coverage import CoverageAdvisor
from wiki_interest.application.loading import LoadSettings, SeriesLoader
from wiki_interest.application.pipeline import Pipeline, Renderers, RunServices
from wiki_interest.application.resolution import TopicResolver
from wiki_interest.application.summary_builder import ProvenanceInput
from wiki_interest.config import Settings
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.domain.models import Access, Agent
from wiki_interest.i18n import Translator
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

    # -- use-case factories ----------------------------------------------------------------

    def resolver(self) -> TopicResolver:
        """Topic resolver over the wired gateways."""
        return TopicResolver(self.wikidata, self.mediawiki)

    def coverage(self) -> CoverageAdvisor:
        """Advisor that finds editions without an article and what could stand in."""
        return CoverageAdvisor(self.wikidata, self.mediawiki, self.pageviews)

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
            season=self.settings.season_settings(),
            anomalies=self.settings.anomaly_settings(),
        )

    def renderers_for(self, language: str) -> tuple[Translator, Renderers]:
        """Translator and renderers for one report language."""
        translator = Translator(language)
        renderers = Renderers(
            charts=MatplotlibChartRenderer(
                empty_note=translator.t("chart.no_data"),
                missing_label=translator.t("value.na"),
                decimal_sep=translator.number_style.decimal_sep,
                thousands_sep=translator.number_style.thousands_sep,
            ),
            agent_summary=AgentSummaryRenderer(translator),
            report_pdf=FpdfReportRenderer(translator),
            method=MethodReportRenderer(),
        )
        return translator, renderers

    def provenance(self) -> ProvenanceInput:
        """Facts about this process and its HTTP traffic so far."""
        stats = self.http.stats.snapshot()
        return ProvenanceInput(
            code_version=__version__,
            user_agent=self.settings.user_agent,
            sources=(
                self.settings.pageviews_base_url,
                self.settings.wikidata_api_url,
                "https://*.wikipedia.org/w/api.php",
            ),
            request_count=stats.requests_made,
            cache_hits=stats.cache_hits,
            thresholds=self.settings.thresholds(),
        )

    def services_for(self, request: AnalysisRequest) -> RunServices:
        """Everything the pipeline needs for one request (implements ``ServiceFactory``)."""
        translator, renderers = self.renderers_for(request.report.language)
        return RunServices(
            resolver=self.resolver(),
            coverage=self.coverage(),
            loader=self.loader(request),
            analysis_settings=self.analysis_settings(request),
            translator=translator,
            renderers=renderers,
            provenance=self.provenance(),
            assessment=self.settings.assessment_settings(),
            stop_after_resolve=self.settings.stop_after == "resolve",
        )

    def pipeline(self) -> Pipeline:
        """The end-to-end pipeline bound to this container."""
        return Pipeline(self, self.clock)

    # -- lifecycle ------------------------------------------------------------------------

    def close(self) -> None:
        """Release the HTTP client and the cache; safe to call more than once."""
        while self.closeables:
            self.closeables.pop()()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
