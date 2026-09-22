"""Ranking of (topic, project) audiences by growth, volume, stability and reliability.

A ranking answers "where should we look next?", so it must be comparable *within one
request*: every component is min-max normalised across the inputs of that request, then
folded with the user's weights. The score is therefore relative (a score of 1.0 means "best
of this set", not "great"), which the report states explicitly.

Two safeguards keep the ranking honest: an audience whose metrics cannot support a growth
figure gets :attr:`~wiki_interest.domain.models.AudienceProfile.INSUFFICIENT_DATA` and a zero
score instead of a flattering default, and a LOW-reliability audience has its score halved so
a spiky or half-empty series can never top a solid one on raw numbers alone.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from wiki_interest.domain.models import (
    AudienceProfile,
    RankedAudience,
    RankingWeights,
    ReliabilityLevel,
    TrendMetrics,
    WikiProject,
    sorted_by_score,
)

__all__ = ["ProfileThresholds", "RankingInput", "rank_audiences"]

_NEUTRAL = 0.5
"""Normalised value used when a component cannot discriminate (all equal or unknown)."""

_RELIABILITY_SCORE: dict[ReliabilityLevel, float] = {
    ReliabilityLevel.HIGH: 1.0,
    ReliabilityLevel.MEDIUM: 0.5,
    ReliabilityLevel.LOW: 0.0,
}


@dataclass(frozen=True, slots=True)
class RankingInput:
    """One audience to rank: its metrics and reliability, or ``None`` metrics if unavailable."""

    topic_id: str
    project: WikiProject
    metrics: TrendMetrics | None
    reliability: ReliabilityLevel


@dataclass(frozen=True, slots=True)
class ProfileThresholds:
    """Growth cut-offs for the interpretive profile labels.

    Attributes:
        growth_high: Relative growth at or above which an audience is growing.
        growth_low: Relative growth at or below which an audience is declining.
        low_reliability_penalty: Factor applied to the score of a LOW-reliability audience.
    """

    growth_high: float = 0.15
    growth_low: float = -0.10
    low_reliability_penalty: float = 0.5


@dataclass(frozen=True, slots=True)
class _RawComponents:
    """Un-normalised component values of one input; ``None`` where the data cannot say."""

    growth: float | None
    volume: float | None
    stability: float | None
    reliability: float


_DEFAULT_PROFILES = ProfileThresholds()


def rank_audiences(
    inputs: Sequence[RankingInput],
    weights: RankingWeights,
    *,
    profiles: ProfileThresholds = _DEFAULT_PROFILES,
) -> tuple[RankedAudience, ...]:
    """Score and order audiences, best first.

    Components per input: ``growth`` is ``growth_yoy``, falling back to ``growth_halves`` and
    then ``slope_per_year`` (the most informative figure the window supports); ``volume`` is
    ``log10(views_avg + 1)`` so a ten-fold larger audience counts one step more, not ten;
    ``stability`` is ``1 / (1 + volatility_cv)``; ``reliability`` maps HIGH/MEDIUM/LOW to
    1 / 0.5 / 0. Growth, volume and stability are min-max normalised across the inputs that
    have them (all equal, or unknown stability, gives the neutral 0.5) and combined with the
    normalised weights. Profiles use the *raw* growth against :class:`ProfileThresholds` and
    the raw volume against the median volume of the set.

    Args:
        inputs: Audiences of one request.
        weights: User weights; normalised here.
        profiles: Growth cut-offs and the LOW-reliability penalty.

    Returns:
        Audiences ordered by :func:`~wiki_interest.domain.models.sorted_by_score`.
    """
    raw = [_raw_components(item) for item in inputs]
    growth_n = _min_max([r.growth for r in raw])
    volume_n = _min_max([r.volume for r in raw])
    stability_n = _min_max([r.stability for r in raw])
    volumes = [r.volume for r in raw if r.volume is not None]
    median_volume = median(volumes) if volumes else None
    normalised = weights.normalised()
    ranked = []
    for item, components, g, v, s in zip(inputs, raw, growth_n, volume_n, stability_n, strict=True):
        score = _score(components, (g, v, s), normalised, item.reliability, profiles)
        ranked.append(
            RankedAudience(
                topic_id=item.topic_id,
                project=item.project,
                score=score,
                components={
                    "growth": g,
                    "volume": v,
                    "stability": s,
                    "reliability": components.reliability,
                },
                profile=_profile(components, median_volume, profiles),
                reliability=item.reliability,
            )
        )
    return sorted_by_score(ranked)


def _raw_components(item: RankingInput) -> _RawComponents:
    """Pick the raw component values out of the metrics."""
    reliability = _RELIABILITY_SCORE[item.reliability]
    m = item.metrics
    if m is None:
        return _RawComponents(None, None, None, reliability)
    growth = next(
        (g for g in (m.growth_yoy, m.growth_halves, m.slope_per_year) if g is not None), None
    )
    stability = None if m.volatility_cv is None else 1 / (1 + m.volatility_cv)
    return _RawComponents(growth, math.log10(m.views_avg + 1), stability, reliability)


def _min_max(values: Sequence[float | None]) -> list[float]:
    """Scale the known values to ``[0, 1]``; unknown or non-discriminating values become 0.5."""
    known = [v for v in values if v is not None]
    if not known or math.isclose(min(known), max(known)):
        return [_NEUTRAL for _ in values]
    low, span = min(known), max(known) - min(known)
    return [_NEUTRAL if v is None else (v - low) / span for v in values]


def _score(
    raw: _RawComponents,
    normalised: tuple[float, float, float],
    weights: RankingWeights,
    reliability: ReliabilityLevel,
    profiles: ProfileThresholds,
) -> float:
    """Weighted sum of normalised components, zero without growth, halved when unreliable."""
    if raw.growth is None:
        return 0.0
    growth, volume, stability = normalised
    score = (
        weights.growth * growth
        + weights.volume * volume
        + weights.stability * stability
        + weights.reliability * raw.reliability
    )
    if reliability is ReliabilityLevel.LOW:
        score *= profiles.low_reliability_penalty
    return score


def _profile(
    raw: _RawComponents, median_volume: float | None, profiles: ProfileThresholds
) -> AudienceProfile:
    """Interpretive label from raw growth and the audience's size relative to the set."""
    if raw.growth is None or raw.volume is None:
        return AudienceProfile.INSUFFICIENT_DATA
    if raw.growth >= profiles.growth_high:
        is_small = median_volume is not None and raw.volume < median_volume
        return AudienceProfile.EARLY_NICHE if is_small else AudienceProfile.GROWTH_MARKET
    if raw.growth <= profiles.growth_low:
        return AudienceProfile.DECLINING
    return AudienceProfile.MATURE_MARKET
