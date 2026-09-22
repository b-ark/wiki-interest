"""Wikidata adapter: parameter building, batching, entity mapping and claim filtering."""

from __future__ import annotations

from typing import Any

import httpx
import pytest
import respx

from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.mediawiki import ActionApiError
from wiki_interest.adapters.wikidata import MAX_IDS_PER_REQUEST, WikidataApi
from wiki_interest.domain.models import WikiProject

WD = "https://www.wikidata.org/w/api.php"
UK, PL, CS = WikiProject("uk"), WikiProject("pl"), WikiProject("cs")


@pytest.fixture
def wikidata(http: HttpJsonClient) -> WikidataApi:
    return WikidataApi(http, ttl_seconds=3600)


def _search_hit(qid: str, label: str, match_type: str, text: str) -> dict[str, Any]:
    return {
        "id": qid,
        "label": label,
        "description": f"about {label}",
        "match": {"type": match_type, "language": "en", "text": text},
    }


class TestSearchEntities:
    def test_sends_documented_parameters_and_maps_candidates(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        route = respx_mock.get(WD).mock(
            return_value=httpx.Response(
                200,
                json={
                    "search": [
                        _search_hit("Q1", "Intermittent Fasting", "label", "Intermittent fasting"),
                        _search_hit("Q2", "IF diet", "alias", "intermittent fasting"),
                        {"id": "Q3", "label": "Fasting"},
                    ]
                },
            )
        )
        found = wikidata.search_entities("intermittent fasting", "en", limit=3)
        params = route.calls.last.request.url.params
        assert params["action"] == "wbsearchentities"
        assert params["search"] == "intermittent fasting"
        assert params["language"] == "en"
        assert params["uselang"] == "en"
        assert params["type"] == "item"
        assert params["limit"] == "3"
        assert params["format"] == "json"
        assert [c.qid for c in found] == ["Q1", "Q2", "Q3"]
        assert found[0].exact_label_match is True, "label equal ignoring case"
        assert found[0].description == "about Intermittent Fasting"
        assert found[1].exact_label_match is True, "an exact alias names the item too"
        assert found[2].exact_label_match is False
        assert found[2].description is None

    def test_match_text_counts_when_label_is_localised_differently(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        respx_mock.get(WD).mock(
            return_value=httpx.Response(
                200, json={"search": [_search_hit("Q333", "Астрономія", "label", "astronomy")]}
            )
        )
        found = wikidata.search_entities("Astronomy", "en")
        assert found[0].exact_label_match is True

    def test_partial_alias_match_is_not_exact(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        respx_mock.get(WD).mock(
            return_value=httpx.Response(
                200, json={"search": [_search_hit("Q1860", "English", "alias", "English lang")]}
            )
        )
        assert wikidata.search_entities("English language", "en")[0].exact_label_match is False

    def test_empty_result(self, respx_mock: respx.MockRouter, wikidata: WikidataApi) -> None:
        respx_mock.get(WD).mock(return_value=httpx.Response(200, json={"search": []}))
        assert wikidata.search_entities("zzz", "en") == ()


def _entities_handler(entities: dict[str, Any]) -> Any:
    """Answer ``wbgetentities`` with the subset of ``entities`` that was asked for."""

    def handler(request: httpx.Request) -> httpx.Response:
        ids = request.url.params["ids"].split("|")
        for qid in ids:
            if qid.startswith("Qbad"):
                return httpx.Response(
                    200,
                    json={"error": {"code": "no-such-entity", "info": "nope", "id": qid}},
                )
        return httpx.Response(
            200,
            json={
                "entities": {qid: entities.get(qid, {"id": qid, "missing": ""}) for qid in ids},
                "success": 1,
            },
        )

    return handler


class TestSitelinks:
    def test_maps_sites_back_to_projects_and_omits_absent_ones(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        route = respx_mock.get(WD).mock(
            side_effect=_entities_handler(
                {
                    "Q1666254": {
                        "id": "Q1666254",
                        "sitelinks": {
                            "ukwiki": {"site": "ukwiki", "title": "Інтервальне голодування"},
                            "cswiki": {"site": "cswiki", "title": "Přerušovaný půst"},
                            "enwiki": {"site": "enwiki", "title": "Intermittent fasting"},
                        },
                    },
                    "Q2": {"id": "Q2", "sitelinks": {}},
                }
            )
        )
        result = wikidata.sitelinks(["Q1666254", "Q2", "Q99999999"], [UK, PL, CS])
        params = route.calls.last.request.url.params
        assert params["action"] == "wbgetentities"
        assert params["props"] == "sitelinks"
        assert params["sitefilter"] == "ukwiki|plwiki|cswiki"
        assert params["ids"] == "Q1666254|Q2|Q99999999"
        assert result == {
            "Q1666254": {UK: "Інтервальне голодування", CS: "Přerušovaný půst"},
            "Q2": {},
        }
        assert "Q99999999" not in result, "missing entities are absent from the outer mapping"

    def test_ids_are_batched_in_chunks_of_fifty(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        route = respx_mock.get(WD).mock(side_effect=_entities_handler({}))
        qids = [f"Q{i}" for i in range(1, 121)]
        wikidata.sitelinks(qids, [UK])
        assert route.call_count == 3
        sizes = [len(call.request.url.params["ids"].split("|")) for call in route.calls]
        assert sizes == [MAX_IDS_PER_REQUEST, MAX_IDS_PER_REQUEST, 20]

    def test_duplicate_ids_are_requested_once(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        route = respx_mock.get(WD).mock(side_effect=_entities_handler({}))
        wikidata.sitelinks(["Q1", "Q1", "Q2"], [UK])
        assert route.calls.last.request.url.params["ids"] == "Q1|Q2"

    def test_unknown_id_failing_the_batch_is_dropped_and_retried(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        route = respx_mock.get(WD).mock(
            side_effect=_entities_handler(
                {"Q1": {"id": "Q1", "sitelinks": {"ukwiki": {"site": "ukwiki", "title": "A"}}}}
            )
        )
        result = wikidata.sitelinks(["Q1", "Qbad1", "Qbad2"], [UK])
        assert result == {"Q1": {UK: "A"}}
        assert route.call_count == 3
        assert route.calls.last.request.url.params["ids"] == "Q1"

    def test_only_unknown_ids_fail(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        respx_mock.get(WD).mock(side_effect=_entities_handler({}))
        assert wikidata.sitelinks(["Qbad1"], [UK]) == {}

    def test_other_api_errors_propagate(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        respx_mock.get(WD).mock(
            return_value=httpx.Response(
                200, json={"error": {"code": "param-missing", "info": "ids required"}}
            )
        )
        with pytest.raises(ActionApiError) as info:
            wikidata.sitelinks(["Q1"], [UK])
        assert info.value.code == "param-missing"
        assert info.value.retryable is False


class TestLabels:
    def test_prefers_requested_language_then_english(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        route = respx_mock.get(WD).mock(
            side_effect=_entities_handler(
                {
                    "Q1": {"id": "Q1", "labels": {"uk": {"value": "Один"}, "en": {"value": "One"}}},
                    "Q2": {"id": "Q2", "labels": {"en": {"value": "Two"}}},
                    "Q3": {"id": "Q3", "labels": {"de": {"value": "Drei"}}},
                }
            )
        )
        result = wikidata.labels(["Q1", "Q2", "Q3"], "uk")
        params = route.calls.last.request.url.params
        assert params["props"] == "labels"
        assert params["languages"] == "uk|en"
        assert result == {"Q1": "Один", "Q2": "Two"}

    def test_english_request_does_not_duplicate_language(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        route = respx_mock.get(WD).mock(side_effect=_entities_handler({}))
        wikidata.labels(["Q1"], "en")
        assert route.calls.last.request.url.params["languages"] == "en"


def _claim(target: str | None, snaktype: str = "value", rank: str = "normal") -> dict[str, Any]:
    snak: dict[str, Any] = {"snaktype": snaktype, "property": "P279"}
    if target is not None:
        snak["datavalue"] = {
            "value": {"entity-type": "item", "id": target},
            "type": "wikibase-entityid",
        }
    return {"mainsnak": snak, "type": "statement", "rank": rank}


class TestRelatedEntities:
    def test_reads_item_ids_per_property_skipping_valueless_and_deprecated(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            prop = request.url.params["property"]
            assert request.url.params["action"] == "wbgetclaims"
            assert request.url.params["entity"] == "Q333"
            claims = {
                "P279": [
                    _claim("Q14632398"),
                    _claim(None, snaktype="somevalue"),
                    _claim(None, snaktype="novalue"),
                    _claim("Q999", rank="deprecated"),
                    _claim("Q413"),
                ],
                "P361": [],
            }
            body = {"claims": {prop: claims[prop]}} if claims.get(prop) else {"claims": {}}
            return httpx.Response(200, json=body)

        route = respx_mock.get(WD).mock(side_effect=handler)
        result = wikidata.related_entities("Q333", ["P279", "P361", "P527"])
        assert result == {"P279": ("Q14632398", "Q413"), "P361": (), "P527": ()}
        assert route.call_count == 3, "one request per property"

    def test_other_api_errors_propagate(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        respx_mock.get(WD).mock(
            return_value=httpx.Response(
                200, json={"error": {"code": "param-missing", "info": "entity required"}}
            )
        )
        with pytest.raises(ActionApiError) as info:
            wikidata.related_entities("Q333", ["P279"])
        assert info.value.code == "param-missing"

    def test_unknown_entity_yields_empty_tuples(
        self, respx_mock: respx.MockRouter, wikidata: WikidataApi
    ) -> None:
        respx_mock.get(WD).mock(
            return_value=httpx.Response(
                200, json={"error": {"code": "no-such-entity", "info": "x", "id": "Q0"}}
            )
        )
        assert wikidata.related_entities("Q0", ["P279"]) == {"P279": ()}
