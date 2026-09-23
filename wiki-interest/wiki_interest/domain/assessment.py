"""Decision layer: what one (topic, edition) looks like to someone choosing where to act.

The metrics answer many questions at once (a share, three growth figures, a p-value, a
level of trust). A reader deciding between audiences needs three answers: how big the
interest is compared with the alternatives, where it is heading, and whether the topic keeps
up with its edition. This module reduces the metrics to those answers with fixed, documented
rules, and maps the combination of size and momentum to an outcome, so every report says the
same thing about the same numbers and no reader (or agent) has to weigh five percentages.

The functions produce categories, never prose; the summary builder puts them into words.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from wiki_interest.domain.models import TrendDirection

__all__ = [
    "AssessmentSettings",
    "EditionRelation",
    "Momentum",
    "RelativeSize",
    "Robustness",
    "edition_relation",
    "momentum",
    "outcome",
    "relative_size",
    "robustness",
]


class Momentum(StrEnum):
    """Where the interest is heading over the analysed window."""

    GROWING = "growing"
    FLAT = "flat"
    """No clear trend: the test is not significant, or the change is too small to matter."""
    DECLINING = "declining"
    UNKNOWN = "unknown"
    """The window is too short to measure a change."""


class RelativeSize(StrEnum):
    """How large the interest is against the largest one in the same report."""

    LARGEST = "largest"
    SIMILAR = "similar"
    """Within :attr:`AssessmentSettings.similar_size_ratio` of the largest."""
    SMALLER = "smaller"


class EditionRelation(StrEnum):
    """Whether the topic keeps up with its whole edition."""

    GAINING = "gaining"
    """The article does better than its edition: the topic's share of attention grows."""
    IN_LINE = "in_line"
    LOSING = "losing"
    """The article does worse than its edition: the topic's share of attention shrinks."""


class Robustness(StrEnum):
    """Whether the last months confirm the long-term direction."""

    CONFIRMED = "confirmed"
    """Recent months move the same way (or, without a trend, stay flat too)."""
    MIXED = "mixed"
    """Recent months are flatter than the trend, or move while the trend is flat."""
    REVERSING = "reversing"
    """Recent months move against the trend."""
    UNKNOWN = "unknown"
    """No recent comparison, no trend, or data too weak or too small to judge."""


@dataclass(frozen=True, slots=True)
class AssessmentSettings:
    """Cut-offs of the decision layer; documented in ``references/methodology.md``.

    Attributes:
        min_momentum: Smallest change (share, or views without normalisation) called growth
            or decline; a significant trend of -2 % is not worth acting on.
        similar_size_ratio: The largest interest divided by another below this makes them
            similar, so a 10 % lead is not presented as a clear winner.
        min_share_shift: Smallest change of the share that counts as gaining or losing
            ground against the edition.
        min_recent_shift: Smallest recent change of the share that counts as a movement
            when checking whether the last months confirm the trend.
        min_recent_views: Mean monthly views below which a three-month window is too noisy
            to confirm or contradict anything.
    """

    min_momentum: float = 0.05
    similar_size_ratio: float = 1.2
    min_share_shift: float = 0.05
    min_recent_shift: float = 0.05
    min_recent_views: float = 300.0


_DEFAULT_SETTINGS = AssessmentSettings()


def momentum(
    growth: float | None,
    direction: TrendDirection,
    settings: AssessmentSettings = _DEFAULT_SETTINGS,
) -> Momentum:
    """Growth or decline only when the trend test and the size of the change agree.

    Args:
        growth: Headline change of the analysed series (year over year, else halves).
        direction: Direction supported by the Mann-Kendall test on the same series;
            ``FLAT`` when the test is not significant.
        settings: Cut-offs.

    Returns:
        ``UNKNOWN`` without a change or a test; ``GROWING``/``DECLINING`` when the test is
        significant in the direction of a change of at least ``min_momentum``; ``FLAT``
        otherwise, including a significant test that contradicts the headline change.
    """
    if growth is None or direction is TrendDirection.UNKNOWN:
        return Momentum.UNKNOWN
    if direction is TrendDirection.RISING and growth >= settings.min_momentum:
        return Momentum.GROWING
    if direction is TrendDirection.FALLING and growth <= -settings.min_momentum:
        return Momentum.DECLINING
    return Momentum.FLAT


