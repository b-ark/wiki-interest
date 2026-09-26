"""The control basket: drawn from a month's top list with a seed, outliers left out, kept."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from fakes import FakeMediaWiki, FakePageviews
from wiki_interest.adapters.control_store import JsonBasketStore
from wiki_interest.application.control import ControlBaskets, RenameLog
from wiki_interest.domain.models import WikiProject
from wiki_interest.domain.trust import TrustSettings

RU = WikiProject("ru")
MONTHS = [date(2024 + (7 + k) // 12, (7 + k) % 12 + 1, 1) for k in range(25)]  # 2024-08..2026-08


class _Clock:
    def __init__(self, today: date) -> None:
        self.day = today

    def today(self) -> date:
        return self.day


def _world() -> FakePageviews:
    pageviews = FakePageviews()
    titles = [f"Article {n}" for n in range(40)]
    pageviews.tops["ru.wikipedia"] = [
        ("Заглавная страница", 9_000_000.0),
        ("Служебная:Поиск", 500_000.0),
        *[(title, 100_000.0 - n) for n, title in enumerate(titles)],
    ]
    for n, title in enumerate(titles):
        values = dict.fromkeys(MONTHS, 1000.0 + n)
        if n == 3:
            values[MONTHS[-1]] = 50_000.0  # in the top list for a burst
        if n == 4:
            values = dict.fromkeys(MONTHS[-6:], 800.0)  # too young
        pageviews.set_article(RU, title, values)
    return pageviews


def _baskets(tmp_path: Path, clock: _Clock, pageviews: FakePageviews) -> ControlBaskets:
    settings = TrustSettings(control_sample=10, control_candidates=20, control_top=30)
    return ControlBaskets(pageviews, JsonBasketStore(tmp_path), clock, settings, max_workers=2)


def test_the_basket_leaves_out_the_main_page_other_namespaces_bursts_and_young_articles(
    tmp_path: Path,
) -> None:
    basket = _baskets(tmp_path, _Clock(date(2026, 9, 26)), _world()).basket(RU)
    assert basket is not None
    assert basket.reference_month == date(2026, 8, 1)
    assert len(basket.titles) == 10
    assert "Заглавная страница" not in basket.titles
    assert "Служебная:Поиск" not in basket.titles
    assert "Article 3" not in basket.titles
    assert "Article 4" not in basket.titles


def test_the_draw_is_seeded_and_the_basket_kept(tmp_path: Path) -> None:
    clock = _Clock(date(2026, 9, 26))
    pageviews = _world()
    first = _baskets(tmp_path / "a", clock, pageviews).basket(RU)
    again = _baskets(tmp_path / "b", clock, pageviews).basket(RU)
    assert first is not None
    assert again is not None
    assert first.titles == again.titles  # the same top list gives the same basket
    calls = len(pageviews.calls)
    kept = _baskets(tmp_path / "a", clock, pageviews).basket(RU)
    assert kept == first
    assert len(pageviews.calls) == calls  # read from the store, nothing fetched


def test_an_old_basket_is_built_again(tmp_path: Path) -> None:
    clock = _Clock(date(2026, 9, 26))
    pageviews = _world()
    _baskets(tmp_path, clock, pageviews).basket(RU)
    clock.day = date(2027, 6, 1)  # past the 180 days
    rebuilt = _baskets(tmp_path, clock, pageviews).basket(RU)
    assert rebuilt is not None
    assert rebuilt.built == date(2027, 6, 1)


def test_the_shares_are_per_million_of_the_edition(tmp_path: Path) -> None:
    baskets = _baskets(tmp_path, _Clock(date(2026, 9, 26)), _world())
    shares = baskets.shares(RU, MONTHS[-3:], [1e8, 1e8, None])
    assert len(shares) == 10
    first = shares[0]
    assert first[0] is not None
    assert 9.9 < first[0] < 10.5
    assert first[2] is None


def test_an_edition_without_a_top_list_has_no_basket(tmp_path: Path) -> None:
    baskets = _baskets(tmp_path, _Clock(date(2026, 9, 26)), FakePageviews())
    assert baskets.basket(RU) is None
    assert baskets.shares(RU, MONTHS, [1e8] * len(MONTHS)) == []


def test_renames_are_read_on_the_redirects_left_behind() -> None:
    mediawiki = FakeMediaWiki()
    mediawiki.move_log[(RU, "Веганизм")] = [date(2019, 3, 2)]
    assert RenameLog(mediawiki).moves(RU, "Веганство", ("Веганизм",)) == [date(2019, 3, 2)]
