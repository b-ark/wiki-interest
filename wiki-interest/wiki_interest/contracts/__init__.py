"""Data contracts shared with the agent.

Pydantic models for ``request.json`` (what the agent asks for), ``summary.json`` (what the
pipeline produces) and chart specifications. These schemas are versioned with
``schema_version``; any breaking change bumps it and updates ``references/request-schema.md``.
"""

from wiki_interest.contracts.charts import ChartKind, ChartSeries, ChartSpec
from wiki_interest.contracts.request import (
    EARLIEST_MONTH,
    AnalysisRequest,
    BundleMode,
    Period,
    QuestionType,
    RankingWeightsSpec,
    ReportOptions,
    TopicSpec,
)
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    ArticleOut,
    Artifacts,
    BundleOut,
    CandidateOut,
    CheckOut,
    Clarification,
    ComparisonRow,
    MetricsOut,
    PointOut,
    Provenance,
    RankedRow,
    ReliabilityOut,
    SeriesKind,
    SeriesOut,
    TopicResolutionOut,
    Verdict,
)

__all__ = [
    "EARLIEST_MONTH",
    "AnalysisRequest",
    "AnalysisSummary",
    "ArticleOut",
    "Artifacts",
    "BundleMode",
    "BundleOut",
    "CandidateOut",
    "ChartKind",
    "ChartSeries",
    "ChartSpec",
    "CheckOut",
    "Clarification",
    "ComparisonRow",
    "MetricsOut",
    "Period",
    "PointOut",
    "Provenance",
    "QuestionType",
    "RankedRow",
    "RankingWeightsSpec",
    "ReliabilityOut",
    "ReportOptions",
    "SeriesKind",
    "SeriesOut",
    "TopicResolutionOut",
    "TopicSpec",
    "Verdict",
]
