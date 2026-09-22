"""MediaWiki Action API adapter for one Wikipedia edition at a time.

Implements :class:`~wiki_interest.ports.mediawiki.MediaWikiGateway`. Everything uses
``format=json&formatversion=2`` so pages come back as a list with real booleans (``missing``)
instead of the legacy id-keyed object with empty-string flags.

Action API conventions that shape this module (verified 2026-09-22, see
``references/api-notes.md``):

* Errors are HTTP 200 with an ``{"error": {"code", "info"}}`` envelope, so the shared HTTP
  client cannot classify them; :func:`action_api_error` does, and the Wikidata adapter reuses it.
* Title normalisation (``астрономія`` -> ``Астрономія``) and redirect resolution are reported
  as ``from``/``to`` pairs that must be chained to map a requested title to its final page.
* Ordinary clients may send at most 50 titles per ``query`` request.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from html.parser import HTMLParser
from itertools import batched
from typing import Any

from wiki_interest.adapters.http import HttpJsonClient, as_array, as_object
from wiki_interest.domain.models import WikiProject
from wiki_interest.errors import UpstreamError
from wiki_interest.ports.mediawiki import PageInfo

__all__ = [
    "ActionApiError",
    "MediaWikiApi",
    "action_api_error",
    "prose_link_titles",
    "raise_for_action_api_error",
]

MAX_TITLES_PER_REQUEST = 50
"""Batch limit of the Action API for users without the ``apihighlimits`` right."""

_MAIN_NAMESPACE = 0
_LEAD_SECTION = 0
_MAX_REDIRECT_HOPS = 5
"""Guards the redirect chain walk; MediaWiki itself only follows one hop, so this is generous."""
_MISSING_TITLE_CODE = "missingtitle"
_BASE_PARAMS: dict[str, str | int] = {"format": "json", "formatversion": 2}


class ActionApiError(UpstreamError):
    """The Action API answered with an error envelope instead of data.

    These are persistent (bad parameters, missing page, unknown entity), so they are never
    retried. ``code`` is the machine-readable API code (``missingtitle``, ``no-such-entity``);
    ``details`` is the whole envelope for codes that carry extra fields (Wikibase adds ``id``).
    """

    def __init__(self, details: Mapping[str, Any], url: str) -> None:
        self.code = str(details.get("code", "unknown"))
        self.info = str(details.get("info", ""))
        self.details = details
        super().__init__(
            f"MediaWiki API error {self.code!r} for {url}: {self.info}",
            retryable=False,
            hint="The API rejected the request; check the title or entity id.",
        )


def action_api_error(payload: Any) -> dict[str, Any] | None:
    """Return the error envelope if ``payload`` is an Action API error, else ``None``."""
    if not isinstance(payload, dict) or "error" not in payload:
        return None
    return as_object(payload["error"], "error envelope")


def raise_for_action_api_error(payload: Any, url: str) -> dict[str, Any]:
    """Return the payload as an object, raising :class:`ActionApiError` for error envelopes."""
    error = action_api_error(payload)
    if error is not None:
        raise ActionApiError(error, url)
    return as_object(payload, url)


class MediaWikiApi:
    """Read-only MediaWiki gateway backed by the shared HTTP client.

    Args:
        http: The shared cached client.
        ttl_seconds: Cache TTL for every lookup; redirects and links change rarely, so the
            composition root passes ``Settings.resolution_ttl_s``.
    """

    def __init__(self, http: HttpJsonClient, ttl_seconds: int | None) -> None:
        self._http = http
        self._ttl = ttl_seconds

    def page_info(
        self, project: WikiProject, titles: Sequence[str]
    ) -> Mapping[str, PageInfo | None]:
        """Normalise, follow redirects and identify pages; every requested title is a key."""
        result: dict[str, PageInfo | None] = {}
        for chunk in batched(titles, MAX_TITLES_PER_REQUEST):
            query = self._query(
                project,
                {
                    "action": "query",
                    "titles": "|".join(chunk),
                    "redirects": 1,
                    "prop": "pageprops",
                    "ppprop": "wikibase_item",
                },
            )
            result.update(_map_titles(chunk, query))
        return result

    def redirects_to(self, project: WikiProject, title: str) -> Sequence[str]:
        """Main-namespace titles redirecting to ``title``, following ``continue`` to the end."""
        params: dict[str, str | int] = {
            "action": "query",
            "titles": title,
            "prop": "redirects",
            "rdnamespace": _MAIN_NAMESPACE,
            "rdlimit": "max",
        }
        found: list[str] = []
        for query in self._paginate(project, params):
            for raw_page in as_array(query.get("pages"), "query.pages"):
                page = as_object(raw_page, "query.pages[]")
                for raw_redirect in as_array(page.get("redirects", []), "pages[].redirects"):
                    found.append(str(as_object(raw_redirect, "redirects[]")["title"]))
        return tuple(found)

    def lead_links(self, project: WikiProject, title: str) -> Sequence[str]:
        """Existing articles linked from the prose of section 0 of ``title``.

        ``prop=links`` alone lists every link in the section, including those inside
        citation templates (ISSN, DOI, publishers) and maintenance boxes, which verified on
        2026-09-22 dragged "International Standard Serial Number" into a fasting bundle. The
        rendered ``text`` tells where a link sits: only links inside paragraph prose, outside
        footnotes and tables, are kept. ``links`` still supplies namespace and existence, so
        the result is the intersection of both. Empty if the page is missing.

        ``redirects=1`` makes a redirect title parse its target rather than the one-line
        redirect page, so callers may pass whatever title the user gave.
        """
        params: dict[str, str | int] = {
            "action": "parse",
            "page": title,
            "prop": "links|text",
            "section": _LEAD_SECTION,
            "redirects": 1,
        }
        try:
            parsed = self._request(project, params)
        except ActionApiError as exc:
            if exc.code == _MISSING_TITLE_CODE:
                return ()
            raise
        parse = as_object(parsed.get("parse"), "parse")
        links = as_array(parse.get("links"), "parse.links")
        prose = prose_link_titles(str(parse.get("text", "")))
        return tuple(
            str(link["title"])
            for link in (as_object(raw, "parse.links[]") for raw in links)
            if link.get("ns") == _MAIN_NAMESPACE
            and link.get("exists")
            and str(link["title"]) in prose
        )

    def search(self, project: WikiProject, query: str, *, limit: int = 5) -> Sequence[str]:
        """Full-text search restricted to articles; titles in relevance order."""
        result = self._query(
            project,
            {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srnamespace": _MAIN_NAMESPACE,
                "srlimit": limit,
            },
        )
        hits = as_array(result.get("search"), "query.search")
        return tuple(str(as_object(hit, "query.search[]")["title"]) for hit in hits)

    def _query(self, project: WikiProject, params: Mapping[str, str | int]) -> dict[str, Any]:
        """Issue an ``action=query`` request and return its ``query`` object."""
        return as_object(self._request(project, params).get("query"), "query")

    def _paginate(
        self, project: WikiProject, params: Mapping[str, str | int]
    ) -> Iterator[dict[str, Any]]:
        """Yield the ``query`` object of each page of a continued ``action=query`` request."""
        current: dict[str, str | int] = dict(params)
        while True:
            payload = self._request(project, current)
            yield as_object(payload.get("query"), "query")
            continuation = payload.get("continue")
            if not continuation:
                return
            current = {**dict(params), **as_object(continuation, "continue")}

    def _request(self, project: WikiProject, params: Mapping[str, str | int]) -> dict[str, Any]:
        url = f"https://{project.host}/w/api.php"
        payload = self._http.get_json(url, {**_BASE_PARAMS, **params}, ttl_seconds=self._ttl)
        return raise_for_action_api_error(payload, url)


def _map_titles(requested: Sequence[str], query: Mapping[str, Any]) -> dict[str, PageInfo | None]:
    """Map each requested title to its final page through ``normalized`` and ``redirects``."""
    normalized = _from_to_map(query.get("normalized", []), "query.normalized")
    redirects = _from_to_map(query.get("redirects", []), "query.redirects")
    pages_by_title: dict[str, dict[str, Any]] = {}
    for raw_page in as_array(query.get("pages", []), "query.pages"):
        listed = as_object(raw_page, "query.pages[]")
        pages_by_title[str(listed.get("title", ""))] = listed

    result: dict[str, PageInfo | None] = {}
    for title in requested:
        canonical = normalized.get(title, title)
        final = _follow_redirects(canonical, redirects)
        page = pages_by_title.get(final)
        if page is None or page.get("missing") or page.get("invalid"):
            result[title] = None
            continue
        props = page.get("pageprops") or {}
        qid = props.get("wikibase_item")
        result[title] = PageInfo(
            title=str(page["title"]),
            qid=str(qid) if qid else None,
            redirected_from=title if final != canonical else None,
        )
    return result


def _from_to_map(raw: Any, context: str) -> dict[str, str]:
    return {
        str(entry["from"]): str(entry["to"])
        for entry in (as_object(item, context) for item in as_array(raw, context))
    }


def _follow_redirects(title: str, redirects: Mapping[str, str]) -> str:
    current = title
    for _ in range(_MAX_REDIRECT_HOPS):
        target = redirects.get(current)
        if target is None:
            return current
        current = target
    return current


_EXCLUDED_CONTAINERS = frozenset({"sup", "table", "style", "script", "figure"})
"""Elements whose links are not prose: footnote markers, infoboxes, embedded CSS/JS, images."""


class _ProseLinkCollector(HTMLParser):
    """Collects ``title`` attributes of article links that sit inside paragraph prose.

    Tracks how deep the parser is inside ``<p>`` and inside excluded containers; a link
    counts only when it is in at least one paragraph and in no excluded container. Links to
    missing pages (``class="new"``) and external links (no ``/wiki/`` href) are ignored.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titles: set[str] = set()
        self._paragraph_depth = 0
        self._excluded_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "p":
            self._paragraph_depth += 1
        elif tag in _EXCLUDED_CONTAINERS:
            self._excluded_depth += 1
        elif tag == "a" and self._paragraph_depth and not self._excluded_depth:
            self._collect(dict(attrs))

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            self._paragraph_depth = max(0, self._paragraph_depth - 1)
        elif tag in _EXCLUDED_CONTAINERS:
            self._excluded_depth = max(0, self._excluded_depth - 1)

    def _collect(self, attrs: Mapping[str, str | None]) -> None:
        href = attrs.get("href") or ""
        title = attrs.get("title")
        classes = (attrs.get("class") or "").split()
        if title and href.startswith("/wiki/") and "new" not in classes:
            self.titles.add(title)


def prose_link_titles(html: str) -> frozenset[str]:
    """Return the titles linked from paragraph prose of rendered MediaWiki HTML.

    Args:
        html: ``parse.text`` of an Action API ``action=parse`` response.

    Returns:
        Link targets exactly as MediaWiki writes them in ``title`` attributes, which match
        the ``title`` field of ``prop=links`` entries.
    """
    collector = _ProseLinkCollector()
    collector.feed(html)
    collector.close()
    return frozenset(collector.titles)
