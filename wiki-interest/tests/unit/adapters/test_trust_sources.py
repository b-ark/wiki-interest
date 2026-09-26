"""The outside checks of the trust: a month's top list, the move log, the stored basket."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import respx

from wiki_interest.adapters.control_store import JsonBasketStore
from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.mediawiki import MediaWikiApi
from wiki_interest.adapters.wikimedia_rest import WikimediaRestPageviews
from wiki_interest.domain.models import Access, WikiProject
from wiki_interest.ports.control import ControlBasket

RU = WikiProject("ru")
TOP = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/ru.wikipedia/all-access/2026/08/all-days"
API = "https://ru.wikipedia.org/w/api.php"


class _Clock:
    def today(self) -> date:
        return date(2026, 9, 26)


def test_the_top_list_comes_most_viewed_first_with_spaces(
    respx_mock: respx.MockRouter, http: HttpJsonClient
) -> None:
    articles = [
        {"article": "Заглавная_страница", "views": 9_000_000, "rank": 1},
        {"article": "Служебная:Поиск", "views": 800_000, "rank": 2},
        {"article": "Лев_Толстой", "views": 120_000, "rank": 3},
    ]
    respx_mock.get(TOP).mock(
        return_value=httpx.Response(200, json={"items": [{"articles": articles}]})
    )
    top = WikimediaRestPageviews(http, _Clock()).top(RU, date(2026, 8, 1), access=Access.ALL)
    assert top[0] == ("Заглавная страница", 9_000_000.0)
    assert top[-1] == ("Лев Толстой", 120_000.0)


def test_a_missing_top_list_is_empty(respx_mock: respx.MockRouter, http: HttpJsonClient) -> None:
    respx_mock.get(TOP).mock(return_value=httpx.Response(404, json={}))
    assert WikimediaRestPageviews(http, _Clock()).top(RU, date(2026, 8, 1), access=Access.ALL) == ()


def test_the_move_log_gives_the_days_a_title_was_moved(
    respx_mock: respx.MockRouter, http: HttpJsonClient
) -> None:
    route = respx_mock.get(API).mock(
        return_value=httpx.Response(
            200,
            json={
                "batchcomplete": True,
                "query": {
                    "logevents": [
                        {"timestamp": "2023-04-02T10:00:00Z", "type": "move"},
                        {"timestamp": "2019-01-15T08:30:00Z", "type": "move"},
                    ]
                },
            },
        )
    )
    moves = MediaWikiApi(http, ttl_seconds=3600).moves(RU, "Веганизм")
    assert moves == (date(2019, 1, 15), date(2023, 4, 2))
    params = route.calls.last.request.url.params
    assert params["list"] == "logevents"
    assert params["letype"] == "move"
    assert params["letitle"] == "Веганизм"


def test_a_basket_is_stored_and_read_back(tmp_path: Path) -> None:
    store = JsonBasketStore(tmp_path / "control")
    assert store.load("ru.wikipedia") is None
    basket = ControlBasket(
        project="ru.wikipedia",
        reference_month=date(2026, 8, 1),
        built=date(2026, 9, 26),
        seed=7,
        titles=("Лев Толстой", "Москва"),
    )
    store.save(basket)
    assert store.load("ru.wikipedia") == basket
    (tmp_path / "control" / "ru.wikipedia.json").write_text("{broken", encoding="utf-8")
    assert store.load("ru.wikipedia") is None
