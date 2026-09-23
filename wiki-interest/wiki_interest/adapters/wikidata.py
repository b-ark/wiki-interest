"""Wikidata adapter over the ``wb*`` modules of Wikidata's Action API.

Implements :class:`~wiki_interest.ports.wikidata.WikidataGateway`. Design notes (verified
2026-09-22, see ``references/api-notes.md``):

* ``wbgetentities`` fails the *whole* batch with ``no-such-entity`` when any id does not
  exist (it does not mark the entity ``missing`` as older docs suggest). The port promises that
  unknown ids are simply absent, so the adapter drops the offending id and re-issues the batch.
* Related entities are read with ``wbgetclaims`` per property rather than one ``wbgetentities
  &props=claims`` call: big items (``Q333`` astronomy) carry hundreds of statements, and the
  bundle builder only needs three or four properties. Each small response is cached separately.
* ``exact_label_match`` compares casefolded strings because ``wbsearchentities`` already
  matches case-insensitively; a candidate whose label *or alias* equals the query is the
  "clear winner" the resolver looks for. Aliases count because users write the long form:
  "English language" is an alias of ``Q1860`` (label "English"), and treating it as fuzzy
  sent a plain request into clarification (verified 2026-09-22). Several exact matches are
  resolved by the resolver, not here.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import batched
from typing import Any

from wiki_interest.adapters.http import HttpJsonClient, as_array, as_object
from wiki_interest.adapters.mediawiki import ActionApiError, raise_for_action_api_error
from wiki_interest.domain.models import EntityCandidate, WikiProject
from wiki_interest.ports.wikidata import EntitySummary

__all__ = ["MAX_IDS_PER_REQUEST", "WikidataApi"]

MAX_IDS_PER_REQUEST = 50
"""``wbgetentities`` accepts at most 50 ids per call for ordinary clients."""

_NO_SUCH_ENTITY_CODE = "no-such-entity"
_FALLBACK_LABEL_LANGUAGE = "en"
_VALUE_SNAK = "value"
_DEPRECATED_RANK = "deprecated"
_WIKI_SUFFIX = "wiki"
_NOT_WIKIPEDIA = frozenset(
    {
        "commonswiki",
        "foundationwiki",
        "incubatorwiki",
        "mediawikiwiki",
        "metawiki",
        "nostalgiawiki",
        "outreachwiki",
        "sourceswiki",
        "specieswiki",
        "testwiki",
        "test2wiki",
        "testwikidatawiki",
        "wikidatawiki",
        "wikifunctionswiki",
        "wikimaniawiki",
    }
)
"""Site ids that end in ``wiki`` but are not language editions of Wikipedia."""


class WikidataApi:
    """Wikidata gateway (:class:`~wiki_interest.ports.wikidata.WikidataGateway`) over HTTP.

    Args:
        http: The shared cached client; the endpoint is ``http.settings.wikidata_api_url``.
        ttl_seconds: Cache TTL for lookups; the composition root passes
            ``Settings.resolution_ttl_s``.
    """

    def __init__(self, http: HttpJsonClient, ttl_seconds: int | None) -> None:
        self._http = http
        self._ttl = ttl_seconds
        self._url = http.settings.wikidata_api_url

    def search_entities(
        self, query: str, language: str, *, limit: int = 5
    ) -> Sequence[EntityCandidate]:
        """Search items by label/alias in ``language``; see the port for the contract."""
        payload = self._request(
            {
                "action": "wbsearchentities",
                "search": query,
                "language": language,
                "uselang": language,
                "type": "item",
                "limit": limit,
            }
        )
        hits = as_array(payload.get("search"), "search")
        return tuple(_candidate(as_object(hit, "search[]"), query) for hit in hits)

    def sitelinks(
        self, qids: Sequence[str], projects: Sequence[WikiProject]
    ) -> Mapping[str, Mapping[WikiProject, str]]:
        """Article titles per edition; unknown ids and editions without an article are absent."""
        by_site = {project.site_id: project for project in projects}
        result: dict[str, Mapping[WikiProject, str]] = {}
        for qid, entity in self._entities(
            qids, {"props": "sitelinks", "sitefilter": "|".join(by_site)}
        ).items():
            links = as_object(entity.get("sitelinks", {}), "entity.sitelinks")
            titles = {
                by_site[site]: str(as_object(link, "sitelinks[]")["title"])
                for site, link in links.items()
                if site in by_site
            }
            result[qid] = titles
        return result

    def labels(
        self, qids: Sequence[str], language: str, *, fallback: bool = True
    ) -> Mapping[str, str]:
        """Labels in ``language``, optionally falling back to English; others are absent."""
        languages = _unique((language, _FALLBACK_LABEL_LANGUAGE)) if fallback else (language,)
        result: dict[str, str] = {}
        for qid, entity in self._entities(
            qids, {"props": "labels", "languages": "|".join(languages)}
        ).items():
            found = as_object(entity.get("labels", {}), "entity.labels")
            for candidate_language in languages:
                if candidate_language in found:
                    label = as_object(found[candidate_language], "labels[]")
                    result[qid] = str(label["value"])
                    break
        return result

    def summary(self, qid: str, language: str) -> EntitySummary | None:
        """Label, description and Wikipedia editions of one item, in one request."""
        return self.summaries([qid], language).get(qid)

    def summaries(self, qids: Sequence[str], language: str) -> Mapping[str, EntitySummary]:
        """Label, description and Wikipedia editions of several items, batched."""
        languages = _unique((language, _FALLBACK_LABEL_LANGUAGE))
        found = self._entities(
            qids, {"props": "labels|descriptions|sitelinks", "languages": "|".join(languages)}
        )
        result: dict[str, EntitySummary] = {}
        for qid, entity in found.items():
            sites = as_object(entity.get("sitelinks", {}), "entity.sitelinks")
            result[qid] = EntitySummary(
                qid=qid,
                label=_first_text(entity.get("labels", {}), languages),
                description=_first_text(entity.get("descriptions", {}), languages),
                languages=tuple(
                    site[: -len(_WIKI_SUFFIX)].replace("_", "-")
                    for site in sites
                    if site.endswith(_WIKI_SUFFIX) and site not in _NOT_WIKIPEDIA
                ),
            )
        return result

    def related_entities(
        self, qid: str, properties: Sequence[str]
    ) -> Mapping[str, tuple[str, ...]]:
        """Item ids of forward claims per property, in statement order, deprecated ones skipped."""
        return {prop: self._claim_targets(qid, prop) for prop in properties}

    def _claim_targets(self, qid: str, prop: str) -> tuple[str, ...]:
        try:
            payload = self._request({"action": "wbgetclaims", "entity": qid, "property": prop})
        except ActionApiError as exc:
            if exc.code == _NO_SUCH_ENTITY_CODE:
                return ()
            raise
        claims = as_object(payload.get("claims", {}), "claims")
        statements = as_array(claims.get(prop, []), f"claims.{prop}")
        targets: list[str] = []
        for raw_statement in statements:
            target = _statement_target(as_object(raw_statement, "claims[]"))
            if target is not None:
                targets.append(target)
        return tuple(targets)

    def _entities(
        self, qids: Sequence[str], params: Mapping[str, str | int]
    ) -> dict[str, dict[str, Any]]:
        """Fetch ``wbgetentities`` in batches, silently skipping ids Wikidata does not know."""
        found: dict[str, dict[str, Any]] = {}
        for chunk in batched(_unique(qids), MAX_IDS_PER_REQUEST):
            found.update(self._entity_batch(list(chunk), params))
        return found

    def _entity_batch(
        self, ids: list[str], params: Mapping[str, str | int]
    ) -> dict[str, dict[str, Any]]:
        """One batch; on ``no-such-entity`` drop the named id and retry with the rest."""
        while ids:
            try:
                payload = self._request({"action": "wbgetentities", "ids": "|".join(ids), **params})
            except ActionApiError as exc:
                unknown = _unknown_entity_id(exc)
                if unknown is None or unknown not in ids:
                    raise
                ids = [qid for qid in ids if qid != unknown]
                continue
            entities = as_object(payload.get("entities", {}), "entities")
            return {
                qid: entity
                for qid, entity in ((k, as_object(v, "entities[]")) for k, v in entities.items())
                if "missing" not in entity
            }
        return {}

    def _request(self, params: Mapping[str, str | int]) -> dict[str, Any]:
        payload = self._http.get_json(
            self._url, {**params, "format": "json"}, ttl_seconds=self._ttl
        )
        return raise_for_action_api_error(payload, self._url)


_EXACT_MATCH_TYPES = frozenset({"label", "alias"})
"""``wbsearchentities`` match types that count as the query naming the item exactly."""


def _candidate(hit: Mapping[str, Any], query: str) -> EntityCandidate:
    label = str(hit.get("label", hit["id"]))
    match = hit.get("match") or {}
    wanted = query.casefold()
    exact = label.casefold() == wanted or (
        match.get("type") in _EXACT_MATCH_TYPES and str(match.get("text", "")).casefold() == wanted
    )
    description = hit.get("description")
    return EntityCandidate(
        qid=str(hit["id"]),
        label=label,
        description=str(description) if description else None,
        exact_label_match=exact,
    )


def _statement_target(statement: Mapping[str, Any]) -> str | None:
    """Item id a statement points to, or ``None`` for novalue/somevalue/deprecated statements."""
    if statement.get("rank") == _DEPRECATED_RANK:
        return None
    snak = as_object(statement.get("mainsnak", {}), "mainsnak")
    if snak.get("snaktype") != _VALUE_SNAK:
        return None
    value = as_object(as_object(snak.get("datavalue", {}), "datavalue").get("value", {}), "value")
    target = value.get("id")
    return str(target) if target else None


def _unknown_entity_id(exc: ActionApiError) -> str | None:
    """Return the id a ``no-such-entity`` error names (Wikibase adds ``id`` to the envelope)."""
    if exc.code != _NO_SUCH_ENTITY_CODE:
        return None
    unknown = exc.details.get("id")
    return str(unknown) if unknown else None


def _first_text(raw: Any, languages: Sequence[str]) -> str | None:
    """Value of the first language present in a ``labels``/``descriptions`` object."""
    texts = as_object(raw, "entity terms")
    for language in languages:
        if language in texts:
            return str(as_object(texts[language], "term")["value"])
    return None


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))
