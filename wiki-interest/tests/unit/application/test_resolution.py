"""Topic resolution: entities, main articles, redirects, substitutes, clarification."""

from __future__ import annotations

import pytest

from fakes import FakeEntity, FakeMediaWiki, FakePage, FakeWikidata
from wiki_interest.application.resolution import ResolutionSettings, TopicResolver
from wiki_interest.contracts.request import AnalysisRequest, TopicSpec
from wiki_interest.domain.models import (
    ArticleRole,
    BundleStatus,
    ResolutionSource,
    SubstituteKind,
    WikiProject,
)
from wiki_interest.errors import ClarificationNeededError, TopicNotFoundError

UK = WikiProject("uk")
CS = WikiProject("cs")
PL = WikiProject("pl")


def _world() -> tuple[FakeWikidata, FakeMediaWiki]:
    """Astronomy exists in uk and cs; telescope and science are other items; pl has no article."""
    wikidata = FakeWikidata(
        [
            FakeEntity(
                "Q333",
                {"en": "astronomy", "uk": "астрономія", "cs": "astronomie"},
                sitelinks={UK: "Астрономія", CS: "Astronomie"},
            ),
            FakeEntity(
                "Q4213",
                {"en": "telescope", "uk": "телескоп"},
                sitelinks={UK: "Телескоп", CS: "Dalekohled"},
            ),
            FakeEntity("Q336", {"en": "science"}, sitelinks={UK: "Наука", CS: "Věda"}),
            FakeEntity("Q999", {"en": "astrology"}, sitelinks={UK: "Астрологія"}),
        ]
    )
    mediawiki = FakeMediaWiki()
    mediawiki.add_page(
        UK, FakePage("Астрономія", qid="Q333", redirects=["Astronomy", "Астрономічна наука"])
    )
    mediawiki.add_page(UK, FakePage("Телескоп", qid="Q4213"))
    mediawiki.add_page(UK, FakePage("Астрологія", qid="Q999"))
    mediawiki.add_page(UK, FakePage("Наука", qid="Q336"))
    mediawiki.add_page(UK, FakePage("Зоря", qid=None))
    mediawiki.add_page(CS, FakePage("Astronomie", qid="Q333"))
    mediawiki.add_page(CS, FakePage("Dalekohled", qid="Q4213"))
    mediawiki.add_page(CS, FakePage("Věda", qid="Q336"))
    return wikidata, mediawiki


def _topic(**overrides: object) -> TopicSpec:
    data: dict[str, object] = {"query": "astronomy", "query_language": "en", "id": "astronomy"}
    data.update(overrides)
    return TopicSpec.model_validate(data)


