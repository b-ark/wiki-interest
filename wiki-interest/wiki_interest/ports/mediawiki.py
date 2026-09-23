"""Port: per-edition MediaWiki lookups (redirects, links, search, page identity)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from wiki_interest.domain.models import WikiProject

__all__ = ["MediaWikiGateway", "Mention", "PageInfo"]


@dataclass(frozen=True, slots=True)
class PageInfo:
    """Identity of an existing page after title normalisation and redirect resolution.

    Attributes:
        title: Canonical title of the target page.
        qid: Wikidata item bound to the page, if any.
        redirected_from: The requested title when it was a redirect, else ``None``.
        redirect_title: Canonical spelling of that redirect page (``redirected_from`` is the
            spelling as requested); the Pageviews API counts redirect visits under it.
        fragment: Section of the target the redirect points to (``"Post przerywany"`` in
            ``Głodówka#Post przerywany``), if any.
    """

    title: str
    qid: str | None
    redirected_from: str | None = None
    redirect_title: str | None = None
    fragment: str | None = None


@dataclass(frozen=True, slots=True)
class Mention:
    """An article whose text contains a phrase, with the matching passage.

    Attributes:
        title: Article title.
        snippet: Plain-text passage around the match as the search engine returned it.
    """

    title: str
    snippet: str


class MediaWikiGateway(Protocol):
    """Read-only access to one Wikipedia edition's MediaWiki API."""

    def page_info(
        self, project: WikiProject, titles: Sequence[str]
    ) -> Mapping[str, PageInfo | None]:
        """Normalise titles, follow redirects and report whether pages exist.

        Args:
            project: Edition to query.
            titles: Titles as given by the user or another API; any spelling accepted.

        Returns:
            ``{requested_title: PageInfo}`` for existing pages and ``{requested_title: None}``
            for missing ones. Every requested title is a key.
        """
        ...

    def redirects_to(self, project: WikiProject, title: str) -> Sequence[str]:
        """Return titles of main-namespace pages that redirect to ``title``."""
        ...

    def lead_links(self, project: WikiProject, title: str) -> Sequence[str]:
        """Return existing main-namespace articles linked from the lead section of ``title``.

        The lead section is the part before the first heading; its links are the concepts an
        editor chose to introduce the topic with, which makes them good bundle candidates.
        """
        ...

    def search(self, project: WikiProject, query: str, *, limit: int = 5) -> Sequence[str]:
        """Full-text search fallback when no sitelink exists; titles best match first."""
        ...

    def mentions(self, project: WikiProject, phrase: str, *, limit: int = 5) -> Sequence[Mention]:
        """Articles whose text contains ``phrase`` exactly (word order kept), best first.

        Unlike :meth:`search`, which matches the words anywhere ("post" alone finds a
        politician), this finds articles that name the topic, for users choosing a substitute
        when an edition has no article of its own.
        """
        ...
