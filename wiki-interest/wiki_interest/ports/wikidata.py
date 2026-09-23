"""Port: Wikidata lookups used to resolve topics across language editions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from wiki_interest.domain.models import EntityCandidate, WikiProject

__all__ = ["EntitySummary", "WikidataGateway"]


@dataclass(frozen=True, slots=True)
class EntitySummary:
    """What an item is and where Wikipedia covers it, for showing the user.

    Attributes:
        qid: Item id.
        label: Label in the requested language, else English, else ``None``.
        description: Short description in the same language fallback order.
        languages: Language codes of every Wikipedia edition with an article on the item
            (``"en"``, ``"be-tarask"``), in Wikidata's order.
    """

    qid: str
    label: str | None
    description: str | None
    languages: tuple[str, ...]


class WikidataGateway(Protocol):
    """Read-only access to Wikidata entities.

    Wikidata is the bridge between a topic phrased in one language and article titles in
    others: search finds the entity, sitelinks give the title per edition, claims give
    broader entities to offer when an edition has no article.
    """

    def search_entities(
        self, query: str, language: str, *, limit: int = 5
    ) -> Sequence[EntityCandidate]:
        """Find entities whose label or alias matches ``query`` in ``language``.

        Args:
            query: Free-text topic as the user wrote it.
            language: Language code of the query text.
            limit: Maximum number of candidates, best match first.

        Returns:
            Candidates in ranking order; empty when nothing matches.
        """
        ...

    def sitelinks(
        self, qids: Sequence[str], projects: Sequence[WikiProject]
    ) -> Mapping[str, Mapping[WikiProject, str]]:
        """Return article titles for entities in the given editions.

        Args:
            qids: Entity ids such as ``"Q333"``. Implementations batch as needed.
            projects: Editions to look up.

        Returns:
            ``{qid: {project: title}}``. Entities or editions without an article are simply
            absent from the inner mapping; unknown ids are absent from the outer mapping.
        """
        ...

    def labels(
        self, qids: Sequence[str], language: str, *, fallback: bool = True
    ) -> Mapping[str, str]:
        """Return human-readable labels, falling back to English when ``language`` has none.

        Args:
            qids: Entity ids.
            language: Wanted label language.
            fallback: Whether an English label may stand in. Pass ``False`` when the label is
                used to search text in ``language``: an English phrase in a Polish article
                is usually a bibliography entry, not a mention of the topic.

        Returns:
            ``{qid: label}``; ids with no usable label are absent.
        """
        ...

    def summary(self, qid: str, language: str) -> EntitySummary | None:
        """Label, description and Wikipedia coverage of one item; ``None`` if it is unknown.

        Used when an edition has no article: the user sees which entity the topic resolved
        to and in which languages it *is* covered before deciding what to do.
        """
        ...

    def summaries(self, qids: Sequence[str], language: str) -> Mapping[str, EntitySummary]:
        """:meth:`summary` for several items in one request; unknown ids are absent.

        Used to compare homonyms: the English label and description of each candidate are
        matched against the meaning the agent stated, and the number of Wikipedias covering
        it hints at the primary sense of the word.
        """
        ...

    def related_entities(
        self, qid: str, properties: Sequence[str]
    ) -> Mapping[str, tuple[str, ...]]:
        """Return entities linked from ``qid`` through the given properties.

        Args:
            qid: Source entity.
            properties: Property ids such as ``"P527"`` (has part). Only forward claims are
                read; reverse lookups need the query service and are out of scope.

        Returns:
            ``{property: (qid, ...)}`` in statement order, with every requested property
            present (possibly empty).
        """
        ...
