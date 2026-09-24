"""Use-case: when an edition has no article on a topic, find what could stand in and ask.

A missing article is a fact about the edition, not a measurement of interest, and there is no
neutral way to replace it: a redirect under the topic's name undercounts, a broader article
overcounts, an article that mentions the topic measures something else. Which of these is
acceptable depends on the user's question, so the pipeline stops *before* fetching any
series and lists the options with their monthly views; the user picks one (or leaves the
edition out) and the next run measures exactly that. This keeps the expensive part of a run,
and the agent's turns, for a question the user has actually agreed to.

Options, in the order they are offered:

1. **Redirect**: a page under the topic's local name that redirects elsewhere, often into a
   section of a broader article. Pageviews of the redirect itself are people who arrived by
   that exact name.
2. **Broader article**: the article of a Wikidata parent (``subclass of``, ``part of``).
3. **Mention**: articles whose text contains the topic's local name as a phrase, offered
   only when there is no redirect and no broader article: winter swimming mentions
   intermittent fasting, but its readers did not come for it.
4. **Skip**: leave the edition out and report "no article".

Local names come from the request (``topics[].local_terms``, typically the agent's
translation), from Wikidata labels *in that language only*, and from the query itself when it
is written in that language. An English label is never used to search a Polish edition: an
English phrase there is almost always a bibliography entry.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date
from statistics import fmean
from typing import Literal

from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.contracts.request import AnalysisRequest, Period, TopicSpec
from wiki_interest.domain.models import (
    Access,
    Agent,
    BundleStatus,
    Granularity,
    WikiProject,
    Window,
)
from wiki_interest.ports.mediawiki import MediaWikiGateway
from wiki_interest.ports.pageviews import PageviewsSource
from wiki_interest.ports.wikidata import EntitySummary, WikidataGateway

__all__ = [
    "CoverageAdvisor",
    "CoverageGap",
    "CoverageOption",
    "CoverageSettings",
    "OptionKind",
]

OptionKind = Literal["redirect", "broader", "mention", "skip"]


@dataclass(frozen=True, slots=True)
class CoverageSettings:
    """Tunables of the gap search.

    Attributes:
        broader_properties: Wikidata properties that lead from the topic to a wider subject
            (subclass of, part of).
        max_broader: How many broader articles to offer.
        max_mentions: How many mentioning articles to offer; more is a wall of text.
        mention_candidates: Search hits fetched per local name before de-duplication.
        views_months: Months of history behind the views shown next to each option.
    """

    broader_properties: tuple[str, ...] = ("P279", "P361")
    max_broader: int = 2
    max_mentions: int = 3
    mention_candidates: int = 6
    views_months: int = 12


_DEFAULT_SETTINGS = CoverageSettings()


@dataclass(frozen=True, slots=True)
class CoverageOption:
    """One thing that could stand in for the missing article.

    Attributes:
        kind: What the option is; see the module docstring.
        title: Page whose views would be measured (the redirect itself for ``redirect``);
            ``None`` for ``skip``.
        target: Article a redirect leads to.
        section: Section of ``target`` a redirect points into, if any.
        snippet: Passage around the mention, for ``mention``.
        views_avg: Mean monthly views of ``title`` over the last ``views_months`` complete
            months, or ``None`` when there is no data (or nothing to measure).
    """

    kind: OptionKind
    title: str | None = None
    target: str | None = None
    section: str | None = None
    snippet: str | None = None
    views_avg: float | None = None


@dataclass(frozen=True, slots=True)
class CoverageGap:
    """An edition without an article on a topic, and what the user can do about it.

    Attributes:
        topic_id: Topic identifier from the request.
        query: The user's wording of the topic.
        project: The edition without an article.
        terms: Local names that were searched for; empty when none was known, which the
            question states so the agent can supply one.
        options: Choices in the order they are offered; always ends with ``skip``.
        entity: What the topic resolved to and where it has articles, so the user can check
            the entity before choosing; ``None`` when no Wikidata item matched at all.
        matched_in_english: Whether the entity was found by the English wording only.
    """

    topic_id: str
    query: str
    project: WikiProject
    terms: tuple[str, ...]
    options: tuple[CoverageOption, ...]
    entity: EntitySummary | None = None
    matched_in_english: bool = False


class CoverageAdvisor:
    """Finds editions without an article and the options that could stand in for it."""

    def __init__(
        self,
        wikidata: WikidataGateway,
        mediawiki: MediaWikiGateway,
        pageviews: PageviewsSource,
        *,
        settings: CoverageSettings = _DEFAULT_SETTINGS,
    ) -> None:
        self._wikidata = wikidata
        self._mediawiki = mediawiki
        self._pageviews = pageviews
        self._settings = settings

    def gaps(
        self, request: AnalysisRequest, resolved: Sequence[ResolvedTopic], today: date
    ) -> tuple[CoverageGap, ...]:
        """List every (topic, edition) without an article that the user has not decided on.

        An edition counts as decided once ``topics[].substitutes`` names it, even if the
        chosen page later turns out to be missing: asking again would loop, and the report
        lists the missing title instead.

        Args:
            request: The request, for decisions, local names and traffic filters.
            resolved: Topics as resolved, in request order.
            today: Reference date for the window behind the views of each option.

        Returns:
            The open gaps in request order; empty when the run can proceed.
        """
        specs = {spec.id: spec for spec in request.topics}
        window = self._window(today)
        traffic = (Access(request.access), Agent(request.agent))
        gaps: list[CoverageGap] = []
        for topic in resolved:
            spec = specs[topic.topic_id]
            open_projects = [
                bundle.project
                for bundle in topic.bundles
                if bundle.status is BundleStatus.NOT_FOUND
                and bundle.project.domain not in spec.substitutes
            ]
            if not open_projects:
                continue
            entity = (
                self._wikidata.summary(topic.qid, request.report.language)
                if topic.qid is not None
                else None
            )
            gaps.extend(
                replace(
                    self._gap(spec, topic, project, window, traffic),
                    entity=entity,
                    matched_in_english=topic.matched_in_english,
                )
                for project in open_projects
            )
        return tuple(gaps)

    # -- one gap --------------------------------------------------------------------------

    def _gap(
        self,
        spec: TopicSpec,
        topic: ResolvedTopic,
        project: WikiProject,
        window: Window,
        traffic: tuple[Access, Agent],
    ) -> CoverageGap:
        terms = self._local_terms(spec, topic.qid, project)
        options: list[CoverageOption] = []
        options += self._redirects(project, terms)
        if topic.qid is not None:
            options += self._broader(project, topic.qid, _titles(options))
        if not options:
            options += self._mentions(project, terms, set())
        measured = [self._with_views(project, option, window, traffic) for option in options]
        return CoverageGap(
            topic_id=topic.topic_id,
            query=spec.query,
            project=project,
            terms=terms,
            options=(*measured, CoverageOption(kind="skip")),
        )

    def _local_terms(
        self, spec: TopicSpec, qid: str | None, project: WikiProject
    ) -> tuple[str, ...]:
        """Names of the topic in the edition's language, most trusted first, no duplicates."""
        candidates: list[str | None] = [spec.local_terms.get(project.domain)]
        if qid is not None:
            labels = self._wikidata.labels([qid], project.language, fallback=False)
            candidates.append(labels.get(qid))
        if spec.query_language == project.language:
            candidates.append(spec.query)
        terms: list[str] = []
        for term in candidates:
            cleaned = (term or "").strip()
            if cleaned and cleaned.casefold() not in {t.casefold() for t in terms}:
                terms.append(cleaned)
        return tuple(terms)

    def _redirects(self, project: WikiProject, terms: Sequence[str]) -> list[CoverageOption]:
        if not terms:
            return []
        infos = self._mediawiki.page_info(project, terms)
        options: list[CoverageOption] = []
        for term in terms:
            info = infos.get(term)
            if info is None or info.redirect_title is None:
                continue
            if info.redirect_title in _titles(options):
                continue
            options.append(
                CoverageOption(
                    kind="redirect",
                    title=info.redirect_title,
                    target=info.title,
                    section=info.fragment,
                )
            )
        return options

    def _broader(self, project: WikiProject, qid: str, taken: set[str]) -> list[CoverageOption]:
        related = self._wikidata.related_entities(qid, self._settings.broader_properties)
        properties = self._settings.broader_properties
        parents = list(dict.fromkeys(q for prop in properties for q in related.get(prop, ())))
        if not parents:
            return []
        links = self._wikidata.sitelinks(parents, [project])
        seen = set(taken)
        options: list[CoverageOption] = []
        for parent in parents:
            title = links.get(parent, {}).get(project)
            if title is None or title in seen:
                continue
            seen.add(title)
            options.append(CoverageOption(kind="broader", title=title))
            if len(options) == self._settings.max_broader:
                break
        return options

    def _mentions(
        self, project: WikiProject, terms: Sequence[str], taken: set[str]
    ) -> list[CoverageOption]:
        seen = set(taken)
        options: list[CoverageOption] = []
        for term in terms:
            hits = self._mediawiki.mentions(project, term, limit=self._settings.mention_candidates)
            for hit in hits:
                if hit.title in seen:
                    continue
                seen.add(hit.title)
                options.append(CoverageOption(kind="mention", title=hit.title, snippet=hit.snippet))
                if len(options) == self._settings.max_mentions:
                    return options
        return options

    # -- views ----------------------------------------------------------------------------

    def _window(self, today: date) -> Window:
        period = Period.last_full_months(today, self._settings.views_months)
        return Window(Granularity.MONTHLY, period.start, period.end)

    def _with_views(
        self,
        project: WikiProject,
        option: CoverageOption,
        window: Window,
        traffic: tuple[Access, Agent],
    ) -> CoverageOption:
        if option.title is None:
            return option
        access, agent = traffic
        series = self._pageviews.per_article(
            project, option.title, window, access=access, agent=agent
        )
        observed = series.observed
        return replace(option, views_avg=fmean(observed) if observed else None)


def _titles(options: Sequence[CoverageOption]) -> set[str]:
    return {o.title for o in options if o.title is not None}
