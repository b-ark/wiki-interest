"""Wikidata adapter against recorded ``wb*`` responses."""

from wiki_interest.domain.models import EntityCandidate

from .conftest import Replay
from .record_fixtures import CS, PL, UK


def test_search_finds_intermittent_fasting_as_exact_label_match(replay: Replay) -> None:
    found = replay("wikidata-search-intermittent-fasting-en")
    assert found
    first = found[0]
    assert isinstance(first, EntityCandidate)
    assert first.qid == "Q1666254"
    assert first.label.casefold() == "intermittent fasting"
    assert first.exact_label_match is True
    assert first.description
    assert sum(c.exact_label_match for c in found) == 1, "only one clear winner"


def test_sitelinks_give_uk_and_cs_titles_but_no_pl(replay: Replay) -> None:
    result = replay("wikidata-sitelinks-q1666254")
    assert set(result) == {"Q1666254"}, "missing and impossible ids are absent"
    links = result["Q1666254"]
    assert links[UK] == "Інтервальне голодування"
    assert links[CS] == "Přerušovaný půst"
    assert PL not in links, "pl.wikipedia has no article linked to Q1666254 (verified 2026-09-22)"


def test_labels_prefer_ukrainian(replay: Replay) -> None:
    result = replay("wikidata-labels-q1666254-uk")
    # Wikidata labels of common nouns are lowercase, unlike Wikipedia titles.
    assert result == {"Q1666254": "Інтервальне голодування", "Q333": "астрономія"}


def test_related_entities_reads_subclass_claims(replay: Replay) -> None:
    result = replay("wikidata-claims-q333")
    assert set(result) == {"P279", "P361"}
    assert "Q14632398" in result["P279"], "astronomy is a subclass of natural science"
    assert all(qid.startswith("Q") for targets in result.values() for qid in targets)
