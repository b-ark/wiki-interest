"""Use-case: turn topic specifications into article bundles per language edition.

A topic phrased by the user ("інтервальне голодування") becomes, for every requested edition,
a :class:`~wiki_interest.domain.models.TopicBundle`: the main article, related articles that
describe the same concepts in every edition, manual additions, and the redirects that feed
views into each of them. Wikidata is the bridge between languages; MediaWiki supplies
edition-specific facts (redirects, lead-section links, search).

The resolver never guesses when the entity is ambiguous: it raises
:class:`~wiki_interest.errors.ClarificationNeededError` so the agent asks the user.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from wiki_interest.contracts.request import AnalysisRequest, TopicSpec
from wiki_interest.domain.bundle import BundleSettings, rank_related_concepts
from wiki_interest.domain.models import (
    ArticleRef,
    ArticleRole,
    BundleStatus,
    EntityCandidate,
    ResolutionSource,
    TopicBundle,
    WikiProject,
)
from wiki_interest.errors import ClarificationNeededError
from wiki_interest.ports.mediawiki import MediaWikiGateway
from wiki_interest.ports.wikidata import WikidataGateway

__all__ = ["ResolutionSettings", "ResolvedTopic", "TopicResolver"]


@dataclass(frozen=True, slots=True)
class ResolutionSettings:
    """Tunables of the resolution step.

    Attributes:
        related_properties: Wikidata properties followed from the main item to find related
            concepts (subclass of, part of, has part, facet of).
        candidate_limit: How many Wikidata search hits to consider.
        search_limit: How many full-text hits to consider in the search fallback.
        max_redirects_per_article: Cap on redirects whose views are added to an article; each
            redirect costs one pageview request, and beyond a few dozen the tail is noise.
        manual_weight: Bundle weight of titles the user added by hand; below the main article
            (1.0) so a long manual list cannot drown the topic's core.
        bundle: Weights and cap for automatically found related concepts.
    """

    related_properties: tuple[str, ...] = ("P279", "P361", "P527", "P1269")
    candidate_limit: int = 5
    search_limit: int = 3
    max_redirects_per_article: int = 20
    manual_weight: float = 0.5
    bundle: BundleSettings = field(default_factory=BundleSettings)


_DEFAULT_SETTINGS = ResolutionSettings()


@dataclass(frozen=True, slots=True)
class ResolvedTopic:
    """What one topic turned out to be, across all requested editions.

    Attributes:
        topic_id: Identifier from the request.
        query: The user's wording.
        qid: Wikidata item the topic was pinned to, or ``None`` when no entity matched.
        label: Label of that item in the query language, when known.
        bundles: One bundle per requested edition, in request order.
        missing_titles: ``(project, title)`` pairs from ``extra_titles`` that do not exist; the
            report lists them so a typo never silently shrinks the bundle.
    """

    topic_id: str
    query: str
    qid: str | None
    label: str | None
    bundles: tuple[TopicBundle, ...]
    missing_titles: tuple[tuple[WikiProject, str], ...] = ()

    def bundle_for(self, project: WikiProject) -> TopicBundle:
        """Return the bundle resolved for ``project``.

        Raises:
            KeyError: If the edition was not part of the request.
        """
        for bundle in self.bundles:
            if bundle.project == project:
                return bundle
        msg = f"No bundle resolved for {project.domain}"
        raise KeyError(msg)


class TopicResolver:
    """Resolves topics to article bundles using Wikidata and MediaWiki gateways."""

    def __init__(
        self,
        wikidata: WikidataGateway,
        mediawiki: MediaWikiGateway,
        *,
        settings: ResolutionSettings = _DEFAULT_SETTINGS,
    ) -> None:
        self._wikidata = wikidata
        self._mediawiki = mediawiki
        self._settings = settings

    def resolve_request(self, request: AnalysisRequest) -> tuple[ResolvedTopic, ...]:
        """Resolve every topic of a request against its projects, in request order."""
        projects = request.project_objects
        return tuple(self.resolve(topic, projects) for topic in request.topics)

    def resolve(self, topic: TopicSpec, projects: Sequence[WikiProject]) -> ResolvedTopic:
        """Resolve one topic in the given editions.

        Args:
            topic: Topic specification from the request (``id`` must be filled).
            projects: Editions to resolve in.

        Returns:
            The resolved topic with one bundle per edition.

        Raises:
            ClarificationNeededError: If the query matches several plausible entities.
        """
        if topic.id is None:
            msg = "TopicSpec.id must be set before resolution"
            raise ValueError(msg)
        qid, label = self._entity(topic, projects)
        mains = self._main_articles(topic, qid, projects)
        related: Mapping[WikiProject, tuple[ArticleRef, ...]] = {}
        if topic.bundle == "auto" and qid is not None:
            related = self._related_articles(qid, mains, projects)
        missing: list[tuple[WikiProject, str]] = []
        bundles = tuple(
            self._bundle(topic, project, mains[project], related.get(project, ()), missing)
            for project in projects
        )
        return ResolvedTopic(
            topic_id=topic.id,
            query=topic.query,
            qid=qid,
            label=label,
            bundles=bundles,
            missing_titles=tuple(missing),
        )

    # -- entity ---------------------------------------------------------------------------

    def _entity(
        self, topic: TopicSpec, projects: Sequence[WikiProject]
    ) -> tuple[str | None, str | None]:
        """Pick the Wikidata item for a topic, or raise when the choice is not obvious."""
        if topic.qid is not None:
            labels = self._wikidata.labels([topic.qid], topic.query_language)
            return topic.qid, labels.get(topic.qid)
        candidates = self._wikidata.search_entities(
            topic.query, topic.query_language, limit=self._settings.candidate_limit
        )
        if not candidates:
            return None, None
        chosen = self._choose(candidates, projects)
        if chosen is None:
            assert topic.id is not None
            raise ClarificationNeededError(
                f"Topic {topic.query!r} matches several Wikidata entities",
                topic_id=topic.id,
                candidates=candidates,
                hint="Ask the user which candidate they mean, then rerun with topics[].qid set.",
            )
        return chosen.qid, chosen.label

    def _choose(
        self, candidates: Sequence[EntityCandidate], projects: Sequence[WikiProject]
    ) -> EntityCandidate | None:
        """Return the only sensible candidate, or ``None`` when a human has to choose.

        A single hit, or exactly one exact match (label or alias), is unambiguous. Exact
        homonyms are common on Wikidata, so several exact matches are narrowed by how many of
        the requested editions have an article about each: an item without articles there
        cannot be analysed anyway (astronomy the science vs the fictional Hogwarts class).
        If several remain, one is picked only when two independent signals agree: it covers
        strictly more requested editions than any other *and* Wikidata ranks it first among
        the exact matches ("English language" -> ``English`` in 5 of 5 editions rather than
        ``English studies`` in 3 of 5). Anything less clear is a question for the user,
        because a wrong pick would silently analyse a different subject.
        """
        if len(candidates) == 1:
            return candidates[0]
        exact = [c for c in candidates if c.exact_label_match]
        if len(exact) <= 1:
            return exact[0] if exact else None
        return self._break_tie(exact, projects)

    def _break_tie(
        self, exact: Sequence[EntityCandidate], projects: Sequence[WikiProject]
    ) -> EntityCandidate | None:
        """Pick among several exact matches by edition coverage, as documented in ``_choose``."""
        links = self._wikidata.sitelinks([c.qid for c in exact], projects)
        coverage = {c.qid: len(links.get(c.qid, {})) for c in exact}
        covered = [c for c in exact if coverage[c.qid] > 0]
        if not covered:
            return None
        best = max(coverage[c.qid] for c in covered)
        leaders = [c for c in covered if coverage[c.qid] == best]
        # ``covered`` keeps Wikidata's ranking, so ``covered[0]`` is its top exact match; a
        # single covered candidate is trivially both the leader and the first.
        if len(leaders) == 1 and leaders[0] is covered[0]:
            return leaders[0]
        return None

    # -- main articles --------------------------------------------------------------------

    def _main_articles(
        self, topic: TopicSpec, qid: str | None, projects: Sequence[WikiProject]
    ) -> dict[WikiProject, ArticleRef | None]:
        """Find the main article per edition: sitelink first, full-text search as fallback."""
        sitelinks: Mapping[WikiProject, str] = {}
        if qid is not None:
            sitelinks = self._wikidata.sitelinks([qid], projects).get(qid, {})
        mains: dict[WikiProject, ArticleRef | None] = {}
        for project in projects:
            title = sitelinks.get(project)
            if title is not None:
                mains[project] = ArticleRef(
                    project, title, ArticleRole.MAIN, ResolutionSource.SITELINK, qid=qid
                )
            else:
                mains[project] = self._search_fallback(topic, qid, project)
        return mains

    def _search_fallback(
        self, topic: TopicSpec, qid: str | None, project: WikiProject
    ) -> ArticleRef | None:
        """Search the edition by the entity's local label, then by the raw query.

        Full-text search returns whatever mentions the words, so a hit is accepted only when
        it is not bound to a *different* Wikidata item: searching Polish Wikipedia for
        "intermittent fasting" returned "Stres oksydacyjny" (oxidative stress, its own item),
        which would have silently analysed another subject. An honest "no article" is better.
        """
        queries: list[str] = []
        if qid is not None:
            local = self._wikidata.labels([qid], project.language).get(qid)
            if local:
                queries.append(local)
        if topic.query not in queries:
            queries.append(topic.query)
        for text in queries:
            hits = self._mediawiki.search(project, text, limit=self._settings.search_limit)
            if not hits:
                continue
            infos = self._mediawiki.page_info(project, hits)
            for hit in hits:
                info = infos.get(hit)
                if info is not None and _same_subject(info.qid, qid):
                    return ArticleRef(
                        project,
                        info.title,
                        ArticleRole.MAIN,
                        ResolutionSource.SEARCH_FALLBACK,
                        qid=info.qid,
                    )
        return None

    # -- related articles -----------------------------------------------------------------

    def _related_articles(
        self,
        qid: str,
        mains: Mapping[WikiProject, ArticleRef | None],
        projects: Sequence[WikiProject],
    ) -> dict[WikiProject, tuple[ArticleRef, ...]]:
        """Build the cross-edition concept bundle and map it to titles per edition."""
        lead_qids: dict[WikiProject, list[str]] = {}
        for project, main in mains.items():
            if main is None:
                continue
            titles = self._mediawiki.lead_links(project, main.title)
            infos = self._mediawiki.page_info(project, titles) if titles else {}
            lead_qids[project] = [info.qid for info in infos.values() if info and info.qid]
        wikidata_related = self._wikidata.related_entities(qid, self._settings.related_properties)
        concepts = rank_related_concepts(
            qid, lead_qids, wikidata_related, settings=self._settings.bundle
        )
        if not concepts:
            return {}
        links = self._wikidata.sitelinks([c.qid for c in concepts], projects)
        result: dict[WikiProject, tuple[ArticleRef, ...]] = {}
        for project in projects:
            refs = [
                ArticleRef(
                    project,
                    links[c.qid][project],
                    ArticleRole.RELATED,
                    c.source,
                    weight=c.weight,
                    qid=c.qid,
                )
                for c in concepts
                if project in links.get(c.qid, {})
            ]
            result[project] = tuple(refs)
        return result

    # -- assembling a bundle --------------------------------------------------------------

    def _bundle(
        self,
        topic: TopicSpec,
        project: WikiProject,
        main: ArticleRef | None,
        related: Sequence[ArticleRef],
        missing: list[tuple[WikiProject, str]],
    ) -> TopicBundle:
        """Assemble main + related + manual articles, apply exclusions, attach redirects."""
        assert topic.id is not None
        articles: list[ArticleRef] = [main] if main is not None else []
        if topic.bundle == "auto" and main is not None:
            # Related concepts describe the neighbourhood of the main article; without it
            # they would stand in for a topic the edition does not cover at all.
            articles.extend(related)
        if topic.bundle != "main":
            articles.extend(self._manual_articles(topic, project, articles, missing))
        articles = self._without_excluded(topic, project, articles)
        if not articles:
            return TopicBundle(topic.id, project, BundleStatus.NOT_FOUND)
        if main is None or articles[0].role is not ArticleRole.MAIN:
            # Nothing came from Wikidata, so the user's first title stands in as the main one.
            articles[0] = replace(articles[0], role=ArticleRole.MAIN, weight=1.0)
        status = (
            BundleStatus.FOUND_VIA_SEARCH
            if articles[0].source is ResolutionSource.SEARCH_FALLBACK
            else BundleStatus.FOUND
        )
        with_redirects = tuple(self._with_redirects(project, a) for a in articles)
        return TopicBundle(topic.id, project, status, with_redirects)

    def _manual_articles(
        self,
        topic: TopicSpec,
        project: WikiProject,
        existing: Sequence[ArticleRef],
        missing: list[tuple[WikiProject, str]],
    ) -> list[ArticleRef]:
        """Validate user-supplied titles and add the existing ones with the manual weight."""
        titles = topic.extra_titles.get(project.domain, [])
        if not titles:
            return []
        infos = self._mediawiki.page_info(project, titles)
        known = {a.title for a in existing}
        added: list[ArticleRef] = []
        for title in titles:
            info = infos.get(title)
            if info is None:
                missing.append((project, title))
                continue
            if info.title in known:
                continue
            known.add(info.title)
            added.append(
                ArticleRef(
                    project,
                    info.title,
                    ArticleRole.MANUAL,
                    ResolutionSource.MANUAL,
                    weight=self._settings.manual_weight,
                    qid=info.qid,
                )
            )
        return added

    def _without_excluded(
        self, topic: TopicSpec, project: WikiProject, articles: list[ArticleRef]
    ) -> list[ArticleRef]:
        """Drop articles the user excluded, matching raw and normalised spellings."""
        raw = topic.exclude_titles.get(project.domain, [])
        if not raw or not articles:
            return articles
        excluded = set(raw)
        for requested, info in self._mediawiki.page_info(project, raw).items():
            excluded.add(requested)
            if info is not None:
                excluded.add(info.title)
        return [a for a in articles if a.title not in excluded]

    def _with_redirects(self, project: WikiProject, article: ArticleRef) -> ArticleRef:
        """Attach the (capped) list of redirect titles whose views belong to the article."""
        redirects = tuple(self._mediawiki.redirects_to(project, article.title))
        return replace(article, redirects=redirects[: self._settings.max_redirects_per_article])


def _same_subject(found_qid: str | None, topic_qid: str | None) -> bool:
    """Whether a search hit may represent the topic.

    Pages without a Wikidata item cannot be checked and are accepted (the reliability check
    still flags the search fallback); pages bound to another item are rejected.
    """
    return found_qid is None or topic_qid is None or found_qid == topic_qid
