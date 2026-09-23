"""Use-case: turn topic specifications into article bundles per language edition.

A topic phrased by the user ("інтервальне голодування") becomes, for every requested edition,
a :class:`~wiki_interest.domain.models.TopicBundle`: the main article with the redirects that
feed views into it (this is what gets measured), plus related articles and manual additions
reported next to it as context. Wikidata is the bridge between languages; MediaWiki supplies
edition-specific facts (redirects, lead-section links, search).

The resolver never guesses when the entity is ambiguous: it raises
:class:`~wiki_interest.errors.ClarificationNeededError` so the agent asks the user. Nor does it
guess what stands in for a missing article: an edition without one gets a ``NOT_FOUND``
bundle, :mod:`wiki_interest.application.coverage` offers the user substitutes, and a
substitute the user chose (``topics[].substitutes``) becomes a ``SUBSTITUTE`` bundle here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from wiki_interest.contracts.request import AnalysisRequest, SubstituteSpec, TopicSpec
from wiki_interest.domain.bundle import BundleSettings, rank_related_concepts
from wiki_interest.domain.entity_choice import CandidateEvidence, ChoiceSettings, choose_by_meaning
from wiki_interest.domain.models import (
    ArticleRef,
    ArticleRole,
    BundleStatus,
    EntityCandidate,
    ResolutionSource,
    SubstituteKind,
    TopicBundle,
    WikiProject,
)
from wiki_interest.errors import ClarificationNeededError, TopicNotFoundError
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
        max_redirects_per_article: Cap on redirects whose views are added to the main article;
            each redirect costs one pageview request, and beyond a few dozen the tail is noise.
        bundle: Relevance scores and cap for automatically found related concepts.
        choice: Weights and thresholds for picking among homonyms by the stated meaning.
    """

    related_properties: tuple[str, ...] = ("P279", "P361", "P527", "P1269")
    candidate_limit: int = 5
    search_limit: int = 3
    max_redirects_per_article: int = 20
    bundle: BundleSettings = field(default_factory=BundleSettings)
    choice: ChoiceSettings = field(default_factory=ChoiceSettings)


_DEFAULT_SETTINGS = ResolutionSettings()
_ENGLISH = "en"
_QUALIFIER = re.compile(r"\s*\([^)]*\)\s*$")
"""A trailing "(programming language)" as in Wikipedia titles."""


@dataclass(frozen=True, slots=True)
class ResolvedTopic:
    """What one topic turned out to be, across all requested editions.

    Attributes:
        topic_id: Identifier from the request.
        query: The user's wording.
        qid: Wikidata item the topic was pinned to, or ``None`` when no entity matched.
        label: Label of that item in the query language, when known.
        matched_in_english: Whether the item was found by ``query_en`` because the search in
            the query language found nothing; the coverage question says so, so the user can
            confirm the entity.
        description: Wikidata description of the item, shown next to the label so the agent
            can check it against what the user meant.
        alternatives: Other items the search returned, so a wrong pick can be corrected by
            ``qid`` without another search.
        bundles: One bundle per requested edition, in request order.
        missing_titles: ``(project, title)`` pairs from ``extra_titles`` that do not exist; the
            report lists them so a typo never silently shrinks the bundle.
        method: How the item was chosen: ``pinned`` (``qid`` given), ``link`` (the user's
            article), ``unique`` (one match), ``auto`` (picked among homonyms by the stated
            meaning), ``default`` (no meaning stated; coverage and ranking agreed), ``none``.
        confidence: For ``auto``: the leader's share of the two best scores, in ``[0.5, 1]``.
        runner_up: For ``auto``: the second-best candidate.
    """

    topic_id: str
    query: str
    qid: str | None
    label: str | None
    bundles: tuple[TopicBundle, ...]
    missing_titles: tuple[tuple[WikiProject, str], ...] = ()
    matched_in_english: bool = False
    description: str | None = None
    alternatives: tuple[EntityCandidate, ...] = ()
    method: str = "none"
    confidence: float | None = None
    runner_up: str | None = None

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


