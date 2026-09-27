"""Observations: each detector fires on the shape it describes, and only then.

The series are synthetic: 72 months from 2020-09 to 2026-08 of an article in an edition with a
steady 100 million views a month, shaped by a trend, a calendar rhythm or an event. The
analysis window is the last 24 months (2024-09 – 2026-08), as by default; the four years
before it are context. Numbers in a statement are the numbers it quotes, so a text citing it
may quote them.
"""

# ruff: noqa: RUF001  -- the statements write the minus sign, as the report does.

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import replace
from datetime import date

import pytest

from wiki_interest.domain.observations import (
    Observation,
    PairHistory,
    Weight,
    edition_name,
    first_data,
    observe,
    pair_steps,
    year_levels,
)
from wiki_interest.domain.prose_numbers import extract_numbers, matches
from wiki_interest.domain.trust import TrustSettings, WindowTrend, window_trend

EDITION = 100_000_000.0
MONTHS = 72
WINDOW = date(2024, 9, 1)


def _months(count: int = MONTHS, start: date = date(2020, 9, 1)) -> tuple[date, ...]:
    out = []
    y, m = start.year, start.month
    for _ in range(count):
        out.append(date(y, m, 1))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return tuple(out)


def _history(
    shape: Callable[[int, date], float],
    *,
    topic: str = "astronomy",
    project: str = "uk.wikipedia",
    edition: Callable[[int], float] = lambda _: EDITION,
    count: int = MONTHS,
) -> PairHistory:
    months = _months(count)
    return PairHistory(
        topic_id=topic,
        topic=topic,
        project=project,
        months=months,
        views=tuple(shape(k, m) for k, m in enumerate(months)),
        edition=tuple(edition(k) for k in range(count)),
    )


def _trends(histories: Sequence[PairHistory], start: date = WINDOW) -> dict[str, WindowTrend]:
    """The window's verdict of each pair, as the pipeline reads it."""
    out = {}
    for history in histories:
        trimmed = first_data(history)
        if trimmed is None:
            continue
        steps, adjusted, _ = pair_steps(trimmed, threshold=TrustSettings().split_step)
        out[history.pair] = window_trend(
            trimmed, window_start=start, steps=steps, adjusted=adjusted
        )
    return out


def _observe(histories: Sequence[PairHistory], start: date = WINDOW) -> list[Observation]:
    return observe(histories, window_start=start, trends=_trends(histories, start))


def _by_id(observations: list[Observation]) -> dict[str, Observation]:
    return {o.id: o for o in observations}


def _flat(level: float = 5_000.0) -> Callable[[int, date], float]:
    return lambda k, _m: level * (1 + 0.02 * math.sin(k))


def _decline(start: float = 10_000.0, yearly: float = 0.75) -> Callable[[int, date], float]:
    return lambda k, _m: start * yearly ** (k / 12) * (1 + 0.02 * math.sin(k))


