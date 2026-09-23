"""Use-case: reduce each analysed pair to size, momentum and trust, and draw the conclusion.

:mod:`wiki_interest.domain.assessment` holds the rules; this module applies them to an
:class:`~wiki_interest.application.analysis.AnalysisResult`:

* every (topic, edition) pair gets a :class:`PairAssessment`: its size against the others,
  its momentum, how it fared against its whole edition, whether the last months confirm the
  direction, the state of its data, and its decision outcome;
* the run as a whole gets a :class:`Conclusion`: which audience deserves the next check and
  why, the sentence the answer ends with.

Everything stays language-neutral (keys and raw numbers) so the summary builder can put it
into any report language, and a cheap agent never has to reconcile five percentages itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from wiki_interest.application.analysis import AnalysisResult, PairAnalysis
from wiki_interest.domain.assessment import (
    AssessmentSettings,
    EditionRelation,
    Momentum,
    RelativeSize,
    Robustness,
    edition_relation,
    momentum,
    outcome,
    relative_size,
    robustness,
)
from wiki_interest.domain.models import (
    CheckStatus,
    ReliabilityLevel,
    TrendMetrics,
    WikiProject,
)

__all__ = [
    "Conclusion",
    "Evidence",
    "PairAssessment",
    "assess",
    "conclude",
    "headline_growth",
]

_CONCERNS = frozenset({CheckStatus.WARN, CheckStatus.FAIL})


@dataclass(frozen=True, slots=True)
class Evidence:
    """One fact about a pair's data, before it is put into words.

    Only what a reader can check without statistics: how many months, whether any are
    missing, how much of the traffic fell on burst days, and the concerns the reliability
    rules raised (a tiny audience, bots, a doubtful article). Test statistics stay in the
    reliability section of ``method.md``.

    Attributes:
        key: Message key: ``evidence.<name>`` for the short statements, or a reliability
            reason key for a concern.
        params: Template values.
        concern: Whether it lowers trust; concerns are listed first.
    """

    key: str
    params: Mapping[str, float | int | str] = field(default_factory=dict)
    concern: bool = False


@dataclass(frozen=True, slots=True)
class PairAssessment:
    """The decision view of one (topic, edition).

    Attributes:
        measured: Whether the edition had an article to measure.
        per_million: Mean share of the edition's views, per million.
        views_avg: Mean monthly views of the article.
        size: Size against the largest pair of the report; ``None`` with nothing to compare.
        momentum: Where the analysed series (share, else views) is heading.
        change: The change behind ``momentum``; ``basis`` says which comparison it is.
        article_change: The article's own views over the same months as ``edition_change``.
        edition_change: The whole edition's views.
        share_change: The topic's share of the edition over those months.
        relation: Whether the topic gained or lost ground inside its edition.
        relation_basis: Months compared for the three changes above (``yoy`` or ``halves``).
        recent_months: Length of the recent window (the last months against the same months
            a year earlier); the three changes below are over it.
        recent_article: Recent change of the article's views.
        recent_edition: Recent change of the whole edition's views.
        recent_shift: Recent change of the share (of views without normalisation).
        robustness: Whether the recent months confirm the long-term direction.
        robustness_reason: Why it cannot be judged, for ``unknown``: ``low_trust``,
            ``low_volume``, ``no_recent`` or ``no_trend``.
        confidence: Trust level from the reliability rules.
        evidence: The state of the data, concerns first.
        outcome: Decision outcome key (see :func:`wiki_interest.domain.assessment.outcome`),
            or ``no_article``.
        measures_topic: False when another subject's article stands in for the topic.
    """

    topic_id: str
    project: WikiProject
    measured: bool
    per_million: float | None
    views_avg: float | None
    size: RelativeSize | None
    momentum: Momentum
    change: float | None
    basis: str | None
    article_change: float | None
    edition_change: float | None
    share_change: float | None
    relation: EditionRelation | None
    relation_basis: str | None
    recent_months: int | None
    recent_article: float | None
    recent_edition: float | None
    recent_shift: float | None
    robustness: Robustness
    robustness_reason: str | None
    confidence: ReliabilityLevel
    evidence: tuple[Evidence, ...]
    outcome: str
    measures_topic: bool = True


@dataclass(frozen=True, slots=True)
class Conclusion:
    """What the whole report concludes, as a key and the pair it points to.

    Keys: ``strong`` (the largest audience also grows), ``emerging`` (only smaller ones
    grow), ``no_growth`` (nothing grows; the largest is the one to research further;
    ``no_growth_ranked`` when the ranking chose it, ``no_growth_split`` when the ranking
    put another audience first),
    ``single_<growing|flat|declining>`` for a report about one audience, ``unknown`` (no
    trend measurable), ``low_trust`` (no audience can carry a conclusion), ``none``
    (nothing was measured).
    """

    key: str
    candidate: PairAssessment | None = None
    largest: PairAssessment | None = None
    """For ``no_growth_split``: the audience with the largest interest, when the ranking put
    another one first."""


def headline_growth(metrics: TrendMetrics) -> tuple[float | None, str | None]:
    """The change a report leads with, and its basis: year over year, halves, or the slope."""
    if metrics.growth_yoy is not None:
        return metrics.growth_yoy, "yoy"
    if metrics.growth_halves is not None:
        return metrics.growth_halves, "halves"
    if metrics.slope_per_year is not None:
        return metrics.slope_per_year, "slope"
    return None, None


def assess(
    analysis: AnalysisResult,
    *,
    normalised: bool,
    settings: AssessmentSettings | None = None,
) -> tuple[PairAssessment, ...]:
    """Assess every pair of ``analysis``, in its order.

    Size is compared on the share of attention when normalising (editions of different size
    are then comparable) and on monthly views otherwise; only pairs that measure the topic
    itself take part, so a broader substitute article never becomes "the largest audience".
    """
    rules = settings or AssessmentSettings()
    sizes = {
        (p.topic_id, p.project): _size_value(p, normalised)
        for p in analysis.pairs
        if p.metrics is not None and p.measures_topic
    }
    known = [v for v in sizes.values() if v is not None]
    largest = max(known) if len(known) > 1 else None
    return tuple(
        _assess_pair(pair, sizes.get((pair.topic_id, pair.project)), largest, normalised, rules)
        for pair in analysis.pairs
    )


def conclude(
    assessments: Sequence[PairAssessment],
    ranking: Sequence[tuple[str, WikiProject]] = (),
) -> Conclusion:
    """The report's conclusion by fixed rules; see :class:`Conclusion` for the keys.

    Args:
        assessments: Every pair of the run.
        ranking: (topic, edition) pairs best first, for a ranking question. The candidate is
            then taken in that order rather than by size, so the conclusion names the audience
            the ranking puts first instead of contradicting it.
    """
    measured = [a for a in assessments if a.measured and a.measures_topic]
    if not measured:
        return Conclusion("none")
    trusted = [a for a in measured if a.outcome != "low_trust"]
    if not trusted:
        return Conclusion("low_trust")
    known = [a for a in trusted if a.momentum is not Momentum.UNKNOWN]
    if not known:
        return Conclusion("unknown")
    if len(measured) == 1:
        return Conclusion(f"single_{known[0].momentum.value}", known[0])
    order = {pair: index for index, pair in enumerate(ranking)}
    growing = [a for a in known if a.momentum is Momentum.GROWING]
    if growing:
        best = _pick(growing, order)
        return Conclusion("emerging" if best.size is RelativeSize.SMALLER else "strong", best)
    return _no_growth(known, order)


def _pick(
    items: Sequence[PairAssessment], order: Mapping[tuple[str, WikiProject], int]
) -> PairAssessment:
    """The first by the ranking when there is one, else the largest."""
    if order:
        return min(items, key=lambda a: order.get((a.topic_id, a.project), len(order)))
    return max(items, key=_size_key)


def _no_growth(
    known: Sequence[PairAssessment], order: Mapping[tuple[str, WikiProject], int]
) -> Conclusion:
    """Nothing grows: the audience to research further, and why it was chosen."""
    if not order:
        return Conclusion("no_growth", _pick(known, order))
    first, largest = _pick(known, order), max(known, key=_size_key)
    if first is largest:
        return Conclusion("no_growth_ranked", first)
    # The ranking weighs stability and decline too; when it disagrees with size, both are
    # named rather than one silently overruling the other.
    return Conclusion("no_growth_split", first, largest)


def _size_key(assessment: PairAssessment) -> float:
    value = assessment.per_million if assessment.per_million is not None else assessment.views_avg
    return value if value is not None else float("-inf")


def _size_value(pair: PairAnalysis, normalised: bool) -> float | None:
    metrics = pair.metrics
    if metrics is None:
        return None
    return metrics.per_million_avg if normalised else metrics.views_avg


def _assess_pair(
    pair: PairAnalysis,
    size_value: float | None,
    largest: float | None,
    normalised: bool,
    rules: AssessmentSettings,
) -> PairAssessment:
    metrics = pair.metrics
    level = pair.reliability.level
    if metrics is None:
        return PairAssessment(
            topic_id=pair.topic_id,
            project=pair.project,
            measured=False,
            per_million=None,
            views_avg=None,
            size=None,
            momentum=Momentum.UNKNOWN,
            change=None,
            basis=None,
            article_change=None,
            edition_change=None,
            share_change=None,
            relation=None,
            relation_basis=None,
            recent_months=None,
            recent_article=None,
            recent_edition=None,
            recent_shift=None,
            robustness=Robustness.UNKNOWN,
            robustness_reason=None,
            confidence=level,
            evidence=(),
            outcome="no_article",
            measures_topic=pair.measures_topic,
        )
    change, basis = headline_growth(metrics)
    trend = momentum(change, metrics.trend_direction, rules)
    size = relative_size(size_value, largest, rules) if pair.measures_topic else None
    edition = pair.findings.edition
    recent, recent_edition = pair.findings.recent, pair.findings.recent_edition
    shift = _recent_shift(
        recent.change if recent else None,
        recent_edition.change if recent_edition else None,
        normalised=normalised,
    )
    reliable = level is not ReliabilityLevel.LOW
    steady = robustness(
        trend, shift, reliable=reliable, views_avg=metrics.views_avg, settings=rules
    )
    reason = None
    if steady is Robustness.UNKNOWN:
        reason = _unknown_reason(trend, reliable, metrics.views_avg, rules)
    return PairAssessment(
        topic_id=pair.topic_id,
        project=pair.project,
        measured=True,
        per_million=metrics.per_million_avg,
        views_avg=metrics.views_avg,
        size=size,
        momentum=trend,
        change=change,
        basis=basis,
        article_change=edition.article_change if edition else None,
        edition_change=edition.edition_change if edition else None,
        share_change=edition.share_change if edition else None,
        relation=edition_relation(edition.share_change, rules) if edition else None,
        relation_basis=edition.basis if edition else None,
        recent_months=recent.months if recent else None,
        recent_article=recent.change if recent else None,
        recent_edition=recent_edition.change if recent_edition else None,
        recent_shift=shift,
        robustness=steady,
        robustness_reason=reason,
        confidence=level,
        evidence=_evidence(pair),
        outcome=outcome(
            size,
            trend,
            trusted=reliable,
            measures_topic=pair.measures_topic,
        ),
        measures_topic=pair.measures_topic,
    )


_SHORT_EVIDENCE: Mapping[tuple[str, bool], str] = {
    ("window_length", False): "evidence.months",
    ("window_length", True): "evidence.months_short",
    ("completeness", False): "evidence.no_gaps",
    ("completeness", True): "evidence.gaps",
    ("spikes", False): "evidence.spikes_ok",
    ("spikes", True): "evidence.spikes_high",
}
"""Checks restated as short evidence, by (check name, is a concern). Other checks appear
only as concerns, with their full reliability message."""
_SILENT_CHECKS = frozenset({"trend"})
"""Checks left out of the evidence: whether the trend is real is what the robustness line
answers in plain words; the test itself is in the detailed reliability section."""
_EVIDENCE_ORDER: Mapping[str, int] = {
    "evidence.months": 1,
    "evidence.months_short": 1,
    "evidence.no_gaps": 2,
    "evidence.gaps": 2,
    "evidence.spikes_ok": 3,
    "evidence.spikes_high": 3,
}
"""Reading order: the window, its gaps, then the bursts."""


def _recent_shift(
    article: float | None, edition: float | None, *, normalised: bool
) -> float | None:
    """Recent change of the share: the article's change against its edition's."""
    if article is None:
        return None
    if not normalised:
        return article
    if edition is None or edition <= -1.0:
        return None
    return (1.0 + article) / (1.0 + edition) - 1.0


def _unknown_reason(
    trend: Momentum,
    reliable: bool,
    views_avg: float | None,
    rules: AssessmentSettings,
) -> str:
    """Why robustness cannot be judged, in the order a reader would fix it."""
    if not reliable:
        return "low_trust"
    if trend is Momentum.UNKNOWN:
        return "no_trend"
    if views_avg is None or views_avg < rules.min_recent_views:
        return "low_volume"
    return "no_recent"  # the only case left: no comparison with a year earlier


def _evidence(pair: PairAnalysis) -> tuple[Evidence, ...]:
    """The state of the data in plain facts, concerns first."""
    items: list[Evidence] = []
    for check in pair.reliability.checks:
        if check.status is CheckStatus.INFO or check.name in _SILENT_CHECKS:
            continue
        concern = check.status in _CONCERNS
        key = _SHORT_EVIDENCE.get((check.name, concern))
        if key is not None:
            items.append(Evidence(key, dict(check.params), concern))
        elif concern:
            items.append(Evidence(check.reason_key, dict(check.params), concern=True))
    return tuple(sorted(items, key=lambda e: (not e.concern, _EVIDENCE_ORDER.get(e.key, 0))))
