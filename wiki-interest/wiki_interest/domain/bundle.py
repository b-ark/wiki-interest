"""Selection of related concepts for a topic bundle.

A topic is a set of articles, not one page: "astronomy" in uk-wiki is ``Астрономія`` plus
telescopes, planets and so on. The candidates come from two signals the adapters collect,
Wikidata relations (subclass, part of, has part, facet of) and links from the lead section
of the main article in each requested edition. This module turns those raw lists into a
weighted, deterministic, capped list of Wikidata ids; resolving ids to titles per edition is
the resolver's job.

Consensus across editions is the key idea: a concept is only weighted like a Wikidata
relation when at least half of the editions introduce the topic with it. Bundles built this
way have the same composition in every edition, so a comparison between editions measures
interest, not differences in how each community wrote its lead paragraph.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, replace

from wiki_interest.domain.models import ResolutionSource, WikiProject

__all__ = ["BundleSettings", "RelatedConcept", "rank_related_concepts"]


@dataclass(frozen=True, slots=True)
class RelatedConcept:
    """A candidate related article, identified by Wikidata id.

    Attributes:
        qid: Wikidata item id.
        weight: Relevance weight to use in the bundle sum (the main article is 1.0).
        source: Which signal justified the weight.
        support: Number of independent signals that mention the concept: one per edition
            whose lead links to it, plus one when a Wikidata relation does.
    """

    qid: str
    weight: float
    source: ResolutionSource
    support: int


@dataclass(frozen=True, slots=True)
class BundleSettings:
    """Weights and size limit for automatic bundles (technical plan, section 7.1).

    Attributes:
        max_related: Cap on related concepts per topic; keeps API traffic and the report
            readable.
        wikidata_weight: Weight of a concept linked through a Wikidata relation.
        consensus_lead_weight: Weight of a concept linked from the lead in at least half of
            the editions; it is as trustworthy as a curated relation.
        single_lead_weight: Weight of a concept linked from at least one lead.
        max_total_related_weight: Upper bound on the summed weights of all related concepts.
            Without it fifteen related articles at 0.5 each outweigh the main article 7.5 to
            1, so a broad neighbour ("Chemistry" in an astronomy lead) could drive the trend.
            When the sum exceeds the bound, every weight is scaled by the same factor, which
            keeps their relative order and caps the related share of the bundle at one half
            with the default of 1.0.
    """

    max_related: int = 15
    wikidata_weight: float = 0.5
    consensus_lead_weight: float = 0.5
    single_lead_weight: float = 0.3
    max_total_related_weight: float = 1.0


_DEFAULT_SETTINGS = BundleSettings()


def rank_related_concepts(
    main_qid: str,
    lead_link_qids_by_project: Mapping[WikiProject, Sequence[str]],
    wikidata_related: Mapping[str, Sequence[str]],
    *,
    excluded: Collection[str] = (),
    settings: BundleSettings = _DEFAULT_SETTINGS,
) -> tuple[RelatedConcept, ...]:
    """Weight, order and cap the related concepts of a topic.

    Weights: ``wikidata_weight`` for a concept present in any ``wikidata_related`` property
    (source ``WIKIDATA_RELATION``); otherwise ``consensus_lead_weight`` when the concept is in
    the lead links of at least ``ceil(n / 2)`` of the ``n`` editions, else
    ``single_lead_weight`` (source ``LEAD_LINK``). The main article and ``excluded`` ids never
    appear. Order is weight descending, support descending, id ascending, so the same inputs
    always give the same bundle and a cached run reproduces exactly.

    Args:
        main_qid: Id of the topic itself.
        lead_link_qids_by_project: Ids of the articles linked from the lead of the main
            article, per edition. Editions without a main article are simply absent.
        wikidata_related: ``{property: ids}`` as returned by the Wikidata gateway.
        excluded: Ids the user removed in a follow-up request.
        settings: Weights and cap.

    Returns:
        At most ``settings.max_related`` concepts, best first, with weights scaled down so
        that they sum to at most ``settings.max_total_related_weight``.
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
    concepts.sort(key=lambda c: (-c.weight, -c.support, c.qid))
    return _scaled(concepts[: settings.max_related], settings.max_total_related_weight)


def _scaled(concepts: list[RelatedConcept], max_total: float) -> tuple[RelatedConcept, ...]:
    """Scale weights down proportionally so that their sum does not exceed ``max_total``."""
    total = sum(c.weight for c in concepts)
    if total <= max_total:
        return tuple(concepts)
    factor = max_total / total
    return tuple(replace(c, weight=c.weight * factor) for c in concepts)


def _concept(
    qid: str, in_wikidata: bool, leads: int, consensus: int, settings: BundleSettings
) -> RelatedConcept:
    """Assign weight and source to one candidate from its signals."""
    support = leads + int(in_wikidata)
    if in_wikidata:
        return RelatedConcept(
            qid, settings.wikidata_weight, ResolutionSource.WIKIDATA_RELATION, support
        )
    if leads >= consensus:
        return RelatedConcept(
            qid, settings.consensus_lead_weight, ResolutionSource.LEAD_LINK, support
        )
    return RelatedConcept(qid, settings.single_lead_weight, ResolutionSource.LEAD_LINK, support)
