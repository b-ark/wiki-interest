"""Ports: Protocol interfaces the application depends on.

A port describes *what* the application needs (pageview series, title resolution, caching,
rendering) without saying *how*. Adapters implement them; tests substitute in-memory fakes.
"""

from wiki_interest.ports.cache import Cache
from wiki_interest.ports.clock import Clock
from wiki_interest.ports.mediawiki import MediaWikiGateway, PageInfo
from wiki_interest.ports.pageviews import PageviewsSource
from wiki_interest.ports.renderers import ChartRenderer, ReportRenderer
from wiki_interest.ports.wikidata import WikidataGateway

__all__ = [
    "Cache",
    "ChartRenderer",
    "Clock",
    "MediaWikiGateway",
    "PageInfo",
    "PageviewsSource",
    "ReportRenderer",
    "WikidataGateway",
]
