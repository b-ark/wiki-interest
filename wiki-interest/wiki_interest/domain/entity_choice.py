"""Choosing among Wikidata homonyms when the agent stated what the user means.

A word such as "шахматы" or "Mercury" matches several Wikidata items. When the request says
what the user means ("the board game of chess", "the chemical element Hg"), the item whose
English label and description match that meaning is almost always the right one; the data
only confirm it (an article in every requested edition, many Wikipedias covering it). This
module scores the candidates by those signals and says whether the leader is clear enough to
pick without asking.

The score is deliberately simple and explainable: a weighted sum of four signals in
``[0, 1]`` with penalties for pages that are not topics (disambiguation pages, lists,
categories) and for items no Wikipedia covers. Meaning must match: a leader whose
description shares nothing with the stated meaning is never picked, however popular.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "CandidateEvidence",
    "ChoiceSettings",
    "ScoredCandidate",
    "choose_by_meaning",
    "meaning_match",
]

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_STOPWORDS = frozenset(
    {
        "a", "an", "and", "as", "at", "by", "for", "from", "in", "into", "is", "its", "of",
        "on", "or", "our", "the", "their", "this", "to", "with", "about", "user", "users",
        "meaning", "sense", "topic", "not",
    }
)  # fmt: skip
_STEM = 5
"""Words are compared by their first letters, so "elements" matches "element"."""
_NOT_A_TOPIC = (
    "disambiguation",
    "wikimedia list",
    "wikimedia category",
    "wikimedia template",
    "family name",
    "given name",
)
"""Description fragments of items that are pages about names, not topics."""


@dataclass(frozen=True, slots=True)
class CandidateEvidence:
    """What is known about one candidate item.

    Attributes:
        qid: Item id.
        rank: Position in the Wikidata search results, from 0.
        label_en: English label, if any.
        description_en: English description, if any.
        wikipedias: Number of Wikipedia editions with an article on the item.
        covered: Number of requested editions with an article on the item.
        requested: Number of requested editions.
    """

    qid: str
    rank: int
    label_en: str | None
    description_en: str | None
    wikipedias: int
    covered: int
    requested: int


@dataclass(frozen=True, slots=True)
class ChoiceSettings:
    """Weights and thresholds of the automatic choice; documented in the methodology.

    Attributes:
        meaning_weight: Weight of the meaning match, the decisive signal.
        coverage_weight: Weight of having an article in the requested editions.
        popularity_weight: Weight of the number of Wikipedias covering the item, a proxy for
            the primary sense of the word.
        rank_weight: Weight of Wikidata's own search ranking.
        min_meaning: Smallest meaning match the leader needs to be picked.
        min_margin: Smallest score lead over the runner-up to pick without asking.
        not_a_topic_factor: Score multiplier for disambiguation pages, lists and the like.
        uncovered_factor: Score multiplier for items no Wikipedia covers.
    """

    meaning_weight: float = 0.5
    coverage_weight: float = 0.25
    popularity_weight: float = 0.15
    rank_weight: float = 0.1
    min_meaning: float = 0.5
    min_margin: float = 0.15
    not_a_topic_factor: float = 0.1
    uncovered_factor: float = 0.2


@dataclass(frozen=True, slots=True)
class ScoredCandidate:
    """A candidate with its total score and meaning match, best first."""

    qid: str
    score: float
    meaning: float


def meaning_match(meaning: str, label: str | None, description: str | None) -> float:
    """Share of the meaning's content words found in the label or description, in [0, 1]."""
    wanted = _stems(meaning)
    if not wanted:
        return 0.0
    found = _stems(f"{label or ''} {description or ''}")
    return len(wanted & found) / len(wanted)


def choose_by_meaning(
    meaning: str,
    candidates: Sequence[CandidateEvidence],
    settings: ChoiceSettings | None = None,
) -> tuple[ScoredCandidate | None, list[ScoredCandidate]]:
    """Score every candidate; return the one to pick (or ``None``) and the full ranking.

    The leader is picked when its meaning match is at least ``min_meaning`` and its score
    leads the runner-up by ``min_margin``; otherwise the caller asks the user.
    """
    rules = settings or ChoiceSettings()
    if not candidates:
        return None, []
    most = max(c.wikipedias for c in candidates)
    ranked = sorted(
        (_score(meaning, c, most, len(candidates), rules) for c in candidates),
        key=lambda s: -s.score,
    )
    leader = ranked[0]
    runner_up = ranked[1].score if len(ranked) > 1 else 0.0
    clear = leader.meaning >= rules.min_meaning and leader.score - runner_up >= rules.min_margin
    return (leader if clear else None), ranked


def _score(
    meaning: str, item: CandidateEvidence, most: int, count: int, rules: ChoiceSettings
) -> ScoredCandidate:
    match = meaning_match(meaning, item.label_en, item.description_en)
    coverage = item.covered / item.requested if item.requested else 0.0
    popularity = math.log1p(item.wikipedias) / math.log1p(most) if most > 0 else 0.0
    rank = 1.0 - item.rank / count if count > 1 else 1.0
    score = (
        rules.meaning_weight * match
        + rules.coverage_weight * coverage
        + rules.popularity_weight * popularity
        + rules.rank_weight * rank
    )
    description = (item.description_en or "").lower()
    if any(fragment in description for fragment in _NOT_A_TOPIC):
        score *= rules.not_a_topic_factor
    if item.wikipedias == 0:
        score *= rules.uncovered_factor
    return ScoredCandidate(item.qid, round(score, 4), round(match, 4))


def _stems(text: str) -> set[str]:
    words = (w.lower() for w in _WORD.findall(text))
    return {w[:_STEM] for w in words if w not in _STOPWORDS and len(w) > 1}
