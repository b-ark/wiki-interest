"""Series algebra: aligning, combining, resampling and normalising :class:`Series`.

These are the only operations the pipeline needs between "adapters returned raw series" and
"metrics are computed", so they live together and stay pure: no I/O, no configuration, no
numeric libraries. Every function returns a new :class:`Series`; inputs are never mutated.

Gap semantics are the important design choice here and are documented per function: a
``None`` point means "the source had no data", and each operation states explicitly whether a
gap in one input becomes a gap in the output.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

from wiki_interest.domain.models import Granularity, Point, Series, SeriesUnit, Window

__all__ = [
    "PER_MILLION_SCALE",
    "align",
    "combine",
    "observed_pairs",
    "per_million",
    "to_monthly",
]

PER_MILLION_SCALE = 1_000_000.0
"""Multiplier that turns a share of project traffic into "views per million project views"."""


def observed_pairs(series: Series) -> tuple[tuple[int, float], ...]:
    """Return ``(index, value)`` for every observed point, preserving positions across gaps.

    Positions matter for anything that fits a line through time (Theil-Sen, detrending): a
    gap must shift the x coordinate of later points, not compress the series.

    Args:
        series: Any series.

    Returns:
        Pairs in chronological order; the index is the point's position in ``series.points``.
    """
    return tuple((i, p.value) for i, p in enumerate(series.points) if p.value is not None)


def align(series: Series, window: Window) -> Series:
    """Reindex a series onto the buckets of a window.

    Buckets the series has no point for become ``None``; points outside the window are
    dropped. This makes every series in a run the same shape so later operations can work
    by position and completeness is always measured against the requested window.

    Args:
        series: Series to align; its granularity must match ``window.granularity``.
        window: Target buckets.

    Returns:
        A series with exactly ``window.count`` points.

    Raises:
        ValueError: If the granularities differ (reindexing daily data onto monthly
            buckets would silently drop 29 of 30 days; use :func:`to_monthly` instead).
    """
    if series.granularity is not window.granularity:
        msg = f"Cannot align a {series.granularity} series onto a {window.granularity} window"
        raise ValueError(msg)
    by_period = {p.period: p.value for p in series.points}
    points = tuple(Point(bucket, by_period.get(bucket)) for bucket in window.buckets())
    return Series(series.granularity, series.unit, points)


def combine(parts: Sequence[tuple[Series, float]]) -> Series:
    """Weighted sum of aligned series with identical granularity, unit and periods.

    A bucket is ``None`` only when *every* part is ``None`` there; otherwise it is the weighted
    sum of the parts that have data. This is deliberate: a bundle is "main article plus
    redirects plus related articles", and a redirect or a young related article missing a
    month must not erase the main article's data for that month. The price is that such a
    month is slightly under-counted, which is why completeness of the parts is reported
    separately rather than hidden here.

    Args:
        parts: ``(series, weight)`` pairs; weights are applied as given (not normalised).

    Returns:
        A series with the same periods, granularity and unit as the parts.

    Raises:
        ValueError: If ``parts`` is empty or the series are not mutually aligned.
    """
    if not parts:
        msg = "combine() needs at least one series"
        raise ValueError(msg)
    first = parts[0][0]
    for series, _ in parts[1:]:
        _require_aligned(first, series, "combine")
    values: list[float | None] = []
    for index in range(len(first.points)):
        observed = [
            value * weight
            for series, weight in parts
            if (value := series.points[index].value) is not None
        ]
        values.append(sum(observed) if observed else None)
    points = tuple(
        Point(period, value) for period, value in zip(first.periods, values, strict=True)
    )
    return Series(first.granularity, first.unit, points)


def to_monthly(daily: Series) -> Series:
    """Sum daily points into calendar months.

    A month is ``None`` only when all of its days are ``None``; a month with some missing
    days keeps the partial sum. Adapters fetch monthly data directly for the analysis, so
    this is used for daily-derived diagnostics (spike detection) and tests, where a partial
    month is more useful than a gap. Months are emitted only for calendar months that have at
    least one daily point, so an aligned daily series yields a contiguous monthly series.

    Args:
        daily: A daily series.

    Returns:
        A monthly series in the same unit.

    Raises:
        ValueError: If ``daily`` is not daily.
    """
    if daily.granularity is not Granularity.DAILY:
        msg = "to_monthly() expects a daily series"
        raise ValueError(msg)
    sums: dict[date, float | None] = {}
    for point in daily.points:
        month = point.period.replace(day=1)
        current = sums.setdefault(month, None)
        if point.value is not None:
            sums[month] = point.value if current is None else current + point.value
    points = tuple(Point(month, value) for month, value in sorted(sums.items()))
    return Series(Granularity.MONTHLY, daily.unit, points)


def per_million(article: Series, project_total: Series) -> Series:
    """Normalise article views by total project views, per million.

    Absolute views are not comparable across editions (uk-wiki has an order of magnitude more
    traffic than cs-wiki); the share of an edition's traffic is. A bucket is ``None`` when
    either side is missing or when the project total is not positive: dividing by zero would
    be meaningless and a zero total is itself a sign of missing aggregate data.

    Args:
        article: Article (or bundle) series in views.
        project_total: Aggregate project series over the same periods.

    Returns:
        A series in :attr:`~wiki_interest.domain.models.SeriesUnit.PER_MILLION`.

    Raises:
        ValueError: If the two series do not share granularity and periods.
    """
    _require_same_periods(article, project_total, "per_million")
    points = tuple(
        Point(
            a.period,
            None
            if a.value is None or t.value is None or t.value <= 0
            else _scale(a.value, t.value),
        )
        for a, t in zip(article.points, project_total.points, strict=True)
    )
    return Series(article.granularity, SeriesUnit.PER_MILLION, points)


def _scale(value: float, total: float) -> float:
    """Return ``value`` as a share of ``total`` expressed per million."""
    return value / total * PER_MILLION_SCALE


def _require_same_periods(first: Series, second: Series, operation: str) -> None:
    """Raise ``ValueError`` unless both series have identical granularity and periods."""
    if first.granularity is not second.granularity:
        msg = f"{operation}() needs series of the same granularity"
        raise ValueError(msg)
    if first.periods != second.periods:
        msg = f"{operation}() needs series over the same periods"
        raise ValueError(msg)


def _require_aligned(first: Series, second: Series, operation: str) -> None:
    """Raise ``ValueError`` unless the series are interchangeable point for point."""
    _require_same_periods(first, second, operation)
    if first.unit is not second.unit:
        msg = f"{operation}() needs series of the same unit"
        raise ValueError(msg)
