"""Every reliability rule at its PASS/WARN/FAIL boundaries, plus the aggregation."""

from __future__ import annotations

from typing import Any

import pytest
from series_factory import healthy_metrics

from wiki_interest.domain.models import (
    BundleStatus,
    Check,
    CheckStatus,
    Reliability,
    ReliabilityLevel,
    ReliabilityThresholds,
    ResolutionSource,
    SubstituteKind,
    TrendMetrics,
)
from wiki_interest.domain.reliability import CHECK_NAMES, REASON_KEYS, assess_reliability

T = ReliabilityThresholds()


def assess(metrics: TrendMetrics | None, **kwargs: Any) -> Reliability:
    kwargs.setdefault("bundle_status", BundleStatus.FOUND)
    kwargs.setdefault("main_source", ResolutionSource.SITELINK)
    return assess_reliability(metrics, **kwargs)


def check(reliability: Reliability, name: str) -> Check:
    found = [c for c in reliability.checks if c.name == name]
    assert len(found) == 1, f"expected exactly one {name!r} check, got {found}"
    return found[0]


class TestHappyPath:
    def test_healthy_metrics_are_high_with_every_rule_passing(self) -> None:
        result = assess(healthy_metrics())
        assert result.level is ReliabilityLevel.HIGH
        assert {c.name for c in result.checks} == CHECK_NAMES
        assert all(c.status is CheckStatus.PASS for c in result.checks)

    def test_check_order_is_stable(self) -> None:
        names = [c.name for c in assess(healthy_metrics()).checks]
        assert names == [
            "window_length",
            "completeness",
            "spikes",
            "trend",
            "resolution",
            "automated",
            "volume",
        ]


class TestWindowLength:
    @pytest.mark.parametrize(
        ("months", "status", "key"),
        [
            (T.min_periods_ok, CheckStatus.PASS, "window_length.ok"),
            (T.min_periods_ok - 1, CheckStatus.WARN, "window_length.short"),
            (T.min_periods_warn, CheckStatus.WARN, "window_length.short"),
            (T.min_periods_warn - 1, CheckStatus.FAIL, "window_length.too_short"),
        ],
    )
    def test_boundaries(self, months: int, status: CheckStatus, key: str) -> None:
        c = check(assess(healthy_metrics(periods=months)), "window_length")
        assert (c.status, c.reason_key, c.params["months"]) == (status, key, months)


class TestCompleteness:
    @pytest.mark.parametrize(
        ("share", "status", "key"),
        [
            (T.completeness_ok, CheckStatus.PASS, "completeness.ok"),
            (0.90, CheckStatus.WARN, "completeness.gaps"),
            (T.completeness_warn, CheckStatus.WARN, "completeness.gaps"),
            (0.5, CheckStatus.FAIL, "completeness.sparse"),
        ],
    )
    def test_boundaries(self, share: float, status: CheckStatus, key: str) -> None:
        c = check(assess(healthy_metrics(completeness=share, periods=20)), "completeness")
        assert (c.status, c.reason_key) == (status, key)
        assert c.params["share"] == share

    def test_reports_missing_months(self) -> None:
        c = check(assess(healthy_metrics(periods=24, completeness=0.875)), "completeness")
        assert c.params["missing_months"] == 3


class TestSpikes:
    @pytest.mark.parametrize(
        ("share", "status", "key"),
        [
            (0.0, CheckStatus.PASS, "spikes.low"),
            (T.spike_share_warn - 0.01, CheckStatus.PASS, "spikes.low"),
            (T.spike_share_warn, CheckStatus.WARN, "spikes.notable"),
            (T.spike_share_fail, CheckStatus.WARN, "spikes.notable"),
            (T.spike_share_fail + 0.01, CheckStatus.FAIL, "spikes.dominant"),
        ],
    )
    def test_boundaries(self, share: float, status: CheckStatus, key: str) -> None:
        c = check(assess(healthy_metrics(spike_share=share)), "spikes")
        assert (c.status, c.reason_key, c.params["share"]) == (status, key, share)

    def test_unavailable_is_info(self) -> None:
        c = check(assess(healthy_metrics(spike_share=None)), "spikes")
        assert (c.status, c.reason_key) == (CheckStatus.INFO, "spikes.unavailable")


