"""Detectors for the facts a report states beyond the headline metrics.

:mod:`~wiki_interest.domain.metrics` condenses a series into numbers; this module looks for
the *events and patterns* a reader would want named, each with dates and magnitudes:

* :func:`detect_level_shift`: the level stepped up or down at one month and stayed there.
* :func:`find_anomalies`: bursts of daily views, dated, with their size against the usual
  level around them.
* :func:`recent_change`: the last few months against the same months a year earlier.
* :func:`seasonal_profile`: which calendar months are above and below the usual level.
* :func:`compare_with_edition`: whether the article moved with its whole edition or against
  it, which separates "the topic lost readers" from "the edition shrank".

Every detector is conservative: it returns ``None`` (or nothing) when the data cannot
support a clear statement, because an invented pattern in a report is worse than a missing
one. Thresholds live in :class:`FindingsSettings`.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean, median

from wiki_interest.domain.metrics import MetricsSettings, comparable_growth
from wiki_interest.domain.models import Granularity, Series
from wiki_interest.domain.trend_tests import pairwise_median_slope

__all__ = [
    "Anomaly",
    "EditionComparison",
    "FindingsSettings",
    "LevelShift",
    "RecentChange",
    "SeasonalProfile",
    "compare_with_edition",
    "detect_level_shift",
    "find_anomalies",
    "recent_change",
    "seasonal_profile",
]

_MONTHS_PER_YEAR = 12


@dataclass(frozen=True, slots=True)
class FindingsSettings:
    """Thresholds of the detectors.

    Attributes:
        min_shift_months: Fewest observed months before a level shift is looked for.
        min_segment_months: Fewest months on each side of a shift; a shorter "level" is a
            bump, not a new normal.
        min_shift_change: Smallest relative change between the two levels worth naming.
        min_shift_t: Welch-like t statistic the difference of the log levels must reach.
        max_step_to_line_error: A step must fit at least this much better than a straight
            line (ratio of squared errors); otherwise the series is a steady trend, and
            naming a month would invent an event.
        anomaly_half_window_days: Days on each side used for the local baseline of a day;
            about six weeks, so that a two-week burst at the very start of the period does
            not fill its own baseline window.
        anomaly_ratio: A burst day is at least this multiple of its local baseline.
        anomaly_mad_multiplier: ...and exceeds it by this many robust standard deviations.
        anomaly_min_excess: ...and by at least this many views, so that 3 views instead of 1
            on an obscure article is not a "burst".
        anomaly_max_gap_days: Burst days at most this far apart form one episode.
        min_anomaly_days: Fewest observed days for burst detection.
        min_anomaly_share: Smallest share of all views in the period an episode must hold.
        max_anomalies: How many episodes to return, largest first.
        mad_scale: Turns a MAD into a standard deviation estimate for normal data.
        recent_months: Length of the "recent" stretch compared with a year earlier.
        min_seasonal_cycles: Full years needed before a seasonal profile is computed.
    """

    min_shift_months: int = 18
    min_segment_months: int = 6
    min_shift_change: float = 0.25
    min_shift_t: float = 4.0
    max_step_to_line_error: float = 0.6
    anomaly_half_window_days: int = 45
    anomaly_ratio: float = 2.5
    anomaly_mad_multiplier: float = 5.0
    anomaly_min_excess: float = 50.0
    anomaly_max_gap_days: int = 2
    min_anomaly_days: int = 60
    min_anomaly_share: float = 0.005
    max_anomalies: int = 3
    mad_scale: float = 1.4826
    recent_months: int = 3
    min_seasonal_cycles: int = 2


_DEFAULT_SETTINGS = FindingsSettings()


# ---------------------------------------------------------------------------
# Level shift
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LevelShift:
    """The series moved to a new level at ``start`` and stayed there.

    Attributes:
        start: First month of the new level.
        before: Mean of the analysed series before ``start``.
        after: Mean from ``start`` on.
        change: ``after / before - 1`` on the geometric means (robust to single spikes).
        months_after: Months observed at the new level.
    """

    start: date
    before: float
    after: float
    change: float
    months_after: int


def detect_level_shift(
    series: Series, settings: FindingsSettings = _DEFAULT_SETTINGS
) -> LevelShift | None:
    """Find a single step change in a monthly series, if there clearly is one.

    Works on ``log(value)`` so a doubling counts the same at any scale. Every split that
    leaves ``min_segment_months`` on both sides is tried; the one with the smallest squared
    error of a two-level model wins. It is reported only when the levels differ by at least
    ``min_shift_change``, the difference is large against the scatter around the two levels
    (``min_shift_t``), and the step explains the series clearly better than a straight line
    (``max_step_to_line_error``), so that a steady trend is not presented as an event.

    Args:
        series: Monthly series (per-million share or raw views).
        settings: Thresholds.

    Returns:
        The shift, or ``None`` when there is no clear one.
    """
    points = [
        (i, p.period, math.log(p.value))
        for i, p in enumerate(series.points)
        if p.value is not None and p.value > 0
    ]
    size = len(points)
    minimum = settings.min_segment_months
    if size < max(settings.min_shift_months, 2 * minimum):
        return None
    logs = [y for _, _, y in points]
    best: tuple[float, int] | None = None
    for split in range(minimum, size - minimum + 1):
        error = _sse(logs[:split]) + _sse(logs[split:])
        if best is None or error < best[0]:
            best = (error, split)
    assert best is not None
    step_error, split = best
    before, after = logs[:split], logs[split:]
    difference = fmean(after) - fmean(before)
    change = math.exp(difference) - 1
    if abs(change) < settings.min_shift_change:
        return None
    scatter = math.sqrt(step_error / (size - 2)) if size > 2 else 0.0  # noqa: PLR2004
    spread = scatter * math.sqrt(1 / len(before) + 1 / len(after))
    if spread > 0 and abs(difference) / spread < settings.min_shift_t:
        return None
    line_error = _line_sse([(float(i), y) for i, _, y in points])
    if line_error > 0 and step_error > settings.max_step_to_line_error * line_error:
        return None
    raw = [math.exp(y) for y in logs]
    return LevelShift(
        start=points[split][1],
        before=fmean(raw[:split]),
        after=fmean(raw[split:]),
        change=change,
        months_after=len(after),
    )


def _sse(values: Sequence[float]) -> float:
    mean = fmean(values)
    return sum((v - mean) ** 2 for v in values)


def _line_sse(points: Sequence[tuple[float, float]]) -> float:
    """Squared error of the least-squares line through ``points``."""
    xs = [x for x, _ in points]
    ys = [y for _, y in points]
    mean_x, mean_y = fmean(xs), fmean(ys)
    var_x = sum((x - mean_x) ** 2 for x in xs)
    if var_x == 0:
        return _sse(ys)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / var_x
    return sum((y - (mean_y + slope * (x - mean_x))) ** 2 for x, y in points)


# ---------------------------------------------------------------------------
# Daily bursts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Anomaly:
    """A burst of daily views.

    Attributes:
        start: First burst day.
        end: Last burst day (equal to ``start`` for a one-day burst).
        peak_day: Day with the most views.
        peak_views: Views on ``peak_day``.
        baseline: Usual daily views around ``peak_day`` (local median).
        multiple: ``peak_views / baseline``.
        share: Views above the baseline during the episode over all views in the period.
    """

    start: date
    end: date
    peak_day: date
    peak_views: float
    baseline: float
    multiple: float
    share: float


def find_anomalies(
    daily: Series, settings: FindingsSettings = _DEFAULT_SETTINGS
) -> tuple[Anomaly, ...]:
    """Dated bursts of attention in a daily series, largest first.

    Each day is compared with the median of the days around it (``anomaly_half_window_days``
    on each side), not with one median for the whole period: a topic that doubled over two
    years would otherwise show its whole last year as one long "burst". A day is a burst day
    when it passes all three bars (ratio, robust deviation, absolute excess); burst days close
    together form one episode.

    Args:
        daily: Daily views over the analysis period.
        settings: Thresholds.

    Returns:
        Up to ``max_anomalies`` episodes that each hold at least ``min_anomaly_share`` of the
        period's views, ordered by size.

    Raises:
        ValueError: If ``daily`` is not a daily series.
    """
    if daily.granularity is not Granularity.DAILY:
        msg = "find_anomalies() expects a daily series"
        raise ValueError(msg)
    observed = [(p.period, p.value) for p in daily.points if p.value is not None]
    if len(observed) < settings.min_anomaly_days:
        return ()
    total = sum(v for _, v in observed)
    if total <= 0:
        return ()
    values = [v for _, v in observed]
    days: list[tuple[date, float, float]] = []
    half = settings.anomaly_half_window_days
    for index, (day, value) in enumerate(observed):
        window = values[max(0, index - half) : index + half + 1]
        baseline = median(window)
        spread = settings.mad_scale * median(abs(v - baseline) for v in window)
        excess = value - baseline
        if (
            value >= settings.anomaly_ratio * baseline
            and excess >= settings.anomaly_mad_multiplier * spread
            and excess >= settings.anomaly_min_excess
        ):
            days.append((day, value, baseline))
    episodes = _episodes(days, settings.anomaly_max_gap_days)
    found = [_anomaly(episode, total) for episode in episodes]
    kept = [a for a in found if a.share >= settings.min_anomaly_share]
    kept.sort(key=lambda a: (-a.share, a.start))
    return tuple(kept[: settings.max_anomalies])


def _episodes(
    days: Sequence[tuple[date, float, float]], max_gap: int
) -> list[list[tuple[date, float, float]]]:
    episodes: list[list[tuple[date, float, float]]] = []
    for day in days:
        if episodes and (day[0] - episodes[-1][-1][0]).days <= max_gap:
            episodes[-1].append(day)
        else:
            episodes.append([day])
    return episodes


def _anomaly(episode: Sequence[tuple[date, float, float]], total: float) -> Anomaly:
    peak_day, peak_views, baseline = max(episode, key=lambda d: d[1])
    excess = sum(value - base for _, value, base in episode)
    return Anomaly(
        start=episode[0][0],
        end=episode[-1][0],
        peak_day=peak_day,
        peak_views=peak_views,
        baseline=baseline,
        multiple=peak_views / baseline if baseline > 0 else math.inf,
        share=excess / total,
    )


# ---------------------------------------------------------------------------
# Recent months
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RecentChange:
    """The last months against the same months one year earlier.

    Attributes:
        start: First month of the recent stretch.
        end: Last month of the recent stretch.
        months: Length of the stretch.
        current: Sum over the recent stretch.
        year_before: Sum over the same months a year earlier.
        change: ``current / year_before - 1``.
    """

    start: date
    end: date
    months: int
    current: float
    year_before: float
    change: float


def recent_change(
    monthly: Series, settings: FindingsSettings = _DEFAULT_SETTINGS
) -> RecentChange | None:
    """Compare the last ``recent_months`` with the same calendar months a year earlier.

    Same-month comparison cancels seasonality, which a "last three months against the three
    before" comparison would mistake for a trend. Every month in both stretches must be
    observed; a partial comparison would mix seasons again.

    Returns:
        The comparison, or ``None`` without complete data or with a zero base.
    """
    span = settings.recent_months
    points = monthly.points
    if len(points) < _MONTHS_PER_YEAR + span:
        return None
    current = [p.value for p in points[-span:]]
    before = [p.value for p in points[-span - _MONTHS_PER_YEAR : -_MONTHS_PER_YEAR]]
    if any(v is None for v in (*current, *before)):
        return None
    now = sum(v for v in current if v is not None)
    then = sum(v for v in before if v is not None)
    if then <= 0:
        return None
    return RecentChange(
        start=points[-span].period,
        end=points[-1].period,
        months=span,
        current=now,
        year_before=then,
        change=now / then - 1,
    )


# ---------------------------------------------------------------------------
# Seasonality
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SeasonalProfile:
    """How each calendar month compares with the usual level.

    Attributes:
        effects: Twelve values, January first: the month's typical level over the trend,
            minus one (``0.3`` = 30 % above usual); ``None`` for a month never observed.
        peak_month: Calendar month (1-12) with the highest effect.
        trough_month: Calendar month with the lowest effect.
    """

    effects: tuple[float | None, ...]
    peak_month: int
    trough_month: int

    @property
    def peak(self) -> float:
        """Effect of the peak month."""
        value = self.effects[self.peak_month - 1]
        assert value is not None
        return value

    @property
    def trough(self) -> float:
        """Effect of the trough month."""
        value = self.effects[self.trough_month - 1]
        assert value is not None
        return value


def seasonal_profile(
    monthly: Series, settings: FindingsSettings = _DEFAULT_SETTINGS
) -> SeasonalProfile | None:
    """Typical level of each calendar month relative to the trend.

    Each observation is divided by a robust exponential trend (Theil-Sen on the logs), the
    ratios are averaged per calendar month, and the twelve averages are scaled to a mean of
    one. Dividing by the trend first keeps growth from making late months look "seasonal".

    Returns:
        The profile, or ``None`` unless every calendar month is observed in at least
        ``min_seasonal_cycles`` years.
    """
    points = [
        (float(i), p.period.month, p.value)
        for i, p in enumerate(monthly.points)
        if p.value is not None and p.value > 0
    ]
    if len(points) < _MONTHS_PER_YEAR * settings.min_seasonal_cycles:
        return None
    logs = [(x, math.log(v)) for x, _, v in points]
    slope = pairwise_median_slope(logs)
    intercept = median(y - slope * x for x, y in logs)
    ratios: dict[int, list[float]] = {}
    for x, month, value in points:
        ratios.setdefault(month, []).append(value / math.exp(intercept + slope * x))
    if len(ratios) < _MONTHS_PER_YEAR or min(len(r) for r in ratios.values()) < (
        settings.min_seasonal_cycles
    ):
        return None
    means = {month: fmean(r) for month, r in ratios.items()}
    scale = fmean(means.values())
    effects = tuple(means[m] / scale - 1 for m in range(1, _MONTHS_PER_YEAR + 1))
    peak = max(range(1, _MONTHS_PER_YEAR + 1), key=lambda m: effects[m - 1])
    trough = min(range(1, _MONTHS_PER_YEAR + 1), key=lambda m: effects[m - 1])
    return SeasonalProfile(effects=effects, peak_month=peak, trough_month=trough)


# ---------------------------------------------------------------------------
# Article against its edition
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EditionComparison:
    """Growth of the article's views against growth of the whole edition, same months.

    Attributes:
        basis: ``"yoy"`` (last 12 months over the 12 before) or ``"halves"``.
        article_change: Growth of the article's raw views.
        edition_change: Growth of all views of the edition.
        share_change: Growth of the article's share, ``(1 + a) / (1 + e) - 1``.
    """

    basis: str
    article_change: float
    edition_change: float
    share_change: float


def compare_with_edition(
    article: Series,
    edition: Series,
    settings: MetricsSettings | None = None,
    *,
    share: Series | None = None,
) -> EditionComparison | None:
    """Split a change in attention share into its two causes.

    A falling share can mean the topic lost readers or that the edition as a whole gained
    them faster. Both growths are computed with the headline's rule (year over year, else
    halves) on the same months.

    Args:
        article: Monthly views of the article.
        edition: Monthly views of the whole edition, same months.
        settings: Growth rule settings (shared with the headline metrics).
        share: The article's per-million series, when normalised. Its growth is then taken
            as the share change, so the number matches the headline and the table exactly;
            otherwise ``(1 + article) / (1 + edition) - 1``.

    Returns:
        The comparison, or ``None`` when either growth cannot be computed on the same basis.
    """
    metric_settings = settings or MetricsSettings()
    article_change, basis = comparable_growth(article.values, metric_settings)
    edition_change, edition_basis = comparable_growth(edition.values, metric_settings)
    if article_change is None or edition_change is None or basis != edition_basis:
        return None
    assert basis is not None
    share_change = (1 + article_change) / (1 + edition_change) - 1
    if share is not None:
        measured, share_basis = comparable_growth(share.values, metric_settings)
        if measured is not None and share_basis == basis:
            share_change = measured
    return EditionComparison(
        basis=basis,
        article_change=article_change,
        edition_change=edition_change,
        share_change=share_change,
    )
