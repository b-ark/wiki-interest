"""The analysis window's verdict (and, from phase 2 of v0.2, the trust in it).

Synthetic series: 72 months from 2020-09 to 2026-08 of an article in an edition with a steady
100 million views a month; the window is the last 24 months. The reference case is the v0.2
one: veganism (Q181138) in the Russian and Czech Wikipedias, 2024-09 – 2026-08, recorded in
``tests/fixtures/v02_veganism.json``.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from wiki_interest.application.window import ControlSeries, DayShares, read_trends, read_trust
from wiki_interest.domain.observations import PairHistory, first_data, pair_steps
from wiki_interest.domain.trust import (
    BreakpointVerdict,
    Confidence,
    TrendVerdict,
    Trust,
    TrustSettings,
    WindowTrend,
    assess_trust,
    breakpoint_verdict,
    control_step,
    control_trend,
    day_spike_months,
    window_trend,
    yoy_counts,
)

EDITION = 100_000_000.0
MONTHS = 72
WINDOW = date(2024, 9, 1)
FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "v02_veganism.json"


def _months(count: int = MONTHS, start: date = date(2020, 9, 1)) -> tuple[date, ...]:
    out = []
    y, m = start.year, start.month
    for _ in range(count):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return tuple(out)


def _history(shape: Callable[[int], float], count: int = MONTHS) -> PairHistory:
    months = _months(count)
    return PairHistory(
        topic_id="topic",
        topic="topic",
        project="uk.wikipedia",
        months=months,
        views=tuple(shape(k) for k in range(count)),
        edition=(EDITION,) * count,
    )


def _trend(history: PairHistory, start: date = WINDOW) -> WindowTrend:
    trimmed = first_data(history)
    assert trimmed is not None
    steps, adjusted, _ = pair_steps(trimmed, threshold=TrustSettings().split_step)
    return window_trend(trimmed, window_start=start, steps=steps, adjusted=adjusted)


def _noise(k: int) -> float:
    return 1 + 0.03 * math.sin(k * 1.7)


class TestVerdict:
    def test_a_flat_series_is_stable(self) -> None:
        trend = _trend(_history(lambda k: 5_000.0 * _noise(k)))
        assert trend.verdict is TrendVerdict.STABLE
        assert trend.slope_pct_per_year is not None
        assert abs(trend.slope_pct_per_year) < 10
        assert trend.segment_start == WINDOW

    @pytest.mark.parametrize(("yearly", "verdict"), [(1.3, "growing"), (0.7, "declining")])
    def test_a_steady_trend_is_read_in_percent_a_year(self, yearly: float, verdict: str) -> None:
        trend = _trend(_history(lambda k: 5_000.0 * yearly ** (k / 12) * _noise(k)))
        assert trend.verdict == verdict
        assert trend.slope_pct_per_year == pytest.approx((yearly - 1) * 100, abs=3)

    def test_a_trend_under_the_stable_band_is_stable(self) -> None:
        trend = _trend(_history(lambda k: 5_000.0 * 0.95 ** (k / 12) * _noise(k)))
        assert trend.verdict is TrendVerdict.STABLE

    def test_a_step_inside_the_window_is_not_a_trend(self) -> None:
        """A level that fell once and held is stable after the step, not a steady fall."""
        trend = _trend(_history(lambda k: (6_000.0 if k < 51 else 4_000.0) * _noise(k)))
        assert trend.verdict is TrendVerdict.STABLE
        assert trend.step is not None
        assert trend.segment_start == date(2024, 12, 1)
        assert trend.level_start == pytest.approx(40.0, rel=0.05)

    def test_a_step_too_late_to_leave_a_year_reads_the_whole_window(self) -> None:
        trend = _trend(_history(lambda k: (6_000.0 if k < 60 else 4_000.0) * _noise(k)))
        assert trend.segment_start == WINDOW
        assert trend.step is None

    def test_under_a_hundred_views_a_month_is_insufficient(self) -> None:
        trend = _trend(_history(lambda k: 60.0 * _noise(k)))
        assert trend.verdict is TrendVerdict.INSUFFICIENT_DATA
        assert trend.slope_pct_per_year is None

    def test_a_window_under_a_year_is_insufficient(self) -> None:
        trend = _trend(_history(lambda k: 5_000.0 * _noise(k)), start=date(2025, 12, 1))
        assert trend.verdict is TrendVerdict.INSUFFICIENT_DATA

    def test_the_trend_line_ends_at_the_window_end(self) -> None:
        trend = _trend(_history(lambda k: 5_000.0 * 0.7 ** (k / 12)))
        assert trend.window_end == date(2026, 8, 1)
        assert trend.level_end == pytest.approx(5_000.0 * 0.7 ** (71 / 12) / 100, rel=0.02)


def _reference(project: str) -> PairHistory:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))["pairs"][project]
    months = tuple(date(int(m[:4]), int(m[5:]), 1) for m in data["months"])
    return PairHistory(
        topic_id="veganism",
        topic="веганство",
        project=project,
        months=months,
        views=tuple(data["views"]),
        edition=tuple(data["edition"]),
    )


class TestReference:
    """Veganism, ru and cs, 2024-09 – 2026-08: the case the v0.2 work was checked on."""

    def test_the_russian_share_has_stabilised_after_a_drop(self) -> None:
        trend = _trend(_reference("ru.wikipedia"))
        assert trend.verdict is TrendVerdict.STABLE
        assert trend.step is not None
        assert trend.step.ratio < 1
        assert trend.segment_start == date(2024, 12, 1)

    def test_the_czech_share_keeps_declining(self) -> None:
        trend = _trend(_reference("cs.wikipedia"))
        assert trend.verdict is TrendVerdict.DECLINING
        assert trend.segment_start == date(2025, 5, 1)
        assert trend.slope_pct_per_year is not None
        assert trend.slope_pct_per_year < -20


def _trust(
    history: PairHistory,
    *,
    controls: list[list[float | None]] | None = None,
    moves: tuple[date, ...] = (),
    spikes: tuple[date, ...] = (),
) -> Trust:
    """The trust of ``history`` as the pipeline reads it."""
    control = (
        {history.project: ControlSeries(history.months, tuple(tuple(c) for c in controls))}
        if controls
        else None
    )
    trends = read_trends([history], WINDOW, spikes={history.pair: spikes})
    days = {history.pair: DayShares({}, spikes)} if spikes else None
    return read_trust([history], trends, controls=control, moves={history.pair: moves}, days=days)[
        history.pair
    ]


def _control(shape: Callable[[int], float], count: int = 30) -> list[list[float | None]]:
    """``count`` control articles of the same shape, each a little off the others."""
    return [[shape(k) * (1 + 0.01 * j) for k in range(MONTHS)] for j in range(count)]


class TestTrustMetrics:
    def test_a_steady_trend_with_little_noise_is_trusted(self) -> None:
        trust = _trust(_history(lambda k: 5_000.0 * 0.7 ** (k / 12) * _noise(k)))
        assert (trust.yoy_down, trust.yoy_months) == (12, 12)
        assert trust.ci90 is not None
        assert trust.ci90[1] < 0  # the interval leaves out zero
        assert trust.snr is not None
        assert trust.snr >= 2
        assert trust.confidence is Confidence.HIGH

    def test_a_flat_series_is_trusted_as_stable(self) -> None:
        trust = _trust(_history(lambda k: 5_000.0 * _noise(k)))
        assert trust.ci90 is not None
        assert -10 < trust.ci90[0] < trust.ci90[1] < 10
        assert trust.confidence is Confidence.HIGH

    def test_noise_leaves_a_stable_verdict_uncertain(self) -> None:
        rough = [1.0, 1.5, 0.6, 1.4, 0.7, 1.3, 0.5, 1.6, 0.8, 1.2, 0.6, 1.5]
        trust = _trust(_history(lambda k: 5_000.0 * rough[k % 12] * (1 + (k % 5) / 10)))
        assert trust.confidence is not Confidence.HIGH

    def test_the_bootstrap_is_seeded(self) -> None:
        history = _history(lambda k: 5_000.0 * 0.8 ** (k / 12) * (1 + 0.2 * math.sin(k * 2.3)))
        assert _trust(history).ci90 == _trust(history).ci90

    def test_too_few_views_are_insufficient_and_say_why(self) -> None:
        trust = _trust(_history(lambda k: 50.0 * _noise(k)))
        assert trust.confidence is Confidence.LOW
        assert [r.code for r in trust.reasons] == ["volume_low"]

    def test_the_control_explains_a_fall_its_articles_share(self) -> None:

        def shape(k: int) -> float:
            return float(0.7 ** (k / 12) * _noise(k))

        trust = _trust(
            _history(lambda k: 5_000.0 * shape(k)), controls=_control(lambda k: 50.0 * shape(k))
        )
        assert trust.control_change == pytest.approx(-30, abs=4)
        assert trust.confidence is Confidence.LOW
        assert trust.reasons[0].code == "control_explains"

    def test_a_flat_control_leaves_the_fall_to_the_topic(self) -> None:
        trust = _trust(
            _history(lambda k: 5_000.0 * 0.7 ** (k / 12) * _noise(k)),
            controls=_control(lambda k: 50.0 * _noise(k)),
        )
        assert trust.control_change is not None
        assert abs(trust.control_change) < 3
        assert trust.confidence is Confidence.HIGH
        assert "control" in [r.code for r in trust.reasons]


class TestBreakpoints:
    def _step(self) -> PairHistory:
        return _history(lambda k: (8_000.0 if k < 30 else 4_000.0) * _noise(k))

    def test_a_step_the_control_did_not_take_is_real(self) -> None:
        trust = _trust(self._step(), controls=_control(lambda k: 50.0 * _noise(k)))
        (step,) = [b for b in trust.breakpoints if b.month == date(2023, 3, 1)]
        assert step.verdict is BreakpointVerdict.REAL
        assert step.control_change_pct is not None
        assert abs(step.control_change_pct) < 5
        # Flat on both sides: a step, not a trend.
        assert step.flat_around(10.0)

    def test_a_step_the_control_took_too_is_an_artifact(self) -> None:
        trust = _trust(
            self._step(), controls=_control(lambda k: (60.0 if k < 30 else 32.0) * _noise(k))
        )
        (step,) = [b for b in trust.breakpoints if b.month == date(2023, 3, 1)]
        assert step.verdict is BreakpointVerdict.ARTIFACT
        assert "artifact" in [r.code for r in trust.reasons]

    def test_a_rename_next_to_a_step_makes_it_an_artifact(self) -> None:
        trust = _trust(self._step(), moves=(date(2023, 2, 17),))
        (step,) = [b for b in trust.breakpoints if b.month == date(2023, 3, 1)]
        assert step.renamed
        assert step.verdict is BreakpointVerdict.ARTIFACT
        assert "renames" in [r.code for r in trust.reasons]

    def test_without_control_data_a_step_is_unknown(self) -> None:
        trust = _trust(self._step())
        (step,) = [b for b in trust.breakpoints if b.month == date(2023, 3, 1)]
        assert step.verdict is BreakpointVerdict.UNKNOWN
        assert "control_none" in [r.code for r in trust.reasons]
        assert "renames_none" in [r.code for r in trust.reasons]

    def test_the_verdict_rule_weighs_the_change_in_log_terms(self) -> None:
        assert breakpoint_verdict(-40, -25, renamed=False) is BreakpointVerdict.ARTIFACT
        assert breakpoint_verdict(-40, -10, renamed=False) is BreakpointVerdict.REAL
        assert breakpoint_verdict(-40, +20, renamed=False) is BreakpointVerdict.REAL
        assert breakpoint_verdict(-40, None, renamed=False) is BreakpointVerdict.UNKNOWN


class TestDaySpikes:
    def test_a_day_that_dominates_its_month_makes_a_spike_month(self) -> None:
        daily = [(date(2025, 3, d), 100.0) for d in range(1, 32)]
        daily[9] = (date(2025, 3, 10), 3_000.0)  # 3,000 of 6,000: half the month on one day
        daily += [(date(2025, 4, d), 100.0) for d in range(1, 31)]
        shares, spikes = day_spike_months(daily)
        assert shares[date(2025, 3, 1)] == pytest.approx(0.5)
        assert shares[date(2025, 4, 1)] == pytest.approx(1 / 30)
        assert spikes == (date(2025, 3, 1),)

    def test_a_spike_month_is_left_out_of_the_slope(self) -> None:
        def burst(k: int) -> float:
            return 5_000.0 * _noise(k) * (4.0 if k == 60 else 1.0)

        history = _history(burst)
        plain = read_trends([history], WINDOW)[history.pair]
        left_out = read_trends([history], WINDOW, spikes={history.pair: (date(2025, 9, 1),)})[
            history.pair
        ]
        assert date(2025, 9, 1) in left_out.excluded
        assert left_out.months == plain.months - 1 or date(2025, 9, 1) in plain.excluded

    def test_a_steady_window_has_no_spike(self) -> None:
        daily = [(date(2025, 3, d), 100.0 + d) for d in range(1, 32)]
        assert day_spike_months(daily)[1] == ()


def test_yoy_counts_read_the_windows_last_twelve_months() -> None:
    shares = [10.0] * 12 + [9.0] * 6 + [11.0] * 6
    assert yoy_counts(shares, window_first=0) == (6, 6, 12)
    # A window of twelve months has no year before it inside the window.
    assert yoy_counts(shares, window_first=12) == (0, 0, 0)


def test_control_step_and_trend_read_the_median_article() -> None:
    controls = [[10.0] * 12 + [5.0] * 12 for _ in range(5)]
    assert control_step(controls, 12) == pytest.approx(-50)
    trend, count = control_trend([[10.0 * 0.9 ** (k / 12) for k in range(24)]] * 3, 0, 24)
    assert trend == pytest.approx(-10, abs=0.5)
    assert count == 3


def test_a_slope_most_months_contradict_is_low_trust() -> None:
    """A trend over one season read a rise; the months, year on year, fell: trust is low."""
    points = tuple((float(k), math.log(5.0 + 0.3 * (k - 60))) for k in range(60, 72))
    trend = WindowTrend(
        pair="topic/uk",
        verdict=TrendVerdict.GROWING,
        window_start=date(2024, 9, 1),
        window_end=date(2026, 8, 1),
        segment_start=date(2025, 9, 1),
        slope_pct_per_year=60.0,
        level_start=5.0,
        level_end=8.3,
        views_avg=2_000.0,
        months=12,
        intercept=0.0,
        slope_log=math.log(1.6) / 12,
        segment_index=60,
        end_index=71,
        points=points,
        window_index=48,
    )
    shares = [10.0] * 60 + [6.0] * 12  # every month under the same month a year earlier
    trust = assess_trust(trend, shares=shares, breakpoints=())
    assert trust.confidence is Confidence.LOW
    assert trust.reasons[0].code == "yoy_against"
