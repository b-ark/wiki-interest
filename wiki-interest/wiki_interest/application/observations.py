"""Use-case: the observations of a run, from the fetched series to what ``facts.json`` lists.

The detectors (:mod:`wiki_interest.domain.observations`) read the article's and the edition's
monthly views over up to six years, whatever period the report shows: a trend, a wave, a
season or a step needs years to be told apart from noise. A period the user named is read on
its own, the season still on the whole window. Editions measured through a substitute
article, or without an article, get a caution the text must carry.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date

from wiki_interest.application.loading import LoadedSeries
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.contracts.summary import AssessmentOut, ObservationOut, QuotedNumber
from wiki_interest.domain.models import BundleStatus
from wiki_interest.domain.observations import (
    Observation,
    ObservationSettings,
    PairHistory,
    Weight,
    edition_name,
    observe,
)

__all__ = [
    "observation_start",
    "outcome_cautions",
    "pair_histories",
    "run_observations",
    "to_out",
    "trend_start",
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
            )
        )
    return histories


def trend_start(request: AnalysisRequest, period: Period) -> date | None:
    """First month the trend detectors read: a period the user named is read on its own."""
    return period.start if request.period is not None else None


def run_observations(
    histories: Sequence[PairHistory], request: AnalysisRequest, period: Period
) -> list[Observation]:
    """The detectors' observations for every pair with an article.

    Args:
        histories: The pairs' long series (:func:`pair_histories`).
        request: The request: a named period is read on its own.
        period: The analysed period.
    """
    found = observe(histories, trend_start=trend_start(request, period))
    if request.normalization == "absolute":
        found.insert(0, _RAW_VIEWS)
    return found


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
