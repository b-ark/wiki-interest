"""Non-parametric trend statistics used by the metrics.

Pageview series are short (24-60 months), skewed and spiked by news, so everything here is
rank- or median-based rather than least-squares:

* :func:`mann_kendall` - is there a monotonic trend at all (Mann 1945, Kendall 1975)?
* :func:`theil_sen_slope` - how steep is it, robustly (Theil 1950, Sen 1968)?
* :func:`detrend` / :func:`seasonal_strength` - how much of what is left repeats every year?

The implementations are deliberately dependency-free and are verified against
``pymannkendall.original_test`` and ``scipy.stats.theilslopes`` in
``tests/unit/domain/test_trend_tests.py``, so the reference libraries stay a dev dependency.
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import fmean, median

__all__ = [
    "MIN_MANN_KENDALL_VALUES",
    "MannKendallResult",
    "detrend",
    "mann_kendall",
    "pairwise_median_slope",
    "seasonal_strength",
    "theil_sen_slope",
]

MIN_MANN_KENDALL_VALUES = 4
"""Below this the normal approximation of S is meaningless (its variance formula assumes n > 3)."""

_MIN_SLOPE_VALUES = 2
_MIN_OBSERVATIONS_PER_POSITION = 2
"""Each season position needs two observations for its mean to say more than the data point."""


@dataclass(frozen=True, slots=True)
class MannKendallResult:
    """Outcome of the Mann-Kendall test.

    Attributes:
        statistic_s: Kendall's S, the count of rising minus falling pairs.
        variance: Variance of S under the null hypothesis, corrected for ties.
        z: Standardised statistic with continuity correction.
        p_value: Two-sided p-value from the normal approximation.
    """

    statistic_s: int
    variance: float
    z: float
    p_value: float


def mann_kendall(values: Sequence[float]) -> MannKendallResult:
    """Two-sided Mann-Kendall test for a monotonic trend.

    Uses the tie-corrected variance and the continuity correction of the classic
    formulation (Gilbert 1987, "Statistical Methods for Environmental Pollution Monitoring",
    ch. 16), which is also what ``pymannkendall.original_test`` implements; the test
    ``test_mann_kendall_matches_pymannkendall`` checks the two agree. The normal approximation
    is standard from about ten points; callers gate on their own minimum.

    When every value is equal the variance is zero and there is no evidence of a trend, so
    ``z = 0`` and ``p_value = 1`` rather than a division by zero.

    Args:
        values: Observations in chronological order.

    Returns:
        The statistic, its variance, ``z`` and the p-value.

    Raises:
        ValueError: If fewer than :data:`MIN_MANN_KENDALL_VALUES` values are given.
    """
    n = len(values)
    if n < MIN_MANN_KENDALL_VALUES:
        msg = f"Mann-Kendall needs at least {MIN_MANN_KENDALL_VALUES} values, got {n}"
        raise ValueError(msg)
    s = sum(_sign(values[j] - values[i]) for i in range(n - 1) for j in range(i + 1, n))
    variance = _tie_corrected_variance(values)
    if variance <= 0:
        return MannKendallResult(statistic_s=s, variance=0.0, z=0.0, p_value=1.0)
    z = (s - _sign(s)) / math.sqrt(variance)
    p_value = math.erfc(abs(z) / math.sqrt(2))
    return MannKendallResult(statistic_s=s, variance=variance, z=z, p_value=p_value)


def theil_sen_slope(values: Sequence[float]) -> float:
    """Estimate the robust linear slope of a series.

    Uses the median of pairwise slopes (Theil 1950, Sen 1968), so a few outliers (news
    spikes) do not dominate the estimate the way OLS would. Equivalent to
    ``scipy.stats.theilslopes(values).slope``; see ``test_theil_sen_matches_scipy``.

    Args:
        values: Observations in chronological order, evenly spaced, at least two points.

    Returns:
        Slope per step in the units of ``values``.

    Raises:
        ValueError: If fewer than two values are given.
    """
    if len(values) < _MIN_SLOPE_VALUES:
        msg = f"Theil-Sen slope needs at least {_MIN_SLOPE_VALUES} values, got {len(values)}"
        raise ValueError(msg)
    return pairwise_median_slope(tuple(enumerate(values)))


def pairwise_median_slope(points: Sequence[tuple[float, float]]) -> float:
    """Theil-Sen slope for explicitly positioned points, so gaps keep their width.

    Args:
        points: ``(x, y)`` pairs with strictly increasing ``x``; at least two.

    Returns:
        Median of the slopes of all pairs.

    Raises:
        ValueError: If fewer than two points are given.
    """
    if len(points) < _MIN_SLOPE_VALUES:
        msg = f"Theil-Sen slope needs at least {_MIN_SLOPE_VALUES} points, got {len(points)}"
        raise ValueError(msg)
    slopes = [
        (points[j][1] - points[i][1]) / (points[j][0] - points[i][0])
        for i in range(len(points) - 1)
        for j in range(i + 1, len(points))
    ]
    return median(slopes)


def detrend(values: Sequence[float | None]) -> tuple[float | None, ...]:
    """Remove a robust linear trend, keeping gaps in place.

    Fits a Theil-Sen line through the observed points at their true positions (the intercept
    is the median of ``y - slope * x``, as in Sen's estimator) and returns residuals. Used
    before measuring seasonality and volatility so that a steady rise is not mistaken for
    either.

    Args:
        values: Observations in chronological order, gaps as ``None``.

    Returns:
        Residuals at the same positions; ``None`` where the input was ``None``. With fewer than
        two observations the observed values are returned unchanged (there is no line to fit).
    """
    points = [(float(i), v) for i, v in enumerate(values) if v is not None]
    if len(points) < _MIN_SLOPE_VALUES:
        return tuple(values)
    slope = pairwise_median_slope(points)
    intercept = median(y - slope * x for x, y in points)
    return tuple(None if v is None else v - (intercept + slope * i) for i, v in enumerate(values))


def seasonal_strength(values: Sequence[float | None], period: int = 12) -> float | None:
    """Share of detrended variance explained by the position within the period.

    A one-way ANOVA decomposition of the Theil-Sen residuals by season position: the
    between-position sum of squares over the total sum of squares, i.e. R-squared of a
    "month-of-year means" model. Near 1 means the series repeats every ``period`` steps (school
    subjects), near 0 means no seasonal pattern. Verified in ``test_seasonal_strength_*``.

    Requires every position to be observed at least twice, which implies at least two full
    cycles; with fewer observations a position mean is just the data point and the ratio is
    meaningless. A series with zero residual variance (a perfect line) has no seasonality to
    measure and yields ``None`` rather than ``0/0``.

    Args:
        values: Observations in chronological order, gaps as ``None``.
        period: Length of one cycle in steps; 12 for months.

    Returns:
        A value in ``[0, 1]``, or ``None`` when not computable.

    Raises:
        ValueError: If ``period`` is smaller than two.
    """
    if period < _MIN_SLOPE_VALUES:
        msg = f"seasonal period must be at least 2, got {period}"
        raise ValueError(msg)
    residuals = [(i % period, r) for i, r in enumerate(detrend(values)) if r is not None]
    counts = Counter(position for position, _ in residuals)
    if len(counts) < period or min(counts.values()) < _MIN_OBSERVATIONS_PER_POSITION:
        return None
    grand_mean = fmean(r for _, r in residuals)
    total_ss = sum((r - grand_mean) ** 2 for _, r in residuals)
    if total_ss <= 0:
        return None
    by_position: dict[int, list[float]] = {}
    for position, r in residuals:
        by_position.setdefault(position, []).append(r)
    between_ss = sum(len(rs) * (fmean(rs) - grand_mean) ** 2 for rs in by_position.values())
    return min(1.0, max(0.0, between_ss / total_ss))


def _sign(value: float) -> int:
    """Signum as an integer."""
    return (value > 0) - (value < 0)


def _tie_corrected_variance(values: Sequence[float]) -> float:
    """Variance of Kendall's S under the null hypothesis, corrected for tied groups."""
    n = len(values)
    ties = sum(t * (t - 1) * (2 * t + 5) for t in Counter(values).values() if t > 1)
    return (n * (n - 1) * (2 * n + 5) - ties) / 18
