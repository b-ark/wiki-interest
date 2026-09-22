"""Topic resolution: entities, main articles, bundles, manual edits, redirects, clarification."""

from __future__ import annotations

import pytest

from fakes import FakeEntity, FakeMediaWiki, FakePage, FakeWikidata
from wiki_interest.application.resolution import ResolutionSettings, TopicResolver
from wiki_interest.contracts.request import AnalysisRequest, TopicSpec
from wiki_interest.domain.models import (
    ArticleRole,
    BundleStatus,
    ResolutionSource,
    WikiProject,
)
from wiki_interest.errors import ClarificationNeededError

UK = WikiProject("uk")
CS = WikiProject("cs")
PL = WikiProject("pl")


def _world() -> tuple[FakeWikidata, FakeMediaWiki]:
    """Astronomy exists in uk and cs; telescope and galaxy are related; pl has no article."""
    wikidata = FakeWikidata(
        [
            FakeEntity(
                "Q333",
                {"en": "astronomy", "uk": "астрономія", "cs": "astronomie"},
                sitelinks={UK: "Астрономія", CS: "Astronomie"},
                claims={"P279": ["Q336"], "P527": ["Q4213"]},
            ),
            FakeEntity(
                "Q4213",
                {"en": "telescope", "uk": "телескоп"},
                sitelinks={UK: "Телескоп", CS: "Dalekohled"},
            ),
            FakeEntity("Q318", {"en": "galaxy"}, sitelinks={UK: "Галактика", CS: "Galaxie"}),
            FakeEntity("Q336", {"en": "science"}, sitelinks={UK: "Наука", CS: "Věda"}),
            FakeEntity("Q999", {"en": "astrology"}, sitelinks={UK: "Астрологія"}),
        ]
    )
    mediawiki = FakeMediaWiki()
    mediawiki.add_page(
        UK,
        FakePage(
            "Астрономія",
            qid="Q333",
            redirects=["Astronomy", "Астрономічна наука"],
            lead_links=["Телескоп", "Галактика", "Астрологія"],
        ),
    )
    mediawiki.add_page(UK, FakePage("Телескоп", qid="Q4213"))
    mediawiki.add_page(UK, FakePage("Галактика", qid="Q318"))
    mediawiki.add_page(UK, FakePage("Астрологія", qid="Q999"))
    mediawiki.add_page(UK, FakePage("Наука", qid="Q336"))
    mediawiki.add_page(UK, FakePage("Зоря", qid=None))
    mediawiki.add_page(CS, FakePage("Astronomie", qid="Q333", lead_links=["Dalekohled", "Galaxie"]))
    mediawiki.add_page(CS, FakePage("Dalekohled", qid="Q4213"))
    mediawiki.add_page(CS, FakePage("Galaxie", qid="Q318"))
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

    def test_exact_homonym_without_articles_in_requested_editions_is_ignored(self) -> None:
        wikidata, mediawiki = _world()
        wikidata.add(FakeEntity("Q1", {"en": "astronomy"}, description="a band"))
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK])
        assert resolved.qid == "Q333"

    def test_exact_homonyms_with_articles_in_requested_editions_need_clarification(
        self,
    ) -> None:
        wikidata, mediawiki = _world()
        wikidata.add(FakeEntity("Q1", {"en": "astronomy"}, sitelinks={UK: "Астрономія (гурт)"}))
        with pytest.raises(ClarificationNeededError) as excinfo:
            TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK])
        assert {c.qid for c in excinfo.value.candidates} == {"Q333", "Q1"}

    def test_homonym_relevance_is_judged_against_the_requested_editions(self) -> None:
        wikidata, mediawiki = _world()
        wikidata.add(FakeEntity("Q1", {"en": "astronomy"}, sitelinks={PL: "Astronomia (zespół)"}))
        # Only the band has a Polish article, so for a Polish-only request it is the pick.
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [PL])
        assert resolved.qid == "Q1"

    def test_broader_coverage_wins_when_wikidata_also_ranks_it_first(self) -> None:
        wikidata, mediawiki = _world()
        # Q1 sorts before Q333 in the fake's ranking and covers both requested editions.
        wikidata.add(
            FakeEntity("Q1", {"en": "astronomy"}, sitelinks={UK: "Астро (гурт)", CS: "Astro"})
        )
        wikidata.entities["Q333"].sitelinks = {UK: "Астрономія"}
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK, CS])
        assert resolved.qid == "Q1"

    def test_broader_coverage_alone_does_not_override_wikidata_ranking(self) -> None:
        wikidata, mediawiki = _world()
        # Q1 is ranked first but covers fewer editions than Q333: the signals disagree.
        wikidata.add(FakeEntity("Q1", {"en": "astronomy"}, sitelinks={UK: "Астро (гурт)"}))
        with pytest.raises(ClarificationNeededError):
            TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK, CS])

    def test_no_entity_and_no_titles_gives_not_found_bundles(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(query="zzz"), [UK, CS])
        assert resolved.qid is None
        assert [b.status for b in resolved.bundles] == [BundleStatus.NOT_FOUND] * 2


