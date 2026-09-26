"""Use-case: what the skill can check next on its own, and how the report names an item.

The next check a report proposes is one the skill can run itself: the topic's neighbouring
articles (found through Wikidata: what it is a kind of, a part of, commonly confused with,
made of) that have an article in the edition the recommendation chose, or more language
editions that have the article. Outside sources come only when neither is left.

Names: an item is named by the title of its article in the report language's Wikipedia
("Веганство" for Q181138 in Ukrainian, not the Wikidata label "веганізм"), lower-cased when
it is a common noun, which Wikidata's English label tells (lower-case by its convention).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from wiki_interest.domain.models import WikiProject
from wiki_interest.errors import UpstreamError
from wiki_interest.ports.wikidata import WikidataGateway

__all__ = ["RELATED_PROPERTIES", "Related", "RelatedTopics", "local_names"]

RELATED_PROPERTIES = ("P279", "P1889", "P361", "P527", "P1269", "P460")
"""Subclass of, different from (often confused with), part of, has part, facet of, said to be
the same as: the neighbours a reader of the topic also reads, in the order they are offered."""
BIG_EDITIONS = ("en", "de", "fr", "es", "ja", "ru", "it", "zh", "pt", "pl", "uk", "nl")
"""Editions offered for a comparison, largest first, when the topic has an article there."""
_MAX_RELATED = 2
_MAX_EDITIONS = 2


@dataclass(frozen=True, slots=True)
class Related:
    """A neighbouring item the skill can measure next.

    Attributes:
        qid: Its Wikidata item.
        label: How the report names it, in the report language.
        projects: The requested editions that have an article on it.
    """

    qid: str
    label: str
    projects: tuple[str, ...]


def local_names(wikidata: WikidataGateway, qids: Sequence[str], language: str) -> dict[str, str]:
    """How the report names each item: its article's title in the report language's Wikipedia.

    Lower-cased when the English label is (a common noun); the Wikidata label in that
    language when there is no article; left out when there is neither.
    """
    if not qids:
        return {}
    project = WikiProject(language)
    titles = wikidata.sitelinks(list(qids), [project])
    labels = wikidata.labels(list(qids), language, fallback=False)
    english = wikidata.labels(list(qids), "en", fallback=False)
    out: dict[str, str] = {}
    for qid in qids:
        title = _bare(titles.get(qid, {}).get(project) or labels.get(qid) or "")
        if not title:
            continue
        common = english.get(qid, "")[:1].islower()
        out[qid] = title[:1].lower() + title[1:] if common and title[1:2].islower() else title
    return out


def _bare(title: str) -> str:
    """A title without its disambiguation: "Tesla (компания)" is "Tesla".

    The meaning is stated next to the name (the item's description); in a headline the
    bracket read as part of the topic (stage16).
    """
    if title.endswith(")") and " (" in title:
        return title[: title.rindex(" (")].strip()
    return title


class RelatedTopics:
    """Finds the neighbouring articles and the further editions of a topic.

    Args:
        wikidata: The Wikidata gateway.
    """

    def __init__(self, wikidata: WikidataGateway) -> None:
        self._wikidata = wikidata

    def neighbours(self, qid: str, projects: Sequence[WikiProject], language: str) -> list[Related]:
        """Up to two neighbours with an article in at least one of ``projects``.

        Neighbours with an article in more of them come first; an outside failure gives
        none rather than failing the run.
        """
        try:
            claims = self._wikidata.related_entities(qid, RELATED_PROPERTIES)
            found = list(
                dict.fromkeys(q for prop in RELATED_PROPERTIES for q in claims.get(prop, ()))
            )
            found = [q for q in found if q != qid]
            if not found:
                return []
            links = self._wikidata.sitelinks(found, list(projects))
            names = local_names(self._wikidata, found, language)
        except UpstreamError:
            return []
        ranked = sorted(
            (q for q in found if links.get(q) and q in names),
            key=lambda q: -len(links.get(q, {})),
        )
        return [
            Related(
                qid=q,
                label=names[q],
                projects=tuple(p.domain for p in projects if p in links.get(q, {})),
            )
            for q in ranked[:_MAX_RELATED]
        ]

    def more_editions(self, qid: str, requested: Sequence[WikiProject]) -> list[str]:
        """Up to two large editions with an article on ``qid`` that were not requested."""
        try:
            summary = self._wikidata.summary(qid, "en")
        except UpstreamError:
            return []
        if summary is None:
            return []
        asked = {p.language for p in requested}
        return [code for code in BIG_EDITIONS if code in summary.languages and code not in asked][
            :_MAX_EDITIONS
        ]