class TestEntityChoice:
    def test_single_exact_match_is_chosen(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK])
        assert resolved.qid == "Q333"
        assert resolved.label == "astronomy"

    def test_pinned_qid_skips_search(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(qid="Q4213"), [UK])
        assert resolved.qid == "Q4213"
        assert resolved.label == "telescope"
        assert not [c for c in wikidata.calls if c[0] == "search_entities"]

    def test_only_fuzzy_matches_require_clarification(self) -> None:
        wikidata, mediawiki = _world()
        with pytest.raises(ClarificationNeededError) as excinfo:
            TopicResolver(wikidata, mediawiki).resolve(_topic(query="astro"), [UK])
        assert excinfo.value.exit_code == 3
        assert excinfo.value.topic_id == "astronomy"
        assert {c.qid for c in excinfo.value.candidates} >= {"Q333", "Q999"}

    def test_stated_meaning_is_never_overruled_by_article_coverage(self) -> None:
        wikidata, mediawiki = _world()
        # The band has no article in the requested editions; the user may still mean it.
        wikidata.add(FakeEntity("Q1", {"en": "astronomy"}, description="a band"))
        topic = _topic(meaning="the rock band")
        with pytest.raises(ClarificationNeededError) as excinfo:
            TopicResolver(wikidata, mediawiki).resolve(topic, [UK, CS])
        assert {c.qid for c in excinfo.value.candidates} == {"Q333", "Q1"}
        assert excinfo.value.coverage == {
            "Q333": ("uk.wikipedia", "cs.wikipedia"),
            "Q1": (),
        }

    def test_stated_meaning_picks_the_matching_homonym_without_asking(self) -> None:
        wikidata, mediawiki = _world()
        wikidata.add(
            FakeEntity(
                "Q718",
                {"en": "chess", "uk": "шахи"},
                sitelinks={UK: "Шахи", CS: "Šachy"},
                description="strategy board game for two players",
            )
        )
        wikidata.add(
            FakeEntity(
                "Q843284",
                {"en": "Chess", "uk": "Шахи"},
                sitelinks={UK: "Шахи (мюзикл)"},
                description="musical by Benny Andersson and Björn Ulvaeus",
            )
        )
        topic = _topic(query="chess", meaning="the board game of chess")
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK, CS])
        assert (resolved.qid, resolved.method, resolved.runner_up) == ("Q718", "auto", "Q843284")
        assert resolved.confidence is not None
        assert resolved.confidence >= 0.7

    def test_close_candidates_are_still_asked_about(self) -> None:
        wikidata, mediawiki = _world()
        for qid, what in (("Q1", "planet"), ("Q2", "planet")):
            wikidata.add(FakeEntity(qid, {"en": "mercury"}, sitelinks={UK: qid}, description=what))
        topic = _topic(query="mercury", meaning="the planet")
        with pytest.raises(ClarificationNeededError):
            TopicResolver(wikidata, mediawiki).resolve(topic, [UK])

    def test_without_meaning_equal_homonyms_are_asked_about(self) -> None:
        wikidata, mediawiki = _world()
        for qid in ("Q1", "Q2"):
            wikidata.add(FakeEntity(qid, {"en": "mercury"}, sitelinks={UK: qid, CS: qid}))
        with pytest.raises(ClarificationNeededError):
            TopicResolver(wikidata, mediawiki).resolve(_topic(query="mercury"), [UK, CS])

    def test_resolution_method_is_recorded(self) -> None:
        wikidata, mediawiki = _world()
        resolver = TopicResolver(wikidata, mediawiki)
        assert resolver.resolve(_topic(), [UK]).method == "unique"
        assert resolver.resolve(_topic(qid="Q4213"), [UK]).method == "pinned"

    def test_without_meaning_the_covered_homonym_is_the_default_and_the_rest_are_listed(
        self,
    ) -> None:
        wikidata, mediawiki = _world()
        wikidata.add(FakeEntity("Q1", {"en": "astronomy"}, description="a band"))
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK])
        assert resolved.qid == "Q333"
        assert resolved.method == "default"
        assert [c.qid for c in resolved.alternatives] == ["Q1"]

    def test_default_needs_coverage_and_ranking_to_agree(self) -> None:
        wikidata, mediawiki = _world()
        # Q1 sorts first but covers fewer editions than Q333: the signals disagree.
        wikidata.add(FakeEntity("Q1", {"en": "astronomy"}, sitelinks={UK: "Астро (гурт)"}))
        with pytest.raises(ClarificationNeededError):
            TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK, CS])

    def test_default_follows_the_requested_editions(self) -> None:
        wikidata, mediawiki = _world()
        wikidata.add(
            FakeEntity("Q1", {"en": "astronomy"}, sitelinks={UK: "Астро (гурт)", CS: "Astro"})
        )
        wikidata.entities["Q333"].sitelinks = {UK: "Астрономія"}
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK, CS])
        assert resolved.qid == "Q1"
        assert [c.qid for c in resolved.alternatives] == ["Q333"]

    def test_single_match_carries_its_description_and_the_other_meanings(self) -> None:
        wikidata, mediawiki = _world()
        wikidata.entities["Q333"].description = "natural science"
        wikidata.add(FakeEntity("Q7", {"en": "astronomy club"}, description="a club"))
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK])
        assert (resolved.qid, resolved.description) == ("Q333", "natural science")
        assert [c.qid for c in resolved.alternatives] == ["Q7"]

    def test_pinned_qid_carries_its_description(self) -> None:
        wikidata, mediawiki = _world()
        wikidata.entities["Q4213"].description = "optical instrument"
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(qid="Q4213"), [UK])
        assert resolved.description == "optical instrument"

    def test_nothing_found_is_reported_not_analysed(self) -> None:
        wikidata, mediawiki = _world()
        with pytest.raises(TopicNotFoundError) as excinfo:
            TopicResolver(wikidata, mediawiki).resolve(_topic(query="zzz"), [UK, CS])
        assert (excinfo.value.exit_code, excinfo.value.query) == (3, "zzz")

    def test_a_chosen_substitute_keeps_an_unknown_topic_alive(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="zzz", substitutes={"uk": {"title": "Зоря", "kind": "mention"}})
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK])
        main = resolved.bundle_for(UK).main
        assert main is not None
        assert main.title == "Зоря"

    def test_a_skipped_edition_is_a_decision_not_a_missing_topic(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="zzz", substitutes={"uk": "skip"})
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK])
        assert resolved.bundle_for(UK).status is BundleStatus.NOT_FOUND


