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

from wiki_interest.domain.observations import PairHistory, first_data, pair_steps
from wiki_interest.domain.trust import TrendVerdict, TrustSettings, WindowTrend, window_trend

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
        trend = _trend(_history(lambda k: (6_000.0 if k < 64 else 4_000.0) * _noise(k)))
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
