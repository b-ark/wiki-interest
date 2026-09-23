"""MediaWiki adapter: title mapping through normalisation and redirects, batching, continuation."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.mediawiki import (
    MAX_TITLES_PER_REQUEST,
    ActionApiError,
    MediaWikiApi,
)
from wiki_interest.domain.models import WikiProject
from wiki_interest.errors import UpstreamError
from wiki_interest.ports.mediawiki import Mention, PageInfo

UK = WikiProject("uk")
API = "https://uk.wikipedia.org/w/api.php"


@pytest.fixture
def mediawiki(http: HttpJsonClient) -> MediaWikiApi:
    return MediaWikiApi(http, ttl_seconds=3600)


def _page(title: str, qid: str | None = None, **extra: Any) -> dict[str, Any]:
    page: dict[str, Any] = {"ns": 0, "title": title, "pageid": abs(hash(title)) % 10_000, **extra}
    if qid:
        page["pageprops"] = {"wikibase_item": qid}
    return page


class TestPageInfo:
    def test_maps_requested_titles_through_normalisation_and_redirects(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        route = respx_mock.get(API).mock(
            return_value=httpx.Response(
                200,
                json={
                    "batchcomplete": True,
                    "query": {
                        "normalized": [
                            {"fromencoded": False, "from": "астрономія", "to": "Астрономія"},
                            {"fromencoded": False, "from": "astronomy", "to": "Astronomy"},
                        ],
                        "redirects": [{"from": "Astronomy", "to": "Астрономія"}],
                        "pages": [
                            _page("Астрономія", "Q333"),
                            _page("Зоряна астрономія", "Q2295061"),
                            {"ns": 0, "title": "Nonexistent page", "missing": True},
                            {"title": "Bad|title", "invalid": True, "invalidreason": "..."},
                            _page("No item"),
                        ],
                    },
                },
            )
        )
        result = mediawiki.page_info(
            UK,
            [
                "астрономія",
                "astronomy",
                "Зоряна астрономія",
                "Nonexistent page",
                "Bad|title",
                "No item",
            ],
        )
        params = route.calls.last.request.url.params
        assert params["action"] == "query"
        assert params["redirects"] == "1"
        assert params["prop"] == "pageprops"
        assert params["ppprop"] == "wikibase_item"
        assert params["format"] == "json"
        assert params["formatversion"] == "2"
        assert result == {
            "астрономія": PageInfo(title="Астрономія", qid="Q333"),
            "astronomy": PageInfo(
                title="Астрономія",
                qid="Q333",
                redirected_from="astronomy",
                redirect_title="Astronomy",
            ),
            "Зоряна астрономія": PageInfo(title="Зоряна астрономія", qid="Q2295061"),
            "Nonexistent page": None,
            "Bad|title": None,
            "No item": PageInfo(title="No item", qid=None),
        }

    def test_titles_are_batched_in_chunks_of_fifty(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            titles = request.url.params["titles"].split("|")
            return httpx.Response(200, json={"query": {"pages": [_page(t) for t in titles]}})

        route = respx_mock.get(API).mock(side_effect=handler)
        titles = [f"T{i}" for i in range(120)]
        result = mediawiki.page_info(UK, titles)
        assert route.call_count == 3
        sizes = [len(call.request.url.params["titles"].split("|")) for call in route.calls]
        assert sizes == [MAX_TITLES_PER_REQUEST, MAX_TITLES_PER_REQUEST, 20]
        assert len(result) == 120
        assert all(info is not None for info in result.values())

    def test_redirect_loop_does_not_hang(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        respx_mock.get(API).mock(
            return_value=httpx.Response(
                200,
                json={
                    "query": {
                        "redirects": [{"from": "A", "to": "B"}, {"from": "B", "to": "A"}],
                        "pages": [_page("A", "Q1"), _page("B", "Q2")],
                    }
                },
            )
        )
        result = mediawiki.page_info(UK, ["A"])
        assert result["A"] is not None
        assert result["A"].title in {"A", "B"}

    def test_empty_input_makes_no_request(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        route = respx_mock.get(API)
        assert mediawiki.page_info(UK, []) == {}
        assert not route.called


class TestRedirectsTo:
    def test_follows_continuation_until_exhausted(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            params = request.url.params
            assert params["prop"] == "redirects"
            assert params["rdnamespace"] == "0"
            assert params["rdlimit"] == "max"
            if "rdcontinue" not in params:
                return httpx.Response(
                    200,
                    json={
                        "continue": {"rdcontinue": "0|6003345", "continue": "||"},
                        "query": {
                            "pages": [{**_page("Астрономія"), "redirects": [_page("Astronomy")]}]
                        },
                    },
                )
            assert params["rdcontinue"] == "0|6003345"
            return httpx.Response(
                200,
                json={
                    "batchcomplete": True,
                    "query": {
                        "pages": [{**_page("Астрономія"), "redirects": [_page("Астрономия")]}]
                    },
                },
            )

        route = respx_mock.get(API).mock(side_effect=handler)
        assert mediawiki.redirects_to(UK, "Астрономія") == ("Astronomy", "Астрономия")
        assert route.call_count == 2

    def test_page_without_redirects_or_missing_yields_empty(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        respx_mock.get(API).mock(
            return_value=httpx.Response(
                200, json={"query": {"pages": [{"ns": 0, "title": "Nope", "missing": True}]}}
            )
        )
        assert mediawiki.redirects_to(UK, "Nope") == ()


class TestSearch:
    def test_returns_titles_in_result_order(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        route = respx_mock.get(API).mock(
            return_value=httpx.Response(
                200,
                json={
                    "query": {
                        "searchinfo": {"totalhits": 2},
                        "search": [_page("Інтервальне голодування"), _page("Голодування")],
                    }
                },
            )
        )
        found = mediawiki.search(UK, "інтервальне голодування", limit=2)
        params = route.calls.last.request.url.params
        assert params["list"] == "search"
        assert params["srsearch"] == "інтервальне голодування"
        assert params["srnamespace"] == "0"
        assert params["srlimit"] == "2"
        assert found == ("Інтервальне голодування", "Голодування")

    def test_unexpected_shape_is_upstream_error(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        respx_mock.get(API).mock(return_value=httpx.Response(200, json={"query": []}))
        with pytest.raises(UpstreamError):
            mediawiki.search(UK, "x")

    def test_api_error_envelope_is_raised_as_action_api_error(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        respx_mock.get(API).mock(
            return_value=httpx.Response(
                200, json={"error": {"code": "invalidtitle", "info": "Bad"}}
            )
        )
        with pytest.raises(ActionApiError) as info:
            mediawiki.search(UK, "|")
        assert info.value.code == "invalidtitle"
        assert isinstance(info.value, UpstreamError)


class TestRedirectTargets:
    def test_redirect_into_a_section_reports_title_and_fragment(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        respx_mock.get(API).mock(
            return_value=httpx.Response(
                200,
                json={
                    "query": {
                        "normalized": [{"from": "post przerywany", "to": "Post przerywany"}],
                        "redirects": [
                            {
                                "from": "Post przerywany",
                                "to": "Głodówka",
                                "tofragment": "Post przerywany",
                            }
                        ],
                        "pages": [_page("Głodówka", "Q9284146")],
                    }
                },
            )
        )
        info = mediawiki.page_info(UK, ["post przerywany"])["post przerywany"]
        assert info == PageInfo(
            title="Głodówka",
            qid="Q9284146",
            redirected_from="post przerywany",
            redirect_title="Post przerywany",
            fragment="Post przerywany",
        )

    def test_fragment_comes_from_the_last_hop_of_a_chain(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        respx_mock.get(API).mock(
            return_value=httpx.Response(
                200,
                json={
                    "query": {
                        "redirects": [
                            {"from": "A", "to": "B", "tofragment": "old"},
                            {"from": "B", "to": "C"},
                        ],
                        "pages": [_page("C")],
                    }
                },
            )
        )
        info = mediawiki.page_info(UK, ["A"])["A"]
        assert info is not None
        assert info.redirect_title == "A"
        assert info.fragment is None


class TestMentions:
    def test_searches_the_exact_phrase_and_cleans_snippets(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        snippet = (
            'stosować tzw. <span class="searchmatch">post</span> '
            '<span class="searchmatch">przerywany</span>\ufeff &amp; dietę'
        )
        route = respx_mock.get(API).mock(
            return_value=httpx.Response(
                200,
                json={"query": {"search": [_page("Insulinooporność", snippet=snippet)]}},
            )
        )
        found = mediawiki.mentions(UK, 'post "przerywany"', limit=4)
        params = route.calls.last.request.url.params
        assert params["srsearch"] == '"post  przerywany"'
        assert params["srprop"] == "snippet"
        assert params["srlimit"] == "4"
        assert found == (
            Mention(title="Insulinooporność", snippet="stosować tzw. post przerywany & dietę"),
        )

    def test_hit_without_snippet_has_empty_passage(
        self, respx_mock: respx.MockRouter, mediawiki: MediaWikiApi
    ) -> None:
        respx_mock.get(API).mock(
            return_value=httpx.Response(200, json={"query": {"search": [_page("X")]}})
        )
        assert mediawiki.mentions(UK, "x") == (Mention(title="X", snippet=""),)
