"""Smoke tests against the real Wikimedia APIs. Deselected by default; run with ``pytest -m live``.

They assert only on facts that do not change (closed months, stable sitelinks), so they
detect API shape changes rather than data drift.
"""

from collections.abc import Iterator
from datetime import date

import pytest

from wiki_interest.adapters.clock import SystemClock
from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.mediawiki import MediaWikiApi
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.adapters.wikidata import WikidataApi
from wiki_interest.adapters.wikimedia_rest import WikimediaRestPageviews
from wiki_interest.config import Settings
from wiki_interest.domain.models import Access, Agent, Granularity, WikiProject, Window

pytestmark = pytest.mark.live

UK, PL, CS = WikiProject("uk"), WikiProject("pl"), WikiProject("cs")


@pytest.fixture(scope="module")
def http() -> Iterator[HttpJsonClient]:
    with HttpJsonClient(Settings(), InMemoryCache()) as client:
        yield client


def test_pageviews_monthly_series_is_complete_for_a_closed_year(http: HttpJsonClient) -> None:
    source = WikimediaRestPageviews(http, SystemClock())
    window = Window(Granularity.MONTHLY, date(2024, 1, 1), date(2024, 12, 1))
    series = source.per_article(UK, "Астрономія", window, access=Access.ALL, agent=Agent.USER)
    assert series.completeness == 1.0
    assert series.values[0] == 3700.0
    aggregate = source.aggregate(UK, window, access=Access.ALL, agent=Agent.USER)
    assert aggregate.completeness == 1.0
    assert aggregate.values[0] == 115_282_138.0


def test_pageviews_404_is_reported_as_no_data(http: HttpJsonClient) -> None:
    source = WikimediaRestPageviews(http, SystemClock())
    window = Window(Granularity.MONTHLY, date(2024, 1, 1), date(2024, 3, 1))
    series = source.per_article(
        PL, "Post przerywany", window, access=Access.ALL, agent=Agent.AUTOMATED
    )
    assert series.values == (None, None, None)


def test_wikidata_resolves_intermittent_fasting_to_uk_and_cs_but_not_pl(
    http: HttpJsonClient,
) -> None:
    wikidata = WikidataApi(http, http.settings.resolution_ttl_s)
    candidates = wikidata.search_entities("intermittent fasting", "en")
    assert candidates[0].qid == "Q1666254"
    assert candidates[0].exact_label_match is True
    links = wikidata.sitelinks(["Q1666254"], [UK, PL, CS])["Q1666254"]
    assert links[UK] == "Інтервальне голодування"
    assert links[CS] == "Přerušovaný půst"
    assert PL not in links
    assert "Q14632398" in wikidata.related_entities("Q333", ["P279"])["P279"]


def test_mediawiki_resolves_redirects_and_search(http: HttpJsonClient) -> None:
    mediawiki = MediaWikiApi(http, http.settings.resolution_ttl_s)
    info = mediawiki.page_info(UK, ["Astronomy", "Nonexistent page xyz 123"])
    assert info["Astronomy"] is not None
    assert info["Astronomy"].title == "Астрономія"
    assert info["Astronomy"].qid == "Q333"
    assert info["Nonexistent page xyz 123"] is None
    assert "Astronomy" in mediawiki.redirects_to(UK, "Астрономія")
    assert mediawiki.search(UK, "інтервальне голодування")[0] == "Інтервальне голодування"