class TestTrends:
    def test_a_steady_decline_is_context_in_the_history_and_the_verdict_in_the_window(
        self,
    ) -> None:
        found = _by_id(_observe([_history(_decline())]))
        long_term = found["long_term:astronomy/uk"]
        assert long_term.weight is Weight.CONTEXT
        assert long_term.statement.startswith("In the wider context since 2021")
        assert "in 2025 it was about a third of what it was in 2021" in long_term.statement
        trend = found["trend:astronomy/uk"]
        assert trend.weight is Weight.HIGH
        assert "declines" in trend.statement
        assert "(−25 % a year)" in trend.statement
        assert "The article lost more than its Wikipedia" in (
            found["vs_wikipedia:astronomy/uk"].statement
        )
        verdict = found["decision:verdict:astronomy/uk"].statement
        assert "is shrinking against its Wikipedia" in verdict
        assert "invest" not in verdict

    def test_a_rise_that_came_back_is_a_wave(self) -> None:
        def wave(k: int, _m: date) -> float:
            return 5_000.0 * (1 + 1.5 * math.exp(-(((k - 30) / 10) ** 2)))

        long_term = _by_id(_observe([_history(wave)]))["long_term:astronomy/uk"]
        assert "was highest in" in long_term.statement
        assert "A wave that has passed" in long_term.statement

    def test_views_that_fall_with_the_edition_are_not_the_topic(self) -> None:
        shrinking = _history(
            lambda k, _m: 5_000.0 * 0.8 ** (k / 12), edition=lambda k: EDITION * 0.8 ** (k / 12)
        )
        found = _by_id(_observe([shrinking]))
        vs = found["vs_wikipedia:astronomy/uk"].statement
        assert "comes from Wikipedia losing readers, not from the topic" in vs
        assert "is stable" in found["trend:astronomy/uk"].statement
        verdict = found["decision:verdict:astronomy/uk"].statement
        assert "holds steady against its Wikipedia" in verdict
        assert "Its views fall with Wikipedia as a whole" in verdict

    def test_a_named_short_window_reads_the_history_as_context(self) -> None:
        found = _by_id(_observe([_history(_school)], start=date(2025, 9, 1)))
        assert found["long_term:astronomy/uk"].statement.startswith("In the wider context")
        assert "school-year rhythm" in found["season:astronomy/uk"].statement
        assert "September 2025 – August 2026" in found["trend:astronomy/uk"].statement

    def test_an_article_younger_than_the_window_is_read_from_its_first_month(self) -> None:
        young = _history(lambda k, _m: None if k < 50 else 1_000.0)  # type: ignore[arg-type,return-value]
        found = _by_id(_observe([young]))
        assert "long_term:astronomy/uk" not in found
        assert "season:astronomy/uk" not in found
        assert "size:astronomy/uk" in found


class TestWindow:
    """ "Now" is the window's last twelve months, set against the twelve before."""

    def test_now_is_the_last_twelve_months(self) -> None:
        size = _by_id(_observe([_history(_flat())]))["size:astronomy/uk"].statement
        assert "times a month in September 2025 – August 2026" in size
        assert "In 2021" not in size

    def test_the_comparison_names_both_spans(self) -> None:
        vs = _by_id(_observe([_history(_school)]))["vs_wikipedia:astronomy/uk"].statement
        assert vs.startswith("In September 2025 – August 2026 against September 2024 – August 2025")
        assert "moved about as much as its Wikipedia" in vs

    def test_two_editions_are_set_against_each_other_over_the_same_months(self) -> None:
        uk = _history(_flat(4_000.0))
        cs = _history(_flat(2_000.0), project="cs.wikipedia", edition=lambda _: EDITION / 4)
        editions = _by_id(_observe([uk, cs]))["sections:astronomy"].statement
        assert editions.startswith("In September 2025 – August 2026 the article")
        assert "Against September 2024 – August 2025 both hold steady" in editions
        assert "The window's verdict on the attention share: it holds steady in both." in editions

    def test_a_step_inside_the_window_starts_the_verdict(self) -> None:
        """A drop that happened once and then held has stabilised; it is not a steady fall."""
        drop = _history(lambda k, _m: 6_000.0 * (1 + 0.02 * math.sin(k)) if k < 51 else 4_000.0)
        trend = _by_id(_observe([drop]))["trend:astronomy/uk"].statement
        assert "has stabilised since the step of December 2024" in trend

    def test_each_year_of_the_history_is_read_whole(self) -> None:
        history = _history(_decline(), edition=lambda k: EDITION * 0.9 ** (k / 12))
        years = year_levels(history)
        assert [y.year for y in years] == [2021, 2022, 2023, 2024, 2025, 2026]
        assert not any(y.partial for y in years[:-1])


def _school(k: int, m: date) -> float:
    return 1_000.0 * (4.0 if m.month == 9 else 0.4 if m.month in (6, 7, 8) else 1.0)