class TestTrend:
    def test_significant_passes_with_direction(self) -> None:
        c = check(assess(healthy_metrics(trend_p_value=0.01)), "trend")
        assert (c.status, c.reason_key) == (CheckStatus.PASS, "trend.significant")
        assert c.params == {"p_value": 0.01, "direction": "rising"}

    @pytest.mark.parametrize("p_value", [T.trend_p_value, 0.5])
    def test_not_significant_warns(self, p_value: float) -> None:
        c = check(assess(healthy_metrics(trend_p_value=p_value)), "trend")
        assert (c.status, c.reason_key) == (CheckStatus.WARN, "trend.not_significant")
        assert c.params == {"p_value": p_value}

    def test_unavailable_is_info(self) -> None:
        c = check(assess(healthy_metrics(trend_p_value=None)), "trend")
        assert (c.status, c.reason_key) == (CheckStatus.INFO, "trend.unavailable")


class TestResolution:
    def test_sitelink_passes(self) -> None:
        c = check(assess(healthy_metrics()), "resolution")
        assert (c.status, c.reason_key) == (CheckStatus.PASS, "resolution.sitelink")

    def test_search_fallback_warns_by_default(self) -> None:
        c = check(
            assess(healthy_metrics(), main_source=ResolutionSource.SEARCH_FALLBACK), "resolution"
        )
        assert (c.status, c.reason_key) == (CheckStatus.WARN, "resolution.search_fallback")

    def test_found_via_search_status_also_counts_as_fallback(self) -> None:
        c = check(
            assess(healthy_metrics(), bundle_status=BundleStatus.FOUND_VIA_SEARCH), "resolution"
        )
        assert c.reason_key == "resolution.search_fallback"

    def test_search_fallback_only_informs_when_configured(self) -> None:
        c = check(
            assess(
                healthy_metrics(),
                main_source=ResolutionSource.SEARCH_FALLBACK,
                thresholds=ReliabilityThresholds(search_fallback_warns=False),
            ),
            "resolution",
        )
        assert c.status is CheckStatus.INFO

    @pytest.mark.parametrize("source", [ResolutionSource.MANUAL, None])
    def test_manual_or_absent_main_is_info(self, source: ResolutionSource | None) -> None:
        c = check(assess(healthy_metrics(), main_source=source), "resolution")
        assert (c.status, c.reason_key) == (CheckStatus.INFO, "resolution.manual")

    def test_not_found_without_metrics_is_low_with_only_this_check(self) -> None:
        result = assess(None, bundle_status=BundleStatus.NOT_FOUND, main_source=None)
        assert result.level is ReliabilityLevel.LOW
        assert len(result.checks) == 1
        c = result.checks[0]
        assert (c.name, c.status, c.reason_key) == (
            "resolution",
            CheckStatus.FAIL,
            "resolution.not_found",
        )


class TestAutomated:
    @pytest.mark.parametrize(
        ("share", "status", "key"),
        [
            (T.automated_share_warn - 0.01, CheckStatus.PASS, "automated.low"),
            (T.automated_share_warn, CheckStatus.INFO, "automated.high"),
        ],
    )
    def test_boundaries(self, share: float, status: CheckStatus, key: str) -> None:
        c = check(assess(healthy_metrics(automated_share=share)), "automated")
        assert (c.status, c.reason_key, c.params["share"]) == (status, key, share)

    def test_unavailable_is_info(self) -> None:
        c = check(assess(healthy_metrics(automated_share=None)), "automated")
        assert (c.status, c.reason_key) == (CheckStatus.INFO, "automated.unavailable")


