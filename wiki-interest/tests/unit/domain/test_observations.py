"""Observations: each detector fires on the shape it describes, and only then.

The series are synthetic: 72 months from 2020-09 of an article in an edition with a steady
100 million views a month, shaped by a trend, a calendar rhythm or an event. Numbers in a
statement are the numbers it quotes, so a text citing it may quote them.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date

import pytest

from wiki_interest.domain.observations import (
    Observation,
    PairHistory,
    Weight,
    edition_name,
    observe,
)
from wiki_interest.domain.prose_numbers import extract_numbers, matches

EDITION = 100_000_000.0
MONTHS = 72


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


def _by_id(observations: list[Observation]) -> dict[str, Observation]:
    return {o.id: o for o in observations}


def _flat(level: float = 5_000.0) -> Callable[[int, date], float]:
    return lambda k, _m: level * (1 + 0.02 * math.sin(k))


def _decline(start: float = 10_000.0, yearly: float = 0.75) -> Callable[[int, date], float]:
    return lambda k, _m: start * yearly ** (k / 12) * (1 + 0.02 * math.sin(k))


class TestTrends:
    def test_a_steady_decline_is_long_and_shared_by_no_one(self) -> None:
        found = _by_id(observe([_history(_decline())]))
        long_term = found["long_term:astronomy/uk"]
        assert long_term.weight is Weight.HIGH
        assert "A long, steady decline" in long_term.statement
        assert "September 2020 – August 2021" in long_term.statement
        assert "loses attention" in found["vs_edition:astronomy/uk"].statement
        assert "no growing interest" in found["decision:verdict:astronomy/uk"].statement

    def test_a_rise_that_came_back_is_a_wave(self) -> None:
        def wave(k: int, _m: date) -> float:
            return 5_000.0 * (1 + 1.5 * math.exp(-(((k - 30) / 10) ** 2)))

        long_term = _by_id(observe([_history(wave)]))["long_term:astronomy/uk"]
        assert "was highest in" in long_term.statement
        assert "A wave that has passed" in long_term.statement

    def test_views_that_fall_with_the_edition_are_not_the_topic(self) -> None:
        shrinking = _history(
            lambda k, _m: 5_000.0 * 0.8 ** (k / 12), edition=lambda k: EDITION * 0.8 ** (k / 12)
        )
        found = _by_id(observe([shrinking]))
        vs = found["vs_edition:astronomy/uk"].statement
        assert "comes from Wikipedia losing readers, not from the topic" in vs
        assert "neither supports nor rules out" in found["decision:verdict:astronomy/uk"].statement

    def test_a_named_short_period_reads_no_long_trend_but_the_season(self) -> None:
        def school(k: int, m: date) -> float:
            return 1_000.0 * (4.0 if m.month == 9 else 0.4 if m.month in (6, 7, 8) else 1.0)

        found = _by_id(observe([_history(school)], trend_start=date(2024, 9, 1)))
        assert "long_term:astronomy/uk" not in found
        assert "school-year rhythm" in found["season:astronomy/uk"].statement

    def test_an_article_younger_than_the_window_is_read_from_its_first_month(self) -> None:
        young = _history(lambda k, _m: None if k < 50 else 1_000.0)  # type: ignore[arg-type,return-value]
        found = _by_id(observe([young]))
        assert "long_term:astronomy/uk" not in found
        assert "season:astronomy/uk" not in found
        assert "size:astronomy/uk" in found


class TestCalendar:
    def test_a_september_peak_and_an_empty_summer_are_school_readers(self) -> None:
        def school(k: int, m: date) -> float:
            return 1_000.0 * (4.0 if m.month == 9 else 0.4 if m.month in (6, 7, 8) else 1.0)

        found = _by_id(observe([_history(school)]))
        season = found["season:astronomy/uk"]
        assert season.weight is Weight.HIGH
        assert "peaks in September" in season.statement
        audience = found["decision:audience:astronomy/uk"]
        assert "school year" in audience.statement
        assert "be ready by August" in audience.statement

    def test_a_january_peak_times_a_launch(self) -> None:
        def resolutions(k: int, m: date) -> float:
            return 1_000.0 * (1.6 if m.month == 1 else 0.9)

        found = _by_id(observe([_history(resolutions)]))
        assert "strongest in January" in found["season:astronomy/uk"].statement
        assert "ready by December" in found["decision:timing:astronomy/uk"].statement

    def test_no_rhythm_is_said_plainly(self) -> None:
        season = _by_id(observe([_history(_flat())]))["season:astronomy/uk"]
        assert season.weight is Weight.LOW
        assert "no marked season" in season.statement


class TestEvents:
    def test_one_month_far_above_its_calendar_month_is_a_spike(self) -> None:
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * (8 if k == 40 else 1))]))
        spike = found["spike:astronomy/uk"]
        assert "January 2024" in spike.statement
        assert "not lasting interest" in spike.statement

    def test_a_flat_abrupt_plateau_looks_automated(self) -> None:
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * (5 if 20 <= k < 40 else 1))]))
        unusual = found["unusual:astronomy/uk"]
        assert unusual.weight is Weight.CAUTION
        assert "probably automated traffic" in unusual.statement
        assert "spike:astronomy/uk" not in found

    def test_a_short_uneven_run_is_a_wave_of_attention(self) -> None:
        run = {20: 4, 21: 7, 22: 5}
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * run.get(k, 1))]))
        assert "wave of attention" in found["wave:astronomy/uk"].statement

    def test_a_lasting_step_names_its_month(self) -> None:
        found = _by_id(observe([_history(lambda k, _m: 6_000.0 if k < 50 else 2_500.0)]))
        step = found["step:astronomy/uk"]
        assert "November 2024" in step.statement
        assert "the level stayed there" in step.statement

    def test_a_step_the_edition_took_too_is_not_the_topic(self) -> None:
        views = _history(
            lambda k, _m: 6_000.0 if k < 50 else 1_500.0,
            edition=lambda k: EDITION if k < 50 else EDITION * 0.5,
        )
        step = _by_id(observe([views]))["step:astronomy/uk"]
        assert "changed at the same time" in step.statement


class TestRecent:
    @pytest.mark.parametrize(
        ("last_months", "expected"),
        [
            (2.0, "the fall stopped"),
            (0.2, "the fall speeds up"),
        ],
    )
    def test_the_last_three_months_against_the_year(
        self, last_months: float, expected: str
    ) -> None:
        def shape(k: int, m: date) -> float:
            base = 10_000.0 * math.pow(0.6, k / 12)
            return base * last_months if k >= MONTHS - 3 else base

        assert expected in _by_id(observe([_history(shape)]))["recent:astronomy/uk"].statement


class TestAcrossPairs:
    def test_two_editions_say_where_the_audience_and_the_interest_are(self) -> None:
        uk = _history(_flat(4_000.0))
        cs = _history(_flat(2_000.0), project="cs.wikipedia", edition=lambda _: EDITION / 4)
        found = _by_id(observe([uk, cs]))
        editions = found["editions:astronomy"].statement
        assert "about twice as much attention in the Czech Wikipedia" in editions
        assert "the Ukrainian Wikipedia is the bigger audience" in editions
        assert "start with the Ukrainian Wikipedia for reach" in (
            found["decision:editions:astronomy"].statement
        )

    def test_two_topics_in_one_edition_are_set_against_each_other(self) -> None:
        rising = _history(lambda k, _m: 1_000.0 * 1.5 ** (k / 12), topic="rust")
        falling = _history(_decline(), topic="python")
        found = _by_id(observe([rising, falling]))
        assert "gets the most attention" in found["topics:uk"].statement
        assert "rust is the stronger candidate" in found["decision:topics:uk"].statement


class TestStatements:
    def test_every_number_a_statement_shows_is_one_it_quotes(self) -> None:
        def school(k: int, m: date) -> float:
            return 1_000.0 * math.pow(0.8, k / 12) * (4.0 if m.month == 9 else 1.0)

        for o in observe([_history(school), _history(_flat(), project="cs.wikipedia")]):
            for number in extract_numbers(o.statement):
                if number.text == "12":  # "the 12 months before": a window, not a finding
                    continue
                assert any(matches(number, q.value, percent=q.percent) for q in o.numbers), (
                    o.id,
                    number.text,
                )

    def test_statements_open_with_a_capital_letter(self) -> None:
        for o in observe([_history(_flat(), topic="шахматы")]):
            assert o.statement[0].isupper(), o.statement

    def test_editions_are_named_by_their_language(self) -> None:
        assert edition_name("pl.wikipedia") == "the Polish Wikipedia"
        assert edition_name("xx.wikipedia") == "xx.wikipedia"