class TestCalendar:
    def test_a_september_peak_and_an_empty_summer_are_school_readers(self) -> None:
        found = _by_id(_observe([_history(_school)]))
        season = found["season:astronomy/uk"]
        assert season.weight is Weight.HIGH
        assert "peaks in September" in season.statement
        audience = found["decision:audience:astronomy/uk"]
        assert "school year" in audience.statement
        assert "be ready by August" in audience.statement

    def test_a_january_peak_times_a_launch(self) -> None:
        def resolutions(k: int, m: date) -> float:
            return 1_000.0 * (1.6 if m.month == 1 else 0.9)

        found = _by_id(_observe([_history(resolutions)]))
        assert "strongest in January" in found["season:astronomy/uk"].statement
        assert "ready by December" in found["decision:timing:astronomy/uk"].statement

    def test_no_rhythm_is_said_plainly(self) -> None:
        season = _by_id(_observe([_history(_flat())]))["season:astronomy/uk"]
        assert season.weight is Weight.LOW
        assert "no marked season" in season.statement


def test_the_summer_drop_of_the_school_rhythm_names_a_summer_month() -> None:
    """The year's lowest month was January, and the text said "drops in summer (January)"."""
    level = {10: 1.8, 6: 0.8, 7: 0.8, 8: 0.8, 1: 0.6}
    found = _by_id(_observe([_history(lambda _k, m: 5_000.0 * level.get(m.month, 1.0))]))
    season = found["season:astronomy/uk"].statement
    assert "drops in summer (" in season
    summer = season.split("drops in summer (", 1)[1]
    assert summer.startswith(("June", "July", "August")), season


class TestEvents:
    def test_one_month_far_above_its_calendar_month_is_a_spike(self) -> None:
        found = _by_id(_observe([_history(lambda k, _m: 5_000.0 * (8 if k == 52 else 1))]))
        spike = found["spike:astronomy/uk"]
        assert "January 2025" in spike.statement
        assert "not lasting interest" in spike.statement

    def test_two_bursting_months_in_a_row_are_not_back_the_next_month(self) -> None:
        burst = {52: 5.0, 53: 4.5}
        found = _by_id(_observe([_history(lambda k, _m: 5_000.0 * burst.get(k, 1))]))
        spike = found["spike:astronomy/uk"].statement
        assert spike.startswith("From January 2025 to February 2025")
        assert "for 2 months, then it was back" in spike
        assert "the next month it was back" not in spike

    def test_a_burst_in_the_latest_month_is_not_said_to_be_over(self) -> None:
        found = _by_id(_observe([_history(lambda k, _m: 5_000.0 * (8 if k == MONTHS - 1 else 1))]))
        spike = found["spike:astronomy/uk"].statement
        assert "whether it lasts is not known yet" in spike
        assert "it was back" not in spike

    def test_a_flat_abrupt_plateau_looks_automated(self) -> None:
        found = _by_id(_observe([_history(lambda k, _m: 5_000.0 * (5 if 50 <= k < 62 else 1))]))
        unusual = found["unusual:astronomy/uk"]
        assert unusual.weight is Weight.CAUTION
        assert "probably automated traffic" in unusual.statement
        assert "spike:astronomy/uk" not in found

    @pytest.mark.parametrize("growth", [15, 30])
    def test_a_steady_rise_is_neither_a_wave_nor_automated(self, growth: int) -> None:
        """Held to the median of all six years, its last months looked far above usual."""
        found = _by_id(_observe([_history(lambda k, _m: 1_000.0 * growth ** (k / (MONTHS - 1)))]))
        assert not [oid for oid in found if oid.startswith(("wave:", "unusual:"))]
        assert "rose almost every year" in found["long_term:astronomy/uk"].statement

    def test_a_run_that_lasts_to_the_end_did_not_go_back(self) -> None:
        found = _by_id(_observe([_history(lambda k, _m: 5_000.0 * (5 if k >= MONTHS - 10 else 1))]))
        assert not [oid for oid in found if oid.startswith(("wave:", "unusual:"))]

    def test_a_long_wave_gives_its_months_as_a_number_a_text_may_repeat(self) -> None:
        """The template's own "for 22 months" was rejected: 22 was in no observation."""
        found = _by_id(_observe([_history(lambda k, _m: 5_000.0 * (5 if 48 <= k < 70 else 1))]))
        unusual = found["unusual:astronomy/uk"]
        assert "for 22 months" in unusual.statement
        assert any(q.value == 22 and not q.percent for q in unusual.numbers)

    def test_a_short_uneven_run_is_a_wave_of_attention(self) -> None:
        run = {56: 4, 57: 7, 58: 5}
        found = _by_id(_observe([_history(lambda k, _m: 5_000.0 * run.get(k, 1))]))
        assert "wave of attention" in found["wave:astronomy/uk"].statement

    def test_a_lasting_step_names_its_month(self) -> None:
        found = _by_id(_observe([_history(lambda k, _m: 6_000.0 if k < 50 else 2_500.0)]))
        step = found["step:2024-11:astronomy/uk"]
        assert "November 2024" in step.statement
        assert "the level stayed there" in step.statement

    def test_a_step_the_edition_took_too_is_not_the_topic(self) -> None:
        views = _history(
            lambda k, _m: 6_000.0 if k < 50 else 1_500.0,
            edition=lambda k: EDITION if k < 50 else EDITION * 0.5,
        )
        step = _by_id(_observe([views]))["step:2024-11:astronomy/uk"]
        assert "changed at the same time" in step.statement