class TestMainAndBundle:
    def test_auto_bundle_uses_cross_edition_consensus_and_wikidata_relations(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(), [UK, CS])
        uk = resolved.bundle_for(UK)
        assert uk.status is BundleStatus.FOUND
        assert uk.main is not None
        assert uk.main.title == "Астрономія"
        assert uk.main.source is ResolutionSource.SITELINK
        assert uk.main.redirects == ("Astronomy", "Астрономічна наука")
        by_title = {a.title: a for a in uk.articles}
        # Four related concepts at a nominal 0.5 each (telescope and science via Wikidata,
        # galaxy and astrology via lead links) are scaled so that together they weigh 1.0.
        assert by_title["Телескоп"].weight == pytest.approx(0.25)
        assert by_title["Телескоп"].source is ResolutionSource.WIKIDATA_RELATION
        assert by_title["Галактика"].weight == pytest.approx(0.25)
        related = [a for a in uk.articles if a.role is ArticleRole.RELATED]
        assert sum(a.weight for a in related) == pytest.approx(1.0)
        assert by_title["Галактика"].source is ResolutionSource.LEAD_LINK
        assert by_title["Наука"].source is ResolutionSource.WIKIDATA_RELATION
        cs_titles = {a.title for a in resolved.bundle_for(CS).articles}
        assert cs_titles == {"Astronomie", "Dalekohled", "Galaxie", "Věda"}

    def test_main_mode_keeps_only_the_main_article(self) -> None:
        wikidata, mediawiki = _world()
        resolved = TopicResolver(wikidata, mediawiki).resolve(_topic(bundle="main"), [UK])
        assert [a.role for a in resolved.bundle_for(UK).articles] == [ArticleRole.MAIN]

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
        # Related concepts exist in other editions but never stand in for a missing main one.
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


class TestManualEdits:
    def test_extra_titles_are_added_with_manual_weight_and_normalised(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(bundle="manual", extra_titles={"uk": ["Зоря", "Astronomy", "Nope"]})
        resolved = TopicResolver(wikidata, mediawiki).resolve(topic, [UK])
        bundle = resolved.bundle_for(UK)
        titles = [(a.title, a.role, a.weight) for a in bundle.articles]
        # "Astronomy" is a redirect to the main article and is therefore not duplicated.
        assert titles == [
            ("Астрономія", ArticleRole.MAIN, 1.0),
            ("Зоря", ArticleRole.MANUAL, 0.5),
        ]
        assert resolved.missing_titles == ((UK, "Nope"),)

    def test_main_mode_ignores_extra_titles(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(bundle="main", extra_titles={"uk": ["Зоря"]})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [UK]).bundle_for(UK)
        assert [a.title for a in bundle.articles] == ["Астрономія"]

    def test_manual_mode_adds_only_listed_titles(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(bundle="manual", extra_titles={"uk": ["Зоря"]})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [UK]).bundle_for(UK)
        assert [(a.title, a.role) for a in bundle.articles] == [
            ("Астрономія", ArticleRole.MAIN),
            ("Зоря", ArticleRole.MANUAL),
        ]
        assert bundle.articles[1].weight == 0.5

    def test_first_manual_title_becomes_main_when_no_entity_matches(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(query="zzz", extra_titles={"uk": ["Зоря", "Телескоп"]})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [UK]).bundle_for(UK)
        assert bundle.status is BundleStatus.FOUND
        assert bundle.main is not None
        assert bundle.main.title == "Зоря"
        assert bundle.main.weight == 1.0
        assert bundle.main.source is ResolutionSource.MANUAL

    def test_exclusions_remove_related_articles_by_any_spelling(self) -> None:
        wikidata, mediawiki = _world()
        topic = _topic(exclude_titles={"uk": ["Галактика", "Astronomy"]})
        bundle = TopicResolver(wikidata, mediawiki).resolve(topic, [UK]).bundle_for(UK)
        titles = {a.title for a in bundle.articles}
        assert "Галактика" not in titles
        # Excluding a redirect spelling of the main article removes the main article too.
        assert "Астрономія" not in titles
        assert bundle.main is not None
        assert bundle.main.role is ArticleRole.MAIN


def test_resolve_request_handles_every_topic_in_order() -> None:
    wikidata, mediawiki = _world()
    request = AnalysisRequest.model_validate(
        {
            "question_type": "compare",
            "topics": [{"query": "astronomy"}, {"query": "telescope", "bundle": "main"}],
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
