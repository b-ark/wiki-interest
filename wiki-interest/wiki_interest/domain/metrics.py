"""Trend metrics of one topic series: from aligned series to :class:`TrendMetrics`.

This is the numerical heart of the skill and the reason the agent never does arithmetic:
every number in the report is computed here, deterministically, from series the adapters
aligned to the analysis window. Each metric has a fixed definition (documented on its helper)
and returns ``None`` instead of a guess whenever the data cannot support it; the reliability
rules then explain the gap to the reader.

The *analysis series* is the per-million normalised series when available (comparable across
editions) and the raw monthly views otherwise. Growth, slope, trend, seasonality and
volatility are computed on it; ``views_*`` and ``spike_share`` always use raw views because
they describe audience size and daily anomalies, which normalisation would obscure.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean, median, pstdev

from wiki_interest.domain.models import Series, TrendDirection, TrendMetrics
from wiki_interest.domain.trend_tests import (
    MannKendallResult,
    detrend,
    mann_kendall,
    pairwise_median_slope,
    seasonal_strength,
    theil_sen_slope,
)

__all__ = ["MetricsSettings", "comparable_growth", "compute_automated_share", "compute_metrics"]

_STEPS_PER_YEAR = 12


@dataclass(frozen=True, slots=True)
class MetricsSettings:
    """Minimum sample sizes and detection constants for :func:`compute_metrics`.

    Grouped here so no threshold hides in code and a methodology change is one edit.

    Attributes:
        alpha: Significance level for the Mann-Kendall test (trend direction).
        yoy_months: Length of each year-over-year half (12 for calendar months).
        min_periods_halves: Fewest buckets for which a first-half/second-half growth is
            computed (each half then has at least two buckets).
        min_half_completeness: Share of matched bucket pairs each growth comparison must
            reach; pairs missing either observation are excluded from both sums.
        min_slope_observations: Fewest positive observations for the log-slope.
        min_trend_observations: Fewest observations for Mann-Kendall; below this the normal
            approximation of S has too little power to say anything either way.
        min_volatility_observations: Fewest observations for the detrended CV.
        min_spike_days: Fewest observed daily points for spike detection; a median and MAD
            over fewer days are too unstable to call anything an anomaly.
        spike_mad_multiplier: A spike exceeds the median by this many robust standard
            deviations (5 sigma, so ordinary weekly variation never qualifies).
        spike_ratio: A spike is also at least this multiple of the median, which keeps
            near-constant series (tiny MAD) from flagging every wobble.
        mad_scale: Consistency constant that turns the MAD into a standard deviation
            estimate for normal data (1 / Phi^-1(3/4)).
        seasonal_period: Cycle length for seasonality; 12 for months.
    """

    alpha: float = 0.05
    yoy_months: int = 12
    min_periods_halves: int = 4
    min_half_completeness: float = 0.75
    min_slope_observations: int = 6
    min_trend_observations: int = 8
    min_volatility_observations: int = 6
    min_spike_days: int = 30
    spike_mad_multiplier: float = 5.0
    spike_ratio: float = 2.0
    mad_scale: float = 1.4826
    seasonal_period: int = 12


_DEFAULT_SETTINGS = MetricsSettings()


def compute_metrics(
    monthly_views: Series,
    *,
    per_million: Series | None = None,
    daily_views: Series | None = None,
    automated_views: Series | None = None,
    settings: MetricsSettings = _DEFAULT_SETTINGS,
) -> TrendMetrics:
    """Compute every metric of :class:`TrendMetrics` for one topic in one project.

    Definitions (``analysis`` is ``per_million`` when given, else ``monthly_views``):

    * ``periods`` / ``completeness``: length and observed share of ``monthly_views``.
    * ``views_total`` / ``views_avg``: sum and mean of observed raw views (both ``0`` when
      nothing was observed, so that the volume rule can warn instead of crashing).
    * ``per_million_avg``: mean of observed ``per_million`` values, ``None`` without them.
    * ``growth_yoy``: last 12 analysis buckets over the 12 before, minus one, using only
      matched months observed in both years. Needs 24 buckets, 75 % pairs and a positive base.
    * ``growth_halves``: same for equal-length second and first halves, excluding the middle
      bucket of an odd window. Needs 4 buckets and 75 % matched pairs.
    * ``slope_per_year``: Theil-Sen slope of ``log(value)`` over positive observations at
      their true positions, reported as ``exp(12 * slope) - 1`` (relative change per year).
      Non-positive values are treated as missing because their log is undefined.
    * ``trend_p_value`` / ``trend_direction``: Mann-Kendall on observed analysis values;
      RISING/FALLING when ``p < alpha`` by the sign of the Theil-Sen slope, FLAT otherwise,
      UNKNOWN with too few observations.
    * ``seasonality_strength``: :func:`~wiki_interest.domain.trend_tests.seasonal_strength`.
    * ``spike_share``: share of total daily views attributable to spike excess; see
      :func:`_spike_share`.
    * ``volatility_cv``: standard deviation of Theil-Sen residuals over the mean level.
    * ``automated_share``: automated over automated plus user views on buckets observed in
      both series.

    Args:
        monthly_views: Raw monthly user views aligned to the analysis window.
        per_million: Normalised series over the same buckets, if normalisation was possible.
        daily_views: Raw daily user views for spike detection, if fetched.
        automated_views: Monthly automated-agent views, if the API had them.
        settings: Sample-size minima and detection constants.

    Returns:
        The metrics; anything the data cannot support is ``None``.
    """
    analysis = per_million if per_million is not None else monthly_views
    analysis_values = analysis.values
    observed_raw = monthly_views.observed
    trend = _trend(analysis.observed, settings)
    return TrendMetrics(
        periods=len(monthly_views),
        completeness=monthly_views.completeness,
        views_total=sum(observed_raw),
        views_avg=fmean(observed_raw) if observed_raw else 0.0,
        per_million_avg=_mean_or_none(per_million),
        growth_yoy=_growth_yoy(analysis_values, settings),
        growth_halves=_growth_halves(analysis_values, settings),
        slope_per_year=_slope_per_year(analysis_values, settings),
        trend_p_value=trend[0],
        trend_direction=trend[1],
        seasonality_strength=seasonal_strength(analysis_values, settings.seasonal_period),
        spike_share=_spike_share(daily_views, settings),
        volatility_cv=_volatility_cv(analysis_values, settings),
        automated_share=compute_automated_share(monthly_views, automated_views),
    )


def comparable_growth(
    values: tuple[float | None, ...], settings: MetricsSettings = _DEFAULT_SETTINGS
) -> tuple[float | None, str | None]:
    """Growth by the same rule the headline uses: year over year, else halves.

    Used to compare an article with its whole edition over exactly the same months.

    Returns:
        ``(growth, basis)`` where ``basis`` is ``"yoy"`` or ``"halves"``; ``(None, None)`` when
        neither can be computed.
    """
    yoy = _growth_yoy(values, settings)
    if yoy is not None:
        return yoy, "yoy"
    halves = _growth_halves(values, settings)
    if halves is not None:
        return halves, "halves"
    return None, None


def _mean_or_none(series: Series | None) -> float | None:
    """Mean of observed values, or ``None`` when there is no series or nothing observed."""
    if series is None or not series.observed:
        return None
    return fmean(series.observed)


def _growth_yoy(values: tuple[float | None, ...], settings: MetricsSettings) -> float | None:
    """Last ``yoy_months`` buckets over the preceding ``yoy_months``."""
    span = settings.yoy_months
    if len(values) < 2 * span:
        return None
    return _growth(values[-2 * span : -span], values[-span:], settings.min_half_completeness)


def _growth_halves(values: tuple[float | None, ...], settings: MetricsSettings) -> float | None:
    """Second half of the window over the first half."""
    if len(values) < settings.min_periods_halves:
        return None
    middle = len(values) // 2
    return _growth(values[:middle], values[-middle:], settings.min_half_completeness)


def _growth(
    before: tuple[float | None, ...],
    after: tuple[float | None, ...],
    min_completeness: float,
) -> float | None:
    """Compare equal-length stretches on matched observations, without imputing gaps.

    Matching positions preserves calendar-month comparability for year-over-year growth.
    Too few matched pairs or a non-positive base cannot support a growth estimate.
    """
    pairs = [(a, b) for a, b in zip(before, after, strict=True) if a is not None and b is not None]
    if not pairs or len(pairs) / len(before) < min_completeness:
        return None
    base = sum(a for a, _ in pairs)
    if base <= 0:
        return None
    return sum(b for _, b in pairs) / base - 1


def _slope_per_year(values: tuple[float | None, ...], settings: MetricsSettings) -> float | None:
    """Theil-Sen slope of the log series as a relative change per year."""
    points = [(float(i), math.log(v)) for i, v in enumerate(values) if v is not None and v > 0]
    if len(points) < settings.min_slope_observations:
        return None
    return math.exp(_STEPS_PER_YEAR * pairwise_median_slope(points)) - 1


def _trend(
    observed: tuple[float, ...], settings: MetricsSettings
) -> tuple[float | None, TrendDirection]:
    """Mann-Kendall p-value and the direction it supports."""
    if len(observed) < settings.min_trend_observations:
        return None, TrendDirection.UNKNOWN
    result: MannKendallResult = mann_kendall(observed)
    if result.p_value >= settings.alpha:
        return result.p_value, TrendDirection.FLAT
    slope = theil_sen_slope(observed)
    if slope > 0:
        return result.p_value, TrendDirection.RISING
    if slope < 0:
        return result.p_value, TrendDirection.FALLING
    return result.p_value, TrendDirection.FLAT


def _spike_share(daily_views: Series | None, settings: MetricsSettings) -> float | None:
    """Share of total daily traffic that is spike excess above the robust baseline.

    Baseline ``m`` is the median of observed days and the spread is ``mad_scale * MAD``, both
    immune to the spikes they are meant to find. A day is a spike when it exceeds
    ``m + spike_mad_multiplier * spread`` *and* ``spike_ratio * m``; the share is the sum of
    ``value - m`` over spike days divided by the sum of all observed days, i.e. how much of
    the audience would vanish without the news events. Verified in
    ``test_spike_share_single_spike_dominates``.
    """
    if daily_views is None:
        return None
    observed = daily_views.observed
    if len(observed) < settings.min_spike_days:
        return None
    total = sum(observed)
    if total <= 0:
        return 0.0
    baseline = median(observed)
    spread = settings.mad_scale * median(abs(v - baseline) for v in observed)
    threshold = max(
        baseline + settings.spike_mad_multiplier * spread, settings.spike_ratio * baseline
    )
    excess = sum(v - baseline for v in observed if v > threshold)
    return excess / total


def _volatility_cv(values: tuple[float | None, ...], settings: MetricsSettings) -> float | None:
    """Coefficient of variation of the Theil-Sen residuals: spread relative to level.

    The population standard deviation is used because the residuals describe this window,
    not a sample of a larger one. A non-positive mean level makes the ratio meaningless.
    """
    residuals = [r for r in detrend(values) if r is not None]
    if len(residuals) < settings.min_volatility_observations:
        return None
    level = fmean(v for v in values if v is not None)
    if level <= 0:
        return None
    return pstdev(residuals) / level


def compute_automated_share(
    user_views: Series | None, automated_views: Series | None
) -> float | None:
    """Return automated / (automated + user) on months observed in both traffic classes.

    Args:
        user_views: User traffic for exactly the same titles as ``automated_views``.
        automated_views: Automated traffic for those titles.

    Returns:
        The share, or ``None`` without both series, overlapping observations or traffic.
    """
    if user_views is None or automated_views is None:
        return None
    user_by_period = {p.period: p.value for p in user_views.points if p.value is not None}
    pairs = [
        (user_by_period[p.period], p.value)
        for p in automated_views.points
        if p.value is not None and p.period in user_by_period
    ]
    if not pairs:
        return None
    automated = sum(a for _, a in pairs)
    denominator = automated + sum(u for u, _ in pairs)
    if denominator <= 0:
        return None
    return automated / denominator