def relative_size(
    value: float | None, largest: float | None, settings: AssessmentSettings = _DEFAULT_SETTINGS
) -> RelativeSize | None:
    """Size against the largest value in the report; ``None`` when either is unknown.

    There is no absolute scale: 40 views per million is a lot for a chess opening and little
    for a pop star, so size is only ever stated against the alternatives the user asked about.
    """
    if value is None or largest is None or value <= 0 or largest <= 0:
        return None
    if value >= largest:
        return RelativeSize.LARGEST
    if largest / value < settings.similar_size_ratio:
        return RelativeSize.SIMILAR
    return RelativeSize.SMALLER


def edition_relation(
    share_change: float | None, settings: AssessmentSettings = _DEFAULT_SETTINGS
) -> EditionRelation | None:
    """Whether the topic gained or lost ground inside its edition over the same months."""
    if share_change is None:
        return None
    if share_change >= settings.min_share_shift:
        return EditionRelation.GAINING
    if share_change <= -settings.min_share_shift:
        return EditionRelation.LOSING
    return EditionRelation.IN_LINE


def robustness(
    trend: Momentum,
    recent_shift: float | None,
    *,
    reliable: bool,
    views_avg: float | None,
    settings: AssessmentSettings = _DEFAULT_SETTINGS,
) -> Robustness:
    """Whether the last months confirm the long-term direction.

    The long-term direction comes from the whole window; ``recent_shift`` is the change of
    the share (or of views without normalisation) in the last months against the same months
    a year earlier, so seasons cancel out. A trend the last months still follow is
    *confirmed*; one they no longer follow is *mixed*; one they go against is *reversing*.
    Without a trend, flat recent months confirm it and moving ones make it mixed.

    Args:
        trend: Long-term momentum.
        recent_shift: Recent change of the share, ``None`` when not measurable.
        reliable: ``False`` when the data cannot carry a conclusion (low reliability).
        views_avg: Mean monthly views; small audiences make three months noise.
        settings: Cut-offs.
    """
    too_small = views_avg is None or views_avg < settings.min_recent_views
    if not reliable or too_small or recent_shift is None or trend is Momentum.UNKNOWN:
        return Robustness.UNKNOWN
    cut = settings.min_recent_shift
    moving = abs(recent_shift) >= cut
    if trend is Momentum.FLAT:
        return Robustness.MIXED if moving else Robustness.CONFIRMED
    sign = 1.0 if trend is Momentum.GROWING else -1.0
    if recent_shift * sign >= cut:
        return Robustness.CONFIRMED
    if recent_shift * sign <= -cut:
        return Robustness.REVERSING
    return Robustness.MIXED


def outcome(
    size: RelativeSize | None,
    trend: Momentum,
    *,
    trusted: bool,
    measures_topic: bool = True,
) -> str:
    """The decision outcome as a stable key: size x momentum, with overriding cases first.

    Keys: ``substitute`` (another subject's article was measured), ``low_trust`` (the data
    cannot carry a conclusion), ``unknown`` (no trend measurable), else
    ``<large|small|single>_<growing|flat|declining>``. ``large`` covers the largest audience
    and those similar to it; ``single`` is a report with nothing to compare against.
    """
    if not measures_topic:
        return "substitute"
    if not trusted:
        return "low_trust"
    if trend is Momentum.UNKNOWN:
        return "unknown"
    if size is None:
        scale = "single"
    elif size is RelativeSize.SMALLER:
        scale = "small"
    else:
        scale = "large"
    return f"{scale}_{trend.value}"