class TestRecent:
    """The last three months are a note: a turn is never called on them."""

    def test_the_last_three_months_against_the_same_months_a_year_earlier(self) -> None:
        recent = _by_id(_observe([_history(_flat())]))["recent:astronomy/uk"]
        assert recent.weight is Weight.LOW
        assert "In the last three months (June–August 2026)" in recent.statement

    def test_months_that_run_against_the_trend_are_too_few_to_call_a_turn(self) -> None:
        def shape(k: int, m: date) -> float:
            base = 10_000.0 * math.pow(0.6, k / 12)
            return base * 2.0 if k >= MONTHS - 3 else base

        recent = _by_id(_observe([_history(shape)]))["recent:astronomy/uk"]
        assert recent.weight is Weight.MEDIUM
        assert "too few to call a turn" in recent.statement


class TestAcrossPairs:
    def test_two_editions_say_where_the_audience_and_the_interest_are(self) -> None:
        uk = _history(_flat(4_000.0))
        cs = _history(_flat(2_000.0), project="cs.wikipedia", edition=lambda _: EDITION / 4)
        found = _by_id(_observe([uk, cs]))
        editions = found["sections:astronomy"].statement
        assert "the Ukrainian Wikipedia is the larger audience (about twice as much)" in editions
        # Twice the views, half the attention: the Czech Wikipedia is four times smaller.
        assert "it is the other way round: the Czech Wikipedia gives the topic more" in editions
        assert "views per million" in editions
        assert found["decision:sections:astronomy"].statement == (
            "Interest in astronomy holds steady in both Wikipedias, with no sign of growth: the "
            "Ukrainian Wikipedia offers the larger existing audience."
        )

    def test_a_substitute_is_never_set_against_the_topic(self) -> None:
        uk = _history(_flat(4_000.0))
        pl = replace(_history(_flat(9_000.0), project="pl.wikipedia"), substitute="Post")
        found = _by_id(_observe([uk, pl]))
        assert "sections:astronomy" not in found
        assert "size:astronomy/pl" in found  # it keeps its own observations

    def test_an_order_of_magnitude_and_a_sharper_fall(self) -> None:
        ru = _history(_decline(80_000.0, 0.6), project="ru.wikipedia")
        uk = _history(_decline(60_000.0, 0.4), edition=lambda _: EDITION / 6)
        editions = _by_id(_observe([ru, uk]))["sections:astronomy"].statement
        assert "the Russian Wikipedia is the much larger audience" in editions
        assert "the gap narrows" in editions
        assert "both are read less: the Russian Wikipedia −40 %, the Ukrainian Wikipedia −60 %" in (
            editions
        )
        assert "more sharply in the Ukrainian Wikipedia" in editions
        assert "it declines in both" in editions

    def test_a_small_audience_that_grows_is_an_early_signal(self) -> None:
        en = _history(
            _decline(20_000.0, 0.8), project="en.wikipedia", edition=lambda _: EDITION * 8
        )
        uk = _history(lambda k, _m: 900.0 * 1.3 ** (k / 12), edition=lambda _: EDITION / 8)
        found = _by_id(_observe([en, uk]))
        editions = found["sections:astronomy"].statement
        assert "went down in the English Wikipedia (−20 %) and went up in the Ukrainian" in (
            editions
        )
        assert "it declines in the English Wikipedia and grows in the Ukrainian" in editions
        hint = found["decision:sections:astronomy"].statement
        assert "grows in the Ukrainian Wikipedia" in hint
        assert "an early signal" in hint
        assert "small base" in hint

    def test_the_larger_audience_with_the_stronger_verdict_is_the_signal(self) -> None:
        ru = _history(_flat(8_000.0), project="ru.wikipedia")
        cs = _history(_decline(9_000.0, 0.6), project="cs.wikipedia", edition=lambda _: EDITION / 8)
        hint = _by_id(_observe([ru, cs]))["decision:sections:astronomy"].statement
        assert hint == (
            "The Russian Wikipedia is the larger audience for astronomy and its interest holds "
            "steady, while in the Czech Wikipedia it declines: the Russian Wikipedia is the "
            "stronger signal of the two."
        )

    def test_about_the_same_audiences_say_so(self) -> None:
        pl = _history(_flat(3_300.0), project="pl.wikipedia")
        uk = _history(_flat(3_000.0))
        found = _by_id(_observe([pl, uk]))
        assert "opened about as often in" in found["sections:astronomy"].statement
        assert "holds steady in both Wikipedias" in found["decision:sections:astronomy"].statement

    def test_two_topics_in_one_edition_are_set_against_each_other(self) -> None:
        rising = _history(lambda k, _m: 1_000.0 * 1.5 ** (k / 12), topic="rust")
        falling = _history(_decline(), topic="python")
        found = _by_id(_observe([rising, falling]))
        topics = found["topics:uk"].statement
        assert "gets the most attention" in topics
        assert "rust grows, python declines" in topics
        assert "rust is the stronger candidate" in found["decision:topics:uk"].statement


