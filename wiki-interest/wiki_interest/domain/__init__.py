"""Pure domain logic: models and calculations with no I/O.

Everything here is deterministic and side-effect free so it can be tested with synthetic
series. Thresholds and other tunables are passed in explicitly, never read from the
environment.
"""

from wiki_interest.domain.metrics import MetricsSettings, compute_metrics
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
from wiki_interest.domain.ranking import ProfileThresholds, RankingInput, rank_audiences
from wiki_interest.domain.reliability import CHECK_NAMES, REASON_KEYS, assess_reliability
from wiki_interest.domain.series import align, combine, observed_pairs, per_million, to_monthly
from wiki_interest.domain.trend_tests import (
    MannKendallResult,
    detrend,
    mann_kendall,
    pairwise_median_slope,
    seasonal_strength,
    theil_sen_slope,
)

__all__ = [
    "CHECK_NAMES",
    "REASON_KEYS",
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
    "MannKendallResult",
    "MetricsSettings",
    "Point",
    "ProfileThresholds",
    "RankedAudience",
    "RankingInput",
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
    "align",
    "assess_reliability",
    "combine",
    "compute_metrics",
    "detrend",
    "mann_kendall",
    "observed_pairs",
    "pairwise_median_slope",
    "per_million",
    "rank_audiences",
    "seasonal_strength",
    "sorted_by_score",
    "theil_sen_slope",
    "to_monthly",
]
