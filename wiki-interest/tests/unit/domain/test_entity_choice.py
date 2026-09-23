"""Scoring Wikidata homonyms against the meaning the agent stated."""

from __future__ import annotations

import pytest

from wiki_interest.domain.entity_choice import (
    CandidateEvidence,
    ChoiceSettings,
    choose_by_meaning,
    meaning_match,
)


def _item(
    qid: str,
    description: str | None,
    *,
    rank: int = 0,
    wikipedias: int = 100,
    covered: int = 2,
    label: str = "chess",
) -> CandidateEvidence:
    return CandidateEvidence(qid, rank, label, description, wikipedias, covered, 2)


def test_meaning_match_ignores_filler_words_and_endings() -> None:
    assert meaning_match("the board game of chess", "chess", "strategy board game") == 1.0
    assert meaning_match("the chemical elements", "mercury", "chemical element Hg") == 1.0
    assert meaning_match("the planet", "mercury", "chemical element") == 0.0
    assert meaning_match("the of", "x", "y") == 0.0


def test_the_matching_item_is_picked_even_when_listed_second() -> None:
    picked, ranked = choose_by_meaning(
        "the board game of chess",
        [
            _item("Q843284", "musical by Benny Andersson", rank=0, wikipedias=30, covered=1),
            _item("Q718", "strategy board game", rank=1),
        ],
    )
    assert picked is not None
    assert picked.qid == "Q718"
    assert [r.qid for r in ranked] == ["Q718", "Q843284"]


def test_no_match_or_a_close_race_asks() -> None:
    unmatched, _ = choose_by_meaning("the rock band", [_item("Q1", "science"), _item("Q2", "town")])
    assert unmatched is None
    tie, _ = choose_by_meaning(
        "the planet", [_item("Q1", "planet", rank=0), _item("Q2", "planet", rank=1)]
    )
    assert tie is None
    assert choose_by_meaning("anything", []) == (None, [])


@pytest.mark.parametrize(
    "description", ["Wikimedia disambiguation page", "family name", "Wikimedia list article"]
)
def test_pages_about_names_are_not_topics(description: str) -> None:
    picked, ranked = choose_by_meaning(
        "chess board game", [_item("Q1", f"chess board game {description}"), _item("Q2", None)]
    )
    assert picked is None or picked.qid != "Q1"
    assert ranked[-1].qid == "Q1" or ranked[0].score < 0.2


def test_uncovered_items_are_penalised_and_settings_apply() -> None:
    covered = _item("Q1", "board game", wikipedias=50)
    uncovered = _item("Q2", "board game", wikipedias=0, covered=0, rank=1)
    picked, _ = choose_by_meaning("board game", [covered, uncovered])
    assert picked is not None
    assert picked.qid == "Q1"
    strict = ChoiceSettings(min_margin=0.99)
    assert choose_by_meaning("board game", [covered, uncovered], strict)[0] is None