class TestSignals:
    """What the window's verdict signals for the next check: never a decision to invest."""

    @pytest.mark.parametrize(
        ("views", "edition", "expected"),
        [
            (1.3, 1.0, "grows against its Wikipedia: a signal worth checking further"),
            (1.3, 1.3, "holds steady against its Wikipedia"),
            (0.6, 1.0, "is shrinking against its Wikipedia"),
            (0.8, 0.8, "holds steady against its Wikipedia"),
            (1.0, 1.3, "is shrinking against its Wikipedia"),
        ],
    )
    def test_the_share_makes_the_signal(self, views: float, edition: float, expected: str) -> None:
        history = _history(
            lambda k, _m: 5_000.0 * views ** (k / 12),
            edition=lambda k: EDITION * edition ** (k / 12),
        )
        verdict = _by_id(_observe([history]))["decision:verdict:astronomy/uk"].statement
        assert expected in verdict
        assert "invest" not in verdict


class TestSeasonEvidence:
    def test_a_steady_fall_is_no_season(self) -> None:
        # Against its own year's median, the first months of every year of a fall look high.
        found = _by_id(_observe([_history(_decline(10_000.0, 0.5))]))
        assert "decision:timing:astronomy/uk" not in found
        assert "no marked season" in found["season:astronomy/uk"].statement

    def test_three_years_are_limited_evidence(self) -> None:
        def january(k: int, m: date) -> float:
            return 1_000.0 * (1.6 if m.month == 1 else 1.0) * (1 + 0.02 * math.sin(k))

        found = _by_id(_observe([_history(january, count=42)]))
        assert "decision:timing:astronomy/uk" not in found
        season = found["season:astronomy/uk"]
        assert season.weight is Weight.LOW
        assert "limited evidence" in season.statement

    def test_a_peak_that_moves_between_months_is_limited_evidence(self) -> None:
        def wandering(k: int, m: date) -> float:
            peak = 1 if m.year % 2 else 4  # January in odd years, April in even ones
            return 1_000.0 * (1.8 if m.month == peak else 1.0) * (1 + 0.02 * math.sin(k))

        found = _by_id(_observe([_history(wandering)]))
        assert "decision:timing:astronomy/uk" not in found

    def test_a_school_rhythm_over_three_years_names_no_audience(self) -> None:
        found = _by_id(_observe([_history(_school, count=42)]))
        assert "decision:audience:astronomy/uk" not in found
        assert "like the school year" in found["season:astronomy/uk"].statement


