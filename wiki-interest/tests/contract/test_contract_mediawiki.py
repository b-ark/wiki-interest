"""MediaWiki adapter against recorded uk.wikipedia responses."""

from wiki_interest.ports.mediawiki import PageInfo

from .conftest import Replay


def test_page_info_normalises_follows_redirect_and_reports_missing(replay: Replay) -> None:
    result = replay("mediawiki-page-info-uk-redirect-and-missing")
    assert result["астрономія"] == PageInfo(title="Астрономія", qid="Q333")
    assert result["Astronomy"] == PageInfo(
        title="Астрономія", qid="Q333", redirected_from="Astronomy", redirect_title="Astronomy"
    )
    assert result["Nonexistent page xyz 123"] is None


def test_redirects_to_lists_main_namespace_redirects(replay: Replay) -> None:
    redirects = replay("mediawiki-redirects-to-uk-astronomy")
    assert "Astronomy" in redirects
    assert all(isinstance(title, str) and title for title in redirects)


def test_search_ranks_the_article_first(replay: Replay) -> None:
    titles = replay("mediawiki-search-uk-fasting")
    assert titles[0] == "Інтервальне голодування"
    assert len(titles) <= 5