class TestArticleLink:
    def test_linked_article_supplies_the_entity(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(
            query="zzz",
            article_url="https://uk.m.wikipedia.org/wiki/%D0%A2%D0%B5%D0%BB%D0%B5%D1%81%D0%BA%D0%BE%D0%BF",
        )
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK, CS])
        assert resolved.qid == "Q4213"
        cs_main = resolved.bundle_for(CS).main
        assert cs_main is not None
        assert cs_main.title == "Dalekohled"
        assert not [c for c in wikidata.calls if c[0] == "search_entities"]

    def test_linked_article_without_item_is_measured_on_its_own(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="zzz", article_url="https://uk.wikipedia.org/wiki/Зоря")
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK])
        main = resolved.bundle_for(UK).main
        assert main is not None
        assert (main.title, main.source) == ("Зоря", ResolutionSource.MANUAL)

    def test_broken_link_is_reported(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(article_url="https://uk.wikipedia.org/wiki/Nope")
        with pytest.raises(TopicNotFoundError):
            TopicResolver(wikidata, mediawiki).resolve(topic, [UK])


class TestMainArticle:
    def test_sitelink_is_the_only_article_and_carries_its_redirects(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK, CS])
        uk = resolved.bundle_for(UK)
        assert uk.status is BundleStatus.FOUND
        (article,) = uk.articles
        assert article is uk.main
        assert (article.title, article.role, article.source) == (
            "Астрономія",
            ArticleRole.MAIN,
            ResolutionSource.SITELINK,
        )
        assert article.redirects == ("Astronomy", "Астрономічна наука")
        assert [a.title for a in resolved.bundle_for(CS).articles] == ["Astronomie"]
        assert resolved.missing_titles == ()

    def test_missing_edition_falls_back_to_search_by_local_label(self) -> None:
        wikidata, mediawiki = _world()
        wikidata.entities["Q333"].labels["pl"] = "astronomia"
        mediawiki.add_page(PL, FakePage("Astronomia", qid="Q333"))
        mediawiki.add_search(PL, "astronomia", ["Astronomia"])
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [PL])
        bundle = resolved.bundle_for(PL)
        assert bundle.status is BundleStatus.FOUND_VIA_SEARCH
        assert bundle.main is not None
        assert bundle.main.source is ResolutionSource.SEARCH_FALLBACK
        assert bundle.main.title == "Astronomia"

    def test_wikipedia_style_qualifier_is_dropped_when_the_search_finds_nothing(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(
            _topic(query="astronomy (science)"), [UK]
        )
        assert resolved.qid == "Q333"
        queries = [c[1][0] for c in wikidata.calls if c[0] == "search_entities"]
        assert queries[:2] == ["astronomy (science)", "astronomy"]

    def test_search_fallback_tries_raw_query_when_label_finds_nothing(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.add_page(PL, FakePage("Astronomy (pl)", qid=None))
        mediawiki.add_search(PL, "astronomy", ["Astronomy (pl)"])
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [PL])
        assert resolved.bundle_for(PL).status is BundleStatus.FOUND_VIA_SEARCH

    def test_search_hit_bound_to_another_item_is_rejected(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.add_page(PL, FakePage("Stres oksydacyjny", qid="Q12345"))
        mediawiki.add_page(PL, FakePage("Astronomia", qid="Q333"))
        mediawiki.add_search(PL, "astronomy", ["Stres oksydacyjny", "Astronomia"])
        bundle = TopicResolver(wikidata, mediawiki).resolve(_topic(), [PL]).bundle_for(PL)
        assert bundle.main is not None
        assert bundle.main.title == "Astronomia"

    def test_only_foreign_search_hits_mean_no_article(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.add_page(PL, FakePage("Stres oksydacyjny", qid="Q12345"))
        mediawiki.add_search(PL, "astronomy", ["Stres oksydacyjny"])
        bundle = TopicResolver(wikidata, mediawiki).resolve(_topic(), [PL, UK]).bundle_for(PL)
        # The article exists in another edition, but nothing stands in for it here unasked.
        assert bundle.status is BundleStatus.NOT_FOUND
        assert bundle.articles == ()

    def test_no_article_anywhere_is_not_found(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [PL])
        assert resolved.bundle_for(PL).status is BundleStatus.NOT_FOUND
        assert resolved.bundle_for(PL).articles == ()

    def test_redirects_are_capped(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.pages[UK]["Астрономія"].redirects = [f"R{i}" for i in range(50)]
        settings = ResolutionSettings(max_redirects_per_article=3)
        resolved = TopicResolver(wikidata, mediawiki, settings=settings).resolve(_topic(), [UK])
        main = resolved.bundle_for(UK).main
        assert main is not None
        assert main.redirects == ("R0", "R1", "R2")


def test_resolve_request_handles_every_topic_in_order() -> None:
    wikidata, mediawiki = _world()
    request = AnalysisRequest.model_validate(
        {
            "question_type": "compare",
            "topics": [{"query": "astronomy"}, {"query": "telescope"}],
            "projects": ["uk", "cs"],
        }
    )
    resolved = TopicResolver(wikidata, mediawiki).resolve_request(request)
    assert [r.topic_id for r in resolved] == ["astronomy", "telescope"]
    assert [b.project for b in resolved[1].bundles] == [UK, CS]


def test_topic_without_id_is_rejected() -> None:
    wikidata, mediawiki = _world()
    with pytest.raises(ValueError, match="id"):
        TopicResolver(wikidata, mediawiki).resolve(TopicSpec(query="x"), [UK])


class TestSubstitutes:
    def test_broader_substitute_is_the_only_article_with_its_own_redirects(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.add_page(PL, FakePage("Nauka", qid="Q336", redirects=["Nauki"]))
        topic = _topic(substitutes={"pl": {"title": "nauka", "kind": "broader"}})
        mediawiki.pages[PL]["nauka"] = mediawiki.pages[PL]["Nauka"]  # a spelling the API accepts
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [PL, UK]).bundle_for(PL)
        assert bundle.status is BundleStatus.SUBSTITUTE
        assert bundle.substitute_kind is SubstituteKind.BROADER
        (article,) = bundle.articles
        assert (article.title, article.role, article.source) == (
            "Nauka",
            ArticleRole.MAIN,
            ResolutionSource.SUBSTITUTE,
        )
        assert article.redirects == ("Nauki",)

    def test_redirect_substitute_is_measured_under_its_own_title(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.add_page(PL, FakePage("Nauka", qid="Q336", redirects=["Astronomia"]))
        topic = _topic(substitutes={"pl": {"title": "Astronomia", "kind": "redirect"}})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [PL]).bundle_for(PL)
        assert bundle.substitute_kind is SubstituteKind.REDIRECT
        (article,) = bundle.articles
        assert (article.title, article.qid, article.redirects) == ("Astronomia", None, ())

    def test_skip_leaves_the_edition_empty_without_searching(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.add_page(PL, FakePage("Astronomy (pl)", qid=None))
        mediawiki.add_search(PL, "astronomy", ["Astronomy (pl)"])
        topic = _topic(substitutes={"pl": "skip"})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [PL]).bundle_for(PL)
        assert bundle.status is BundleStatus.NOT_FOUND
        assert not any(name == "search" for name, _ in mediawiki.calls)

    def test_missing_substitute_is_reported_not_guessed(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(substitutes={"pl": {"title": "Nope", "kind": "mention"}})
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [PL])
        assert resolved.bundle_for(PL).status is BundleStatus.NOT_FOUND
        assert resolved.missing_titles == ((PL, "Nope"),)

    def test_an_existing_article_wins_over_a_stale_substitute(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(substitutes={"uk": {"title": "Наука", "kind": "broader"}})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [UK]).bundle_for(UK)
        assert bundle.status is BundleStatus.FOUND
        assert bundle.main is not None
        assert bundle.main.title == "Астрономія"


class TestEnglishFallbackAndLocalTerms:
    def test_english_wording_is_used_only_when_the_query_finds_nothing(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="astronomia", query_language="pl", query_en="astronomy")
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK])
        assert (resolved.qid, resolved.matched_in_english) == ("Q333", True)
        searches = [args for name, args in wikidata.calls if name == "search_entities"]
        assert [(q, lang) for q, lang, _ in searches] == [("astronomia", "pl"), ("astronomy", "en")]

    def test_label_prefers_the_query_language_after_an_english_match(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="астрономия", query_language="uk", query_en="astronomy")
        wikidata.entities["Q333"].labels["uk"] = "Астрономія"
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK])
        assert resolved.label == "Астрономія"

    def test_english_wording_is_not_used_when_the_query_matches(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="астрономія", query_language="uk", query_en="astrology")
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK])
        assert (resolved.qid, resolved.matched_in_english) == ("Q333", False)

    def test_vague_english_wording_still_asks(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="gwiazdy", query_language="pl", query_en="astro")
        with pytest.raises(ClarificationNeededError):
            TopicResolver(wikidata, mediawiki).resolve(topic, [UK])

    def test_local_term_is_searched_first(self) -> None:
        wikidata, mediawiki = _world()
        mediawiki.add_page(PL, FakePage("Astronomia", qid=None))
        mediawiki.add_search(PL, "astronomia", ["Astronomia"])
        topic = _topic(local_terms={"pl": "astronomia"})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [PL]).bundle_for(PL)
        assert bundle.main is not None
        assert bundle.main.title == "Astronomia"
        first_search = next(args for name, args in mediawiki.calls if name == "search")
        assert first_search[1] == "astronomia"