class TestStatements:
    def test_every_number_a_statement_shows_is_one_it_quotes(self) -> None:
        def school(k: int, m: date) -> float:
            return 1_000.0 * math.pow(0.8, k / 12) * (4.0 if m.month == 9 else 1.0)

        for o in _observe([_history(school), _history(_flat(), project="cs.wikipedia")]):
            for number in extract_numbers(o.statement):
                if number.text == "12":  # "the 12 months before": a window, not a finding
                    continue
                assert any(matches(number, q.value, percent=q.percent) for q in o.numbers), (
                    o.id,
                    number.text,
                )

    def test_statements_open_with_a_capital_letter(self) -> None:
        for o in _observe([_history(_flat(), topic="шахматы")]):
            assert o.statement[0].isupper(), o.statement

    def test_the_size_gives_the_attention_share_per_million(self) -> None:
        size = _by_id(_observe([_history(_flat(5_000.0))]))["size:astronomy/uk"]
        assert size.weight is Weight.HIGH
        assert "views per million views of this Wikipedia" in size.statement
        assert any(49.5 < q.value < 50.5 for q in size.numbers)

    def test_editions_are_named_by_their_language(self) -> None:
        assert edition_name("pl.wikipedia") == "the Polish Wikipedia"
        assert edition_name("xx.wikipedia") == "xx.wikipedia"


class TestStepsBeyondTheTrend:
    """A step is a jump beyond the local trend, not what a steady trend moves in six months."""

    @pytest.mark.parametrize("per_year", [0.5, 0.64, 2.2])
    def test_a_steady_trend_of_any_speed_has_no_step(self, per_year: float) -> None:
        # -50 %, -36 % (the window's split used to fire here) and ×2.2 a year (×100 in six).
        history = _history(lambda k, _m: 10_000.0 * per_year ** (k / 12))
        steps, _, _ = pair_steps(history, threshold=TrustSettings().split_step)
        assert steps == []

    def test_a_step_on_a_falling_line_is_found_at_the_size_the_reader_sees(self) -> None:
        def shape(k: int, _m: date) -> float:
            return float(10_000.0 * 0.8 ** (k / 12)) * (0.5 if k >= 40 else 1.0)

        steps, _, _ = pair_steps(_history(shape))
        assert [s.index for s in steps] == [40]
        # The six months after against the six before: the step and half a year of the fall.
        assert steps[0].ratio == pytest.approx(0.5 * 0.8**0.5, rel=0.05)

    def test_a_peak_is_not_a_step_larger_than_the_levels_show(self) -> None:
        """A rise then a fall: the level moved little, whatever the slopes on either side."""

        def shape(k: int, _m: date) -> float:
            return 10_000.0 * (1.12 ** (k - 40) if k < 40 else 0.9 ** (k - 40))

        steps, _, _ = pair_steps(_history(shape), threshold=TrustSettings().split_step)
        assert all(abs(math.log(s.ratio)) >= math.log(1.25) for s in steps)