@dataclass(frozen=True, slots=True)
class _Entity:
    """What a topic resolved to before its articles are looked up."""

    qid: str | None = None
    label: str | None = None
    description: str | None = None
    matched_in_english: bool = False
    alternatives: tuple[EntityCandidate, ...] = ()
    linked_article: ArticleRef | None = None
    """The user's linked article when it has no Wikidata item; it becomes the main one."""
    method: str = "none"
    confidence: float | None = None
    runner_up: str | None = None


@dataclass(frozen=True, slots=True)
class _Choice:
    """The candidate picked and how; ``candidate`` is ``None`` when the user must choose."""

    candidate: EntityCandidate | None
    method: str = "unique"
    confidence: float | None = None
    runner_up: str | None = None


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
            TopicNotFoundError: If nothing matches the topic in any requested edition.
        """
        if topic.id is None:
            msg = "TopicSpec.id must be set before resolution"
            raise ValueError(msg)
        entity = self._entity(topic, projects)
        qid = entity.qid
        missing: list[tuple[WikiProject, str]] = []
        mains = self._main_articles(topic, qid, projects, missing)
        if entity.linked_article is not None:
            mains[entity.linked_article.project] = entity.linked_article
        related: Mapping[WikiProject, tuple[ArticleRef, ...]] = {}
        if topic.bundle == "auto" and qid is not None:
            related = self._related_articles(qid, mains, projects)
        bundles = tuple(
            self._bundle(topic, project, mains[project], related.get(project, ()), missing)
            for project in projects
        )
        if _nothing_found(topic, qid, bundles):
            raise TopicNotFoundError(
                f"Nothing matches topic {topic.query!r}",
                topic_id=topic.id,
                query=topic.query,
                hint="Ask the user for a link to a Wikipedia article about the topic.",
            )
        return ResolvedTopic(
            topic_id=topic.id,
            query=topic.query,
            qid=qid,
            label=entity.label,
            bundles=bundles,
            missing_titles=tuple(missing),
            matched_in_english=entity.matched_in_english,
            description=entity.description,
            alternatives=entity.alternatives,
            method=entity.method,
            confidence=entity.confidence,
            runner_up=entity.runner_up,
        )

    # -- entity ---------------------------------------------------------------------------

    def _entity(self, topic: TopicSpec, projects: Sequence[WikiProject]) -> _Entity:
        """Pick the Wikidata item for a topic, or raise when the choice is not obvious.

        Sources, in order: a pinned ``qid``; the item of the article the user linked; a search
        by the query in its own language; the same search by ``query_en`` when the first finds
        nothing. Every search result goes through :meth:`_choose`, so a vague translation still
        ends in a question rather than a guess.
        """
        if topic.qid is not None:
            return self._pinned(topic.qid, topic.query_language)
        if topic.article_ref is not None:
            return self._linked(topic, *topic.article_ref)
        candidates = self._search(topic.query, topic.query_language)
        in_english = False
        if not candidates and topic.query_en and topic.query_language != _ENGLISH:
            candidates = self._search(topic.query_en, _ENGLISH)
            in_english = bool(candidates)
        if not candidates:
            return _Entity()
        choice = self._choose(candidates, projects, meaning=topic.meaning)
        chosen = choice.candidate
        if chosen is None:
            assert topic.id is not None
            raise ClarificationNeededError(
                f"Topic {topic.query!r} matches several Wikidata entities",
                topic_id=topic.id,
                candidates=candidates,
                coverage=self._coverage(candidates, projects),
                hint=(
                    "Set topics[].qid to the candidate the conversation clearly means, or ask "
                    "the user which one they mean."
                ),
            )
        label = chosen.label
        if in_english:
            local = self._wikidata.labels([chosen.qid], topic.query_language).get(chosen.qid)
            label = local or chosen.label
        return _Entity(
            qid=chosen.qid,
            label=label,
            description=chosen.description,
            matched_in_english=in_english,
            alternatives=tuple(c for c in candidates if c.qid != chosen.qid),
            method=choice.method,
            confidence=choice.confidence,
            runner_up=choice.runner_up,
        )

    def _search(self, text: str, language: str) -> tuple[EntityCandidate, ...]:
        """Wikidata search; a wording with a Wikipedia-style qualifier is retried without it.

        Agents often write the article title ("Go (programming language)"), which matches no
        Wikidata label. The retry finds "Go" and its homonyms, and :meth:`_choose` with the
        stated meaning then decides or asks, as for any other ambiguous word.
        """
        limit = self._settings.candidate_limit
        found = tuple(self._wikidata.search_entities(text, language, limit=limit))
        bare = _QUALIFIER.sub("", text).strip()
        if not found and bare and bare != text:
            found = tuple(self._wikidata.search_entities(bare, language, limit=limit))
        return found

    def _pinned(self, qid: str, language: str) -> _Entity:
        summary = self._wikidata.summary(qid, language)
        if summary is None:
            return _Entity(qid=qid, method="pinned")
        return _Entity(
            qid=qid, label=summary.label, description=summary.description, method="pinned"
        )

    def _linked(self, topic: TopicSpec, project: WikiProject, title: str) -> _Entity:
        """The item of the article the user linked; the article itself if it has none."""
        info = self._mediawiki.page_info(project, [title]).get(title)
        if info is None:
            assert topic.id is not None
            raise TopicNotFoundError(
                f"The linked article {title!r} does not exist in {project.domain}",
                topic_id=topic.id,
                query=topic.query,
                hint="Ask the user to check the link.",
            )
        if info.qid is not None:
            pinned = self._pinned(info.qid, topic.query_language)
            return replace(pinned, method="link")
        article = ArticleRef(project, info.title, ArticleRole.MAIN, ResolutionSource.MANUAL)
        return _Entity(label=info.title, linked_article=article, method="link")

    def _choose(
        self,
        candidates: Sequence[EntityCandidate],
        projects: Sequence[WikiProject],
        *,
        meaning: str | None,
    ) -> _Choice:
        """Pick the candidate, or return an empty choice when the agent has to ask.

        A single hit, or exactly one exact match (label or alias), is unambiguous. Several
        matches are homonyms, and nearly every common word has some (a band called
        "Astronomy", a novel called "Ртуть"), so two cases differ:

        * The agent stated what the user means (``meaning``): the candidates are scored by
          how well their English label and description match it, backed by coverage of the
          requested editions and by how many Wikipedias cover them
          (:func:`~wiki_interest.domain.entity_choice.choose_by_meaning`). A clear leader is
          picked (``auto``); close candidates go back to the agent.
        * No meaning was stated, so the agent considered the word unambiguous: the default is
          the exact match that covers the most requested editions, if Wikidata also ranks it
          first (:meth:`_break_tie`); otherwise the agent asks.

        The pick is never silent: every summary names the analysed entity with its
        description, how it was chosen and the other meanings.
        """
        if len(candidates) == 1:
            return _Choice(candidates[0])
        exact = [c for c in candidates if c.exact_label_match]
        if len(exact) == 1:
            return _Choice(exact[0])
        if meaning:
            return self._by_meaning(meaning, exact or list(candidates), projects)
        if not exact:
            return _Choice(None)
        default = self._break_tie(exact, projects)
        return _Choice(default, method="default") if default else _Choice(None)

    def _by_meaning(
        self, meaning: str, candidates: Sequence[EntityCandidate], projects: Sequence[WikiProject]
    ) -> _Choice:
        """Score homonyms against the stated meaning; pick a clear leader, else ask."""
        qids = [c.qid for c in candidates]
        english = self._wikidata.summaries(qids, _ENGLISH)
        links = self._wikidata.sitelinks(qids, projects)
        evidence = [
            CandidateEvidence(
                qid=c.qid,
                rank=rank,
                label_en=english[c.qid].label if c.qid in english else c.label,
                description_en=english[c.qid].description if c.qid in english else None,
                wikipedias=len(english[c.qid].languages) if c.qid in english else 0,
                covered=len(links.get(c.qid, {})),
                requested=len(projects),
            )
            for rank, c in enumerate(candidates)
        ]
        picked, ranked = choose_by_meaning(meaning, evidence, self._settings.choice)
        if picked is None:
            return _Choice(None)
        runner_up = ranked[1] if len(ranked) > 1 else None
        total = picked.score + (runner_up.score if runner_up else 0.0)
        return _Choice(
            next(c for c in candidates if c.qid == picked.qid),
            method="auto",
            confidence=round(picked.score / total, 2) if total > 0 else 1.0,
            runner_up=runner_up.qid if runner_up else None,
        )

    def _break_tie(
        self, exact: Sequence[EntityCandidate], projects: Sequence[WikiProject]
    ) -> EntityCandidate | None:
        """Default among homonyms when no meaning was stated: two signals must agree.

        It covers strictly more requested editions than any other exact match *and* Wikidata
        ranks it first among those with coverage ("English language" -> ``English`` in 5 of 5
        editions rather than ``English studies`` in 3 of 5). Otherwise ``None``.
        """
        links = self._wikidata.sitelinks([c.qid for c in exact], projects)
        coverage = {c.qid: len(links.get(c.qid, {})) for c in exact}
        covered = [c for c in exact if coverage[c.qid] > 0]
        if not covered:
            return None
        best = max(coverage[c.qid] for c in covered)
        leaders = [c for c in covered if coverage[c.qid] == best]
        # ``covered`` keeps Wikidata's ranking, so ``covered[0]`` is its top exact match.
        if len(leaders) == 1 and leaders[0] is covered[0]:
            return leaders[0]
        return None

    def _coverage(
        self, candidates: Sequence[EntityCandidate], projects: Sequence[WikiProject]
    ) -> dict[str, tuple[str, ...]]:
        links = self._wikidata.sitelinks([c.qid for c in candidates], projects)
        return {
            c.qid: tuple(p.domain for p in projects if p in links.get(c.qid, {}))
            for c in candidates
        }

    # -- main articles --------------------------------------------------------------------

    def _main_articles(
        self,
        topic: TopicSpec,
        qid: str | None,
        projects: Sequence[WikiProject],
        missing: list[tuple[WikiProject, str]],
    ) -> dict[WikiProject, ArticleRef | None]:
        """Find the main article per edition.

        Order: the Wikidata sitelink; the user's decision for an edition they were already
        asked about (a substitute page, or ``"skip"``); full-text search as the last resort.
        A decision wins over search so the run measures exactly what the user agreed to.
        """
        sitelinks: Mapping[WikiProject, str] = {}
        if qid is not None:
            sitelinks = self._wikidata.sitelinks([qid], projects).get(qid, {})
        mains: dict[WikiProject, ArticleRef | None] = {}
        for project in projects:
            title = sitelinks.get(project)
            choice = topic.substitutes.get(project.domain)
            if title is not None:
                mains[project] = ArticleRef(
                    project, title, ArticleRole.MAIN, ResolutionSource.SITELINK, qid=qid
                )
            elif choice == "skip":
                mains[project] = None
            elif isinstance(choice, SubstituteSpec):
                mains[project] = self._substitute(project, choice, missing)
            else:
                mains[project] = self._search_fallback(topic, qid, project)
        return mains

    def _substitute(
        self,
        project: WikiProject,
        choice: SubstituteSpec,
        missing: list[tuple[WikiProject, str]],
    ) -> ArticleRef | None:
        """Check that the chosen page exists and turn it into the edition's main article.

        A redirect is measured under its own title, not its target's: that is the whole
        point of choosing it (visits under the topic's name only).
        """
        info = self._mediawiki.page_info(project, [choice.title]).get(choice.title)
        if info is None:
            missing.append((project, choice.title))
            return None
        if choice.kind == "redirect" and info.redirect_title is not None:
            return ArticleRef(
                project, info.redirect_title, ArticleRole.MAIN, ResolutionSource.SUBSTITUTE
            )
        return ArticleRef(
            project, info.title, ArticleRole.MAIN, ResolutionSource.SUBSTITUTE, qid=info.qid
        )

    def _search_fallback(
        self, topic: TopicSpec, qid: str | None, project: WikiProject
    ) -> ArticleRef | None:
        """Search the edition by the user's local term, the entity's label, then the raw query.

        Full-text search returns whatever mentions the words, so a hit is accepted only when
        it is not bound to a *different* Wikidata item: searching Polish Wikipedia for
        "intermittent fasting" returned "Stres oksydacyjny" (oxidative stress, its own item),
        which would have silently analysed another subject. An honest "no article" is better.
        """
        queries: list[str] = []
        local_term = topic.local_terms.get(project.domain)
        if local_term:
            queries.append(local_term)
        if qid is not None:
            local = self._wikidata.labels([qid], project.language).get(qid)
            if local and local not in queries:
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
            if main is None or main.source is ResolutionSource.SUBSTITUTE:
                # A substitute describes another subject; its lead would pull that
                # subject's neighbourhood into the topic.
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
        """Assemble main + related + manual articles, apply exclusions, attach redirects.

        Only the main article gets its redirects: it is the one measured. Context articles
        are shown by their own title's views, which keeps the request count down.
        """
        assert topic.id is not None
        if main is not None and main.source is ResolutionSource.SUBSTITUTE:
            return self._substitute_bundle(topic, project, main)
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
            articles[0] = replace(articles[0], role=ArticleRole.MAIN)
        status = (
            BundleStatus.FOUND_VIA_SEARCH
            if articles[0].source is ResolutionSource.SEARCH_FALLBACK
            else BundleStatus.FOUND
        )
        measured = (self._with_redirects(project, articles[0]), *articles[1:])
        return TopicBundle(topic.id, project, status, measured)

    def _substitute_bundle(
        self, topic: TopicSpec, project: WikiProject, main: ArticleRef
    ) -> TopicBundle:
        """A bundle of the substitute page alone.

        Related or manual articles would blur what the user agreed to measure. Redirects to
        a broader or mentioning article are its own traffic and are kept; a redirect chosen
        as the substitute is measured alone by definition.
        """
        assert topic.id is not None
        choice = topic.substitutes[project.domain]
        assert isinstance(choice, SubstituteSpec)
        kind = SubstituteKind(choice.kind)
        article = main if kind is SubstituteKind.REDIRECT else self._with_redirects(project, main)
        return TopicBundle(
            topic.id, project, BundleStatus.SUBSTITUTE, (article,), substitute_kind=kind
        )

    def _manual_articles(
        self,
        topic: TopicSpec,
        project: WikiProject,
        existing: Sequence[ArticleRef],
        missing: list[tuple[WikiProject, str]],
    ) -> list[ArticleRef]:
        """Validate user-supplied titles and add the existing ones as context."""
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


def _nothing_found(topic: TopicSpec, qid: str | None, bundles: Sequence[TopicBundle]) -> bool:
    """No entity, no article anywhere, and nothing the user supplied to measure instead.

    Titles or decisions from the user mean they know what they are after; only a topic that
    matched nothing at all, with nothing to fall back on, is reported as not found.
    """
    if qid is not None or any(b.status is not BundleStatus.NOT_FOUND for b in bundles):
        return False
    return not topic.substitutes and not any(topic.extra_titles.values())
