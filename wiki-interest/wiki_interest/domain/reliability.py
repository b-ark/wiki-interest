"""Reliability rules: how much the metrics of one (topic, project) can be trusted.

Each rule is a small function that reads a :class:`_Context` and returns one
:class:`~wiki_interest.domain.models.Check` with a stable ``name`` and ``reason_key``. The
domain produces no prose: the report layer translates ``reason_key`` and ``params`` into the
report language, and a translation-completeness test walks :data:`REASON_KEYS` to make sure
nothing is left untranslated. Adding a rule means adding a function to :data:`_RULES`; the
aggregation in :func:`assess_reliability` never changes.

Thresholds come from :class:`~wiki_interest.domain.models.ReliabilityThresholds` so the
methodology document and the code share one set of numbers.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from wiki_interest.domain.models import (
    BundleStatus,
    Check,
    CheckStatus,
    Reliability,
    ReliabilityLevel,
    ReliabilityThresholds,
    ResolutionSource,
    TrendDirection,
    TrendMetrics,
)

__all__ = ["CHECK_NAMES", "REASON_KEYS", "assess_reliability"]

CHECK_NAMES: frozenset[str] = frozenset(
    {
        "window_length",
        "completeness",
        "spikes",
        "trend",
        "resolution",
        "automated",
        "volume",
        "bundle",
    }
)
"""Every ``Check.name`` this module can emit."""

REASON_KEYS: frozenset[str] = frozenset(
    {
        "window_length.ok",
        "window_length.short",
        "window_length.too_short",
        "completeness.ok",
        "completeness.gaps",
        "completeness.sparse",
        "spikes.low",
        "spikes.notable",
        "spikes.dominant",
        "spikes.unavailable",
        "trend.significant",
        "trend.not_significant",
        "trend.unavailable",
        "resolution.sitelink",
        "resolution.search_fallback",
        "resolution.manual",
        "resolution.not_found",
        "automated.low",
        "automated.high",
        "automated.unavailable",
        "volume.ok",
        "volume.low",
        "bundle.consistent",
        "bundle.diverges",
    }
)
"""Every ``Check.reason_key`` this module can emit; the i18n tables must cover all of them."""

_MIN_WARNS_FOR_MEDIUM = 2
_DEFAULT_THRESHOLDS = ReliabilityThresholds()


@dataclass(frozen=True, slots=True)
class _Context:
    """Everything a rule may look at."""

    metrics: TrendMetrics
    bundle_status: BundleStatus
    main_source: ResolutionSource | None
    main_metrics: TrendMetrics | None
    thresholds: ReliabilityThresholds


_Rule = Callable[[_Context], Check | None]


def assess_reliability(
    metrics: TrendMetrics | None,
    *,
    bundle_status: BundleStatus,
    main_source: ResolutionSource | None,
    main_metrics: TrendMetrics | None = None,
    thresholds: ReliabilityThresholds = _DEFAULT_THRESHOLDS,
) -> Reliability:
    """Run every reliability rule and aggregate the verdict.

    Aggregation is deliberately blunt so the reader can reproduce it by eye: any FAIL makes
    the verdict LOW, two or more WARNs make it MEDIUM, otherwise HIGH. INFO checks never
    change the level; they exist so the report can say what was *not* checked.

    A topic that has no article in the edition (or no data at all, ``metrics is None``) is
    LOW with the resolution check alone: there is nothing else to assess, and listing
    "window too short" for a series that does not exist would mislead.

    Args:
        metrics: Metrics of the bundle series, or ``None`` when there is no series.
        bundle_status: Outcome of resolving the topic in this project.
        main_source: How the main article's title was obtained, if there is one.
        main_metrics: Metrics of the main article alone, when the bundle has related
            articles; enables the bundle-consistency rule.
        thresholds: Rule thresholds.

    Returns:
        The level and the checks that produced it.
    """
    if metrics is None:
        check = _resolution(bundle_status, main_source, thresholds)
        return Reliability(level=ReliabilityLevel.LOW, checks=(check,))
    context = _Context(metrics, bundle_status, main_source, main_metrics, thresholds)
    results = (rule(context) for rule in _RULES)
    checks = tuple(check for check in results if check is not None)
    return Reliability(level=_aggregate(checks), checks=checks)


def _aggregate(checks: tuple[Check, ...]) -> ReliabilityLevel:
    """Any FAIL is LOW, two or more WARNs are MEDIUM, otherwise HIGH."""
    statuses = [c.status for c in checks]
    if CheckStatus.FAIL in statuses:
        return ReliabilityLevel.LOW
    if statuses.count(CheckStatus.WARN) >= _MIN_WARNS_FOR_MEDIUM:
        return ReliabilityLevel.MEDIUM
    return ReliabilityLevel.HIGH


def _window_length(ctx: _Context) -> Check:
    """Enough months to see a trend rather than a season."""
    months = ctx.metrics.periods
    params = {"months": months}
    if months >= ctx.thresholds.min_periods_ok:
        return Check("window_length", CheckStatus.PASS, "window_length.ok", params)
    if months >= ctx.thresholds.min_periods_warn:
        return Check("window_length", CheckStatus.WARN, "window_length.short", params)
    return Check("window_length", CheckStatus.FAIL, "window_length.too_short", params)


def _completeness(ctx: _Context) -> Check:
    """Gaps in the series (young article, API outage) weaken every other number."""
    share = ctx.metrics.completeness
    missing = ctx.metrics.periods - round(share * ctx.metrics.periods)
    params = {"missing_months": missing, "share": share}
    if share >= ctx.thresholds.completeness_ok:
        return Check("completeness", CheckStatus.PASS, "completeness.ok", params)
    if share >= ctx.thresholds.completeness_warn:
        return Check("completeness", CheckStatus.WARN, "completeness.gaps", params)
    return Check("completeness", CheckStatus.FAIL, "completeness.sparse", params)


def _spikes(ctx: _Context) -> Check:
    """Growth that lives in a few news days is not sustained interest."""
    share = ctx.metrics.spike_share
    if share is None:
        return Check("spikes", CheckStatus.INFO, "spikes.unavailable")
    params = {"share": share}
    if share < ctx.thresholds.spike_share_warn:
        return Check("spikes", CheckStatus.PASS, "spikes.low", params)
    if share > ctx.thresholds.spike_share_fail:
        return Check("spikes", CheckStatus.FAIL, "spikes.dominant", params)
    return Check("spikes", CheckStatus.WARN, "spikes.notable", params)


def _trend(ctx: _Context) -> Check:
    """Whether the direction the report states is statistically supported."""
    p_value = ctx.metrics.trend_p_value
    if p_value is None:
        return Check("trend", CheckStatus.INFO, "trend.unavailable")
    if p_value < ctx.thresholds.trend_p_value:
        params = {"p_value": p_value, "direction": ctx.metrics.trend_direction.value}
        return Check("trend", CheckStatus.PASS, "trend.significant", params)
    return Check("trend", CheckStatus.WARN, "trend.not_significant", {"p_value": p_value})


def _resolution(
    bundle_status: BundleStatus,
    main_source: ResolutionSource | None,
    thresholds: ReliabilityThresholds,
) -> Check:
    """How confidently the topic was mapped to an article in this edition.

    A search fallback may have picked a neighbouring subject, so it warns by default; a
    manually supplied title is the user's own choice and only informs.
    """
    if bundle_status is BundleStatus.NOT_FOUND:
        return Check("resolution", CheckStatus.FAIL, "resolution.not_found")
    via_search = (
        main_source is ResolutionSource.SEARCH_FALLBACK
        or bundle_status is BundleStatus.FOUND_VIA_SEARCH
    )
    if via_search:
        status = CheckStatus.WARN if thresholds.search_fallback_warns else CheckStatus.INFO
        return Check("resolution", status, "resolution.search_fallback")
    if main_source is ResolutionSource.SITELINK:
        return Check("resolution", CheckStatus.PASS, "resolution.sitelink")
    return Check("resolution", CheckStatus.INFO, "resolution.manual")


def _resolution_rule(ctx: _Context) -> Check:
    """Adapter that lets :func:`_resolution` sit in the rule list."""
    return _resolution(ctx.bundle_status, ctx.main_source, ctx.thresholds)


def _automated(ctx: _Context) -> Check:
    """A large automated share means the user series may be contaminated too."""
    share = ctx.metrics.automated_share
    if share is None:
        return Check("automated", CheckStatus.INFO, "automated.unavailable")
    params = {"share": share}
    if share < ctx.thresholds.automated_share_warn:
        return Check("automated", CheckStatus.PASS, "automated.low", params)
    return Check("automated", CheckStatus.WARN, "automated.high", params)


def _volume(ctx: _Context) -> Check:
    """Tiny audiences make every percentage noisy."""
    views_avg = ctx.metrics.views_avg
    params = {"views_avg": views_avg}
    if views_avg >= ctx.thresholds.min_views_avg:
        return Check("volume", CheckStatus.PASS, "volume.ok", params)
    return Check("volume", CheckStatus.WARN, "volume.low", params)


def _bundle(ctx: _Context) -> Check | None:
    """The bundle and its main article should tell the same story.

    When they diverge the conclusion depends on which related articles were included, which
    the reader must know before acting on it.
    """
    if ctx.main_metrics is None:
        return None
    main = ctx.main_metrics.trend_direction
    bundle = ctx.metrics.trend_direction
    unknown = TrendDirection.UNKNOWN
    if main is bundle or main is unknown or bundle is unknown:
        return Check("bundle", CheckStatus.INFO, "bundle.consistent")
    params = {"main_direction": main.value, "bundle_direction": bundle.value}
    return Check("bundle", CheckStatus.WARN, "bundle.diverges", params)


_RULES: tuple[_Rule, ...] = (
    _window_length,
    _completeness,
    _spikes,
    _trend,
    _resolution_rule,
    _automated,
    _volume,
    _bundle,
)
