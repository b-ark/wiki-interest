"""Use-case: the observations of a run, from the fetched series to what ``facts.json`` lists.

The detectors (:mod:`wiki_interest.domain.observations`) read the article's and the edition's
monthly views over up to six years: the season, the steps and the long view need years to be
told apart from noise, and they are the report's context. What the report answers (the
comparisons, the verdict of each language) reads the analysis window alone: the period the
user named, or the last 24 complete months. Editions measured through a substitute article,
or without an article, get a caution the text must carry.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date

from wiki_interest.application.loading import LoadedSeries
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.application.window import trust_observation, trust_out
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.contracts.summary import AssessmentOut, ObservationOut, QuotedNumber
from wiki_interest.domain.models import BundleStatus
from wiki_interest.domain.observations import (
    MONTH_NAMES,
    Observation,
    ObservationSettings,
    PairHistory,
    Weight,
    edition_name,
    observe,
)
from wiki_interest.domain.trust import BreakpointVerdict, Trust, WindowTrend

__all__ = [
    "observation_start",
    "outcome_cautions",
    "pair_histories",
    "run_observations",
    "to_out",
]

_YEAR = 12
_SUBSTITUTE = re.compile(r"\((.+)\)\s*$")
"""The substitute article in a pair label: ``pl.wikipedia (Post)``."""


def observation_start(
    request: AnalysisRequest, period: Period, settings: ObservationSettings | None = None
) -> date:
    """First month the observations read: six years before the period ends.

    A period the user named that starts earlier is read from its start.
    """
    years = (settings or ObservationSettings()).observe_years
    end = period.end
    months = end.year * _YEAR + end.month - 1 - (years * _YEAR - 1)
    six_years = date(months // _YEAR, months % _YEAR + 1, 1)
    return min(six_years, period.start) if request.period is not None else six_years


def pair_histories(
    loaded: Sequence[LoadedSeries], resolved: Sequence[ResolvedTopic]
) -> list[PairHistory]:
    """The long monthly series of every pair with an article, as the detectors read them.

    Args:
        loaded: The fetched series, with the long window (``long_views``, ``long_total``).
        resolved: The topics, for their labels and substitute articles.
    """
    labels = {t.topic_id: t.label or t.query for t in resolved}
    substitutes = {
        (t.topic_id, b.project.domain): b.main.title
        for t in resolved
        for b in t.bundles
        if b.status is BundleStatus.SUBSTITUTE and b.main is not None
    }
    histories: list[PairHistory] = []
    for item in loaded:
        views, total = item.long_views, item.long_total
        if item.main_views is None or views is None or total is None:
            continue
        topic = labels.get(item.topic_id, item.topic_id)
        substitute = substitutes.get((item.topic_id, item.project.domain))
        if substitute:
            topic = f"{topic} (measured through the article «{substitute}»)"
        by_month = dict(zip(total.periods, total.values, strict=True))
        histories.append(
            PairHistory(
                topic_id=item.topic_id,
                topic=topic,
                project=item.project.domain,
                months=views.periods,
                views=views.values,
                edition=tuple(by_month.get(m) for m in views.periods),
                substitute=substitute,
            )
        )
    return histories


def run_observations(
    histories: Sequence[PairHistory],
    request: AnalysisRequest,
    period: Period,
    trends: Mapping[str, WindowTrend] | None = None,
    trust: Mapping[str, Trust] | None = None,
) -> list[Observation]:
    """The detectors' observations for every pair with an article.

    Args:
        histories: The pairs' long series (:func:`pair_histories`).
        request: The request.
        period: The analysis window.
        trends: The window's verdict of each pair (``read_trends``).
        trust: The trust in each verdict (``read_trust``): a ``trust:`` observation per
            pair, and each step says whether it looks technical.
    """
    found = observe(histories, window_start=period.start, trends=trends)
    if trust:
        found = _with_trust(found, histories, trust)
    if request.normalization == "absolute":
        found.insert(0, _RAW_VIEWS)
    found[:0] = _period_cautions(request.period, period)
    return found


def _with_trust(
    found: list[Observation], histories: Sequence[PairHistory], trust: Mapping[str, Trust]
) -> list[Observation]:
    """Each pair's trust after its verdict, and each step's check against the control."""
    names = {h.pair: (h.topic, h.project) for h in histories}
    out: list[Observation] = []
    for o in found:
        pair = o.pair or ""
        checked = _checked_step(o, trust[pair]) if o.kind == "step" and pair in trust else o
        out.append(checked)
        if o.kind == "trend" and pair in trust and pair in names:
            topic, project = names[pair]
            out.append(trust_observation(pair, topic, project, trust_out(trust[pair])))
    return out


def _checked_step(step: Observation, trust: Trust) -> Observation:
    """``step`` with what the control articles and the move log say of it."""
    found = next((b for b in trust.breakpoints if b.month == step.month), None)
    if found is None or step.month is None:
        return step
    if found.verdict is BreakpointVerdict.ARTIFACT:
        why = (
            "the article was renamed then"
            if found.renamed
            else "the edition's control articles moved the same way that month"
        )
        tail = f" Probably a technical change, not interest: {why}."
    elif found.verdict is BreakpointVerdict.REAL:
        tail = " The edition's control articles did not move that month: the change is the topic's."
    else:
        return step
    return replace(step, statement=step.statement + tail)


def _period_cautions(requested: Period | None, period: Period) -> list[Observation]:
    """Why the analysed period is not the one the user asked for, as cautions the text carries.

    A line in the chat answer was dropped whenever the agent left its label untranslated, and
    the user who asked "since 2010" never read why the report starts in 2015 (stage13). A
    caution is written by the agent itself, and the check makes sure it is.
    """
    if requested is None or requested.start >= period.start:
        # The last month cut off as incomplete is a line of the chat answer, not a caution:
        # it would ask every text about a named period to explain an unfinished month.
        return []
    return [
        Observation(
            "caution:period_start",
            "caution",
            None,
            Weight.CAUTION,
            f"The user asked from {_month(requested.start)}, but Wikipedia pageview data start "
            f"in {_month(period.start)}: the analysis begins there, and nothing can be said "
            "about the years before.",
        )
    ]


def _month(day: date) -> str:
    """``July 2015``."""
    return f"{MONTH_NAMES[day.month - 1]} {day.year}"


_RAW_VIEWS = Observation(
    "caution:raw_views",
    "caution",
    None,
    Weight.CAUTION,
    "The user asked for raw views: the report's charts and table show the article's own views, "
    "not adjusted for the size of each edition, so a bigger edition shows more views without "
    "more interest. The observations still read the attention share, which is adjusted.",
)


def outcome_cautions(
    assessments: Sequence[AssessmentOut], topics: dict[str, str]
) -> list[Observation]:
    """Cautions for editions without an article or measured through a substitute.

    Args:
        assessments: The run's assessments (their outcomes).
        topics: Topic id -> label.
    """
    out: list[Observation] = []
    for a in assessments:
        language = a.project.split(".")[0]
        pair = f"{a.topic_id}/{language}"
        ed = edition_name(a.project)
        topic = topics.get(a.topic_id, a.topic_id)
        if a.outcome == "no_article":
            text = (
                f"{ed} has no article on {topic}, so there is nothing to measure there: that is "
                "no article, not no interest."
            )
        elif a.outcome == "substitute":
            title = _SUBSTITUTE.search(a.label)
            article = f"«{title.group(1)}»" if title else f"({a.label})"
            text = (
                f"{ed} has no article on {topic} itself; its numbers come from the broader "
                f"article {article}, which also counts readers of other things: name "
                f"{article} whenever this edition is mentioned."
            )
        elif a.outcome == "low_trust":
            text = f"The data for {topic} in {ed} are too weak for a conclusion."
        else:
            continue
        statement = text[0].upper() + text[1:]
        out.append(Observation(f"caution:{pair}", "caution", pair, Weight.CAUTION, statement))
    return out


def to_out(observations: Sequence[Observation]) -> list[ObservationOut]:
    """The observations as the summary stores them."""
    return [
        ObservationOut(
            id=o.id,
            kind=o.kind,
            pair=o.pair,
            weight=o.weight.value,
            statement=o.statement,
            numbers=[QuotedNumber(value=q.value, percent=q.percent) for q in o.numbers],
        )
        for o in observations
    ]
