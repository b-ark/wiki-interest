"""Port: Wikidata lookups used to resolve topics across language editions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol

from wiki_interest.domain.models import EntityCandidate, WikiProject

__all__ = ["WikidataGateway"]


class WikidataGateway(Protocol):
    """Read-only access to Wikidata entities.

    Wikidata is the bridge between a topic phrased in one language and article titles in
    others: search finds the entity, sitelinks give the title per edition, claims give
    related entities for building topic bundles.
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

    def labels(self, qids: Sequence[str], language: str) -> Mapping[str, str]:
        """Return human-readable labels, falling back to English when ``language`` has none.

        Returns:
            ``{qid: label}``; ids with no label in either language are absent.
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
