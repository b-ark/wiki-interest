"""Selection of related concepts reported next to a topic.

Readers of "astronomy" in uk-wiki also read about telescopes and planets; the report names
those neighbouring articles with their own views as context. They are never added into the
topic's numbers: which neighbours an edition has differs between editions, so a sum would
compare article sets rather than interest.

The candidates come from two signals the adapters collect, Wikidata relations (subclass,
part of, has part, facet of) and links from the lead section of the main article in each
requested edition. This module turns those raw lists into a deterministic, capped list of
Wikidata ids ordered by relevance; resolving ids to titles per edition is the resolver's job.
A concept linked from the leads of at least half of the editions counts as much as a
Wikidata relation; one linked from a single lead ranks lower.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from wiki_interest.domain.models import ResolutionSource, WikiProject

__all__ = ["BundleSettings", "RelatedConcept", "rank_related_concepts"]


@dataclass(frozen=True, slots=True)
class RelatedConcept:
    """A candidate related article, identified by Wikidata id.

    Attributes:
        qid: Wikidata item id.
        relevance: How strongly the signals tie the concept to the topic; orders the list.
        source: Which signal justified the relevance.
        support: Number of independent signals that mention the concept: one per edition
            whose lead links to it, plus one when a Wikidata relation does.
    """

    qid: str
    relevance: float
    source: ResolutionSource
    support: int


@dataclass(frozen=True, slots=True)
class BundleSettings:
    """Relevance scores and size limit for related concepts.

    Attributes:
        max_related: Cap on related concepts per topic; each costs one pageview request per
            edition.
        wikidata_relevance: Relevance of a concept linked through a Wikidata relation.
        consensus_lead_relevance: Relevance of a concept linked from the lead in at least half
            of the editions; it is as trustworthy as a curated relation.
        single_lead_relevance: Relevance of a concept linked from at least one lead.
    """

    max_related: int = 15
    wikidata_relevance: float = 0.5
    consensus_lead_relevance: float = 0.5
    single_lead_relevance: float = 0.3


_DEFAULT_SETTINGS = BundleSettings()


def rank_related_concepts(
    main_qid: str,
    lead_link_qids_by_project: Mapping[WikiProject, Sequence[str]],
    wikidata_related: Mapping[str, Sequence[str]],
    *,
    excluded: Collection[str] = (),
    settings: BundleSettings = _DEFAULT_SETTINGS,
) -> tuple[RelatedConcept, ...]:
    """Score, order and cap the related concepts of a topic.

    Relevance: ``wikidata_relevance`` for a concept present in any ``wikidata_related``
    property (source ``WIKIDATA_RELATION``); otherwise ``consensus_lead_relevance`` when the
    concept is in the lead links of at least ``ceil(n / 2)`` of the ``n`` editions, else
    ``single_lead_relevance`` (source ``LEAD_LINK``). The main article and ``excluded`` ids
    never appear. Order is relevance descending, support descending, id ascending, so the same
    inputs always give the same list and a cached run reproduces exactly.

    Args:
        main_qid: Id of the topic itself.
        lead_link_qids_by_project: Ids of the articles linked from the lead of the main
            article, per edition. Editions without a main article are simply absent.
        wikidata_related: ``{property: ids}`` as returned by the Wikidata gateway.
        excluded: Ids the user removed in a follow-up request.
        settings: Weights and cap.

    Returns:
        At most ``settings.max_related`` concepts, best first.
    """
    banned = {main_qid, *excluded}
    lead_support = Counter(
        qid for links in lead_link_qids_by_project.values() for qid in set(links)
    )
    wikidata_ids = {qid for ids in wikidata_related.values() for qid in ids}
    consensus = math.ceil(len(lead_link_qids_by_project) / 2)
    concepts = [
        _concept(qid, qid in wikidata_ids, lead_support[qid], consensus, settings)
        for qid in (wikidata_ids | set(lead_support)) - banned
    ]
    concepts.sort(key=lambda c: (-c.relevance, -c.support, c.qid))
    return tuple(concepts[: settings.max_related])


def _concept(
    qid: str, in_wikidata: bool, leads: int, consensus: int, settings: BundleSettings
) -> RelatedConcept:
    """Assign relevance and source to one candidate from its signals."""
    support = leads + int(in_wikidata)
    if in_wikidata:
        return RelatedConcept(
            qid, settings.wikidata_relevance, ResolutionSource.WIKIDATA_RELATION, support
        )
    if leads >= consensus:
        return RelatedConcept(
            qid, settings.consensus_lead_relevance, ResolutionSource.LEAD_LINK, support
        )
    return RelatedConcept(qid, settings.single_lead_relevance, ResolutionSource.LEAD_LINK, support)
