"""Builders for synthetic series and metrics used across the domain tests."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date, timedelta
from typing import Any

from wiki_interest.domain.models import (
    Granularity,
    Point,
    Series,
    SeriesUnit,
    TrendDirection,
    TrendMetrics,
)

MONTH_START = date(2023, 1, 1)
DAY_START = date(2024, 1, 1)

HEALTHY_METRICS = TrendMetrics(
    periods=24,
    completeness=1.0,
    views_total=24_000.0,
    views_avg=1_000.0,
    per_million_avg=12.0,
    growth_yoy=0.2,
    growth_halves=0.1,
    slope_per_year=0.15,
    trend_p_value=0.01,
    trend_direction=TrendDirection.RISING,
    seasonality_strength=0.1,
    spike_share=0.05,
    volatility_cv=0.1,
    automated_share=0.05,
)
"""Metrics that pass every reliability rule; override fields to hit other branches."""


def month_after(start: date, offset: int) -> date:
    index = start.year * 12 + start.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def monthly(
    values: Sequence[float | None],
    *,
    start: date = MONTH_START,
    unit: SeriesUnit = SeriesUnit.VIEWS,
) -> Series:
    points = tuple(Point(month_after(start, i), v) for i, v in enumerate(values))
    return Series(Granularity.MONTHLY, unit, points)


def daily(values: Sequence[float | None], *, start: date = DAY_START) -> Series:
    points = tuple(Point(start + timedelta(days=i), v) for i, v in enumerate(values))
    return Series(Granularity.DAILY, SeriesUnit.VIEWS, points)


def healthy_metrics(**overrides: Any) -> TrendMetrics:
    return replace(HEALTHY_METRICS, **overrides)
