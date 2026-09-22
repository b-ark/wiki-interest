"""Pure domain logic: models and calculations with no I/O.

Everything here is deterministic and side-effect free so it can be tested with synthetic
series. Thresholds and other tunables are passed in explicitly, never read from the
environment.
"""

from wiki_interest.domain.models import (
    Access,
    Agent,
    ArticleRef,
    ArticleRole,
    AudienceProfile,
    BundleStatus,
    Check,
    CheckStatus,
    EntityCandidate,
    Granularity,
    Point,
    RankedAudience,
    RankingWeights,
    Reliability,
    ReliabilityLevel,
    ReliabilityThresholds,
    ResolutionSource,
    Series,
    SeriesUnit,
    TopicBundle,
    TrendDirection,
    TrendMetrics,
    WikiProject,
    Window,
    sorted_by_score,
)

__all__ = [
    "Access",
    "Agent",
    "ArticleRef",
    "ArticleRole",
    "AudienceProfile",
    "BundleStatus",
    "Check",
    "CheckStatus",
    "EntityCandidate",
    "Granularity",
    "Point",
    "RankedAudience",
    "RankingWeights",
    "Reliability",
    "ReliabilityLevel",
    "ReliabilityThresholds",
    "ResolutionSource",
    "Series",
    "SeriesUnit",
    "TopicBundle",
    "TrendDirection",
    "TrendMetrics",
    "WikiProject",
    "Window",
    "sorted_by_score",
]