class TestVolume:
    @pytest.mark.parametrize(
        ("views_avg", "status", "key"),
        [
            (T.min_views_avg, CheckStatus.PASS, "volume.ok"),
            (T.min_views_avg - 1, CheckStatus.WARN, "volume.low"),
        ],
    )
    def test_boundaries(self, views_avg: float, status: CheckStatus, key: str) -> None:
        c = check(assess(healthy_metrics(views_avg=views_avg)), "volume")
        assert (c.status, c.reason_key, c.params["views_avg"]) == (status, key, views_avg)


class TestAggregation:
    def test_one_warn_is_still_high(self) -> None:
        assert assess(healthy_metrics(views_avg=10)).level is ReliabilityLevel.HIGH

    def test_two_warns_are_medium(self) -> None:
        result = assess(healthy_metrics(views_avg=10, trend_p_value=0.3))
        assert result.level is ReliabilityLevel.MEDIUM

    def test_any_fail_is_low_even_without_warns(self) -> None:
        assert assess(healthy_metrics(spike_share=0.9)).level is ReliabilityLevel.LOW

    def test_info_checks_do_not_lower_the_level(self) -> None:
        result = assess(healthy_metrics(spike_share=None, automated_share=None, trend_p_value=None))
        assert result.level is ReliabilityLevel.HIGH

    def test_metrics_none_is_low_even_when_found(self) -> None:
        assert assess(None).level is ReliabilityLevel.LOW


class TestRegistry:
    def test_every_emitted_reason_key_is_registered(self) -> None:
        scenarios = [
            assess(healthy_metrics()),
            assess(healthy_metrics(periods=15, completeness=0.9, spike_share=0.3)),
            assess(healthy_metrics(periods=3, completeness=0.5, spike_share=0.9)),
            assess(healthy_metrics(spike_share=None, trend_p_value=None, automated_share=None)),
            assess(healthy_metrics(trend_p_value=0.5, automated_share=0.5, views_avg=1)),
            assess(healthy_metrics(), main_source=ResolutionSource.SEARCH_FALLBACK),
            assess(healthy_metrics(), main_source=ResolutionSource.MANUAL),
            assess(None, bundle_status=BundleStatus.NOT_FOUND, main_source=None),
            *(
                assess(
                    healthy_metrics(),
                    bundle_status=BundleStatus.SUBSTITUTE,
                    main_source=ResolutionSource.SUBSTITUTE,
                    substitute_kind=kind,
                )
                for kind in SubstituteKind
            ),
        ]
        emitted = {c.reason_key for r in scenarios for c in r.checks}
        assert emitted == REASON_KEYS
        assert {c.name for r in scenarios for c in r.checks} == CHECK_NAMES

    def test_reason_keys_are_namespaced_by_check_name(self) -> None:
        for key in REASON_KEYS:
            assert key.split(".")[0] in CHECK_NAMES


class TestSubstitutes:
    def _assess(self, kind: SubstituteKind) -> Reliability:
        return assess(
            healthy_metrics(),
            bundle_status=BundleStatus.SUBSTITUTE,
            main_source=ResolutionSource.SUBSTITUTE,
            substitute_kind=kind,
        )

    def test_redirect_warns_because_it_only_undercounts(self) -> None:
        result = self._assess(SubstituteKind.REDIRECT)
        assert check(result, "resolution").status is CheckStatus.WARN
        assert result.level is ReliabilityLevel.HIGH  # one warning alone does not lower it

    @pytest.mark.parametrize("kind", [SubstituteKind.BROADER, SubstituteKind.MENTION])
    def test_another_subject_makes_the_verdict_low(self, kind: SubstituteKind) -> None:
        result = self._assess(kind)
        resolution = check(result, "resolution")
        assert resolution.status is CheckStatus.FAIL
        assert resolution.reason_key == f"resolution.substitute_{kind.value}"
        assert result.level is ReliabilityLevel.LOW
