"""Observations: each detector fires on the shape it describes, and only then.

The series are synthetic: 72 months from 2020-09 to 2026-08 (full calendar years 2021–2025 and
a partial 2026) of an article in an edition with a steady 100 million views a month, shaped by
a trend, a calendar rhythm or an event. Numbers in a statement are the numbers it quotes, so a
text citing it may quote them.
"""

# ruff: noqa: RUF001  -- the statements write the minus sign, as the report does.

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace
from datetime import date

import pytest

from wiki_interest.domain.observations import (
    Observation,
    PairHistory,
    Quoted,
    Weight,
    edition_name,
    observe,
    share_move,
    year_levels,
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
        assert "in 2025 it was about a third of what it was in 2021" in long_term.statement
        assert "loses attention" in found["vs_edition:astronomy/uk"].statement
        verdict = found["decision:verdict:astronomy/uk"].statement
        assert "is shrinking, faster than its Wikipedia" in verdict
        assert "invest" not in verdict

    def test_a_rise_that_came_back_is_a_wave(self) -> None:
        def wave(k: int, _m: date) -> float:
            return 5_000.0 * (1 + 1.5 * math.exp(-(((k - 30) / 10) ** 2)))

        long_term = _by_id(observe([_history(wave)]))["long_term:astronomy/uk"]
        assert "was highest in" in long_term.statement
        assert "A wave that has passed" in long_term.statement

    @pytest.mark.parametrize(
        ("edition_yearly", "views_yearly", "says"),
        [
            (0.94, 1.03, "held its views (+3 %)"),  # the share rose 9.6 %, under the 10 % bar
            (1.30, 1.144, "is read more (+14 %"),  # the share fell 12 % in a growing edition
        ],
    )
    def test_the_views_verb_follows_the_views(
        self, edition_yearly: float, views_yearly: float, says: str
    ) -> None:
        """A share and an edition moving apart once gave "read less (+3 % views)"."""
        history = _history(
            lambda _k, m: 5_000.0 * views_yearly ** (m.year - 2020),
            edition=lambda k: EDITION * edition_yearly ** ((8 + k) // 12),
        )
        vs = _by_id(observe([history]))["vs_edition:astronomy/uk"].statement
        assert says in vs
        assert "read less (+" not in vs

    def test_views_that_fall_with_the_edition_are_not_the_topic(self) -> None:
        shrinking = _history(
            lambda k, _m: 5_000.0 * 0.8 ** (k / 12), edition=lambda k: EDITION * 0.8 ** (k / 12)
        )
        found = _by_id(observe([shrinking]))
        vs = found["vs_edition:astronomy/uk"].statement
        assert "comes from Wikipedia losing readers, not from the topic" in vs
        verdict = found["decision:verdict:astronomy/uk"].statement
        assert "read less, but no more than its Wikipedia" in verdict

    def test_a_named_short_period_reads_no_long_trend_but_the_season(self) -> None:
        found = _by_id(observe([_history(_school)], trend_start=date(2024, 9, 1)))
        assert "long_term:astronomy/uk" not in found
        assert "school-year rhythm" in found["season:astronomy/uk"].statement

    def test_an_article_younger_than_the_window_is_read_from_its_first_month(self) -> None:
        young = _history(lambda k, _m: None if k < 50 else 1_000.0)  # type: ignore[arg-type,return-value]
        found = _by_id(observe([young]))
        assert "long_term:astronomy/uk" not in found
        assert "season:astronomy/uk" not in found
        assert "size:astronomy/uk" in found


def _school(k: int, m: date) -> float:
    return 1_000.0 * (4.0 if m.month == 9 else 0.4 if m.month in (6, 7, 8) else 1.0)


class TestCalendarYears:
    """The level and the long view read calendar years, as the report's chart draws them."""

    def test_now_is_the_partial_last_year_and_then_the_first_full_one(self) -> None:
        size = _by_id(observe([_history(_flat())]))["size:astronomy/uk"].statement
        assert "times a month in January–August 2026" in size
        assert "In 2021 it was opened" in size

    def test_a_partial_year_with_too_few_months_gives_way_to_the_last_full_one(self) -> None:
        size = _by_id(observe([_history(_flat(), count=65)]))["size:astronomy/uk"].statement
        assert "times a month in 2025" in size
        assert "January 2026" not in size

    def test_the_long_view_reads_full_years_only(self) -> None:
        # January–August 2026 misses the September peak: read with 2021–2025 it would look
        # like a fall; read on full years the school rhythm is flat.
        found = _by_id(observe([_history(_school)]))
        long_term = found["long_term:astronomy/uk"]
        assert "stayed in the same range over 2021–2025" in long_term.statement
        size = found["size:astronomy/uk"].statement
        assert "January–August 2026 is not a full year" in size
        assert "set it against full years with care" in size

    def test_a_partial_year_without_a_season_needs_no_caution(self) -> None:
        size = _by_id(observe([_history(_flat())]))["size:astronomy/uk"].statement
        assert "not a full year" not in size

    def test_two_editions_are_set_against_each_other_over_the_same_months(self) -> None:
        uk = _history(_flat(4_000.0))
        cs = _history(_flat(2_000.0), project="cs.wikipedia", edition=lambda _: EDITION / 4)
        editions = _by_id(observe([uk, cs]))["editions:astronomy"].statement
        assert editions.startswith("In January–August 2026 the article")
        assert "Against the same months of 2025 both hold steady" in editions

    def test_a_partial_year_is_compared_with_the_same_months_a_year_earlier(self) -> None:
        # Set against the whole of 2025, January–August 2026 would lose the September peak.
        vs = _by_id(observe([_history(_school)]))["vs_edition:astronomy/uk"].statement
        assert vs.startswith("In January–August 2026 (against the same months of 2025)")
        assert "moved with the Ukrainian Wikipedia" in vs

    def test_a_full_last_year_is_compared_with_the_year_before(self) -> None:
        found = _by_id(observe([_history(_decline(), count=65)]))
        assert found["vs_edition:astronomy/uk"].statement.startswith("In 2025 (against 2024)")

    def test_each_year_carries_the_change_the_text_reads(self) -> None:
        history = _history(_decline(), edition=lambda k: EDITION * 0.9 ** (k / 12))
        years = year_levels(history)
        assert [y.year for y in years] == [2021, 2022, 2023, 2024, 2025, 2026]
        assert years[0].change is None  # no whole year of data before 2021
        last = years[-1].change
        assert last is not None
        assert last.share == pytest.approx(
            (1 + last.article / 100) / (1 + last.edition / 100) * 100 - 100
        )
        vs = _by_id(observe([history]))["vs_edition:astronomy/uk"]
        assert Quoted(round(last.share), percent=True) in vs.numbers
        assert share_move(last.share) == "lost"


@pytest.mark.parametrize(
    ("change", "move"), [(10.5, "gained"), (10.0, "held"), (-10.0, "held"), (-10.5, "lost")]
)
def test_a_share_moves_beyond_ten_percent(change: float, move: str) -> None:
    assert share_move(change) == move


class TestCalendar:
    def test_a_september_peak_and_an_empty_summer_are_school_readers(self) -> None:
        found = _by_id(observe([_history(_school)]))
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


def test_the_summer_drop_of_the_school_rhythm_names_a_summer_month() -> None:
    """The year's lowest month was January, and the text said "drops in summer (January)"."""
    level = {10: 1.8, 6: 0.8, 7: 0.8, 8: 0.8, 1: 0.6}
    found = _by_id(observe([_history(lambda _k, m: 5_000.0 * level.get(m.month, 1.0))]))
    season = found["season:astronomy/uk"].statement
    assert "drops in summer (" in season
    summer = season.split("drops in summer (", 1)[1]
    assert summer.startswith(("June", "July", "August")), season


class TestEvents:
    def test_one_month_far_above_its_calendar_month_is_a_spike(self) -> None:
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * (8 if k == 40 else 1))]))
        spike = found["spike:astronomy/uk"]
        assert "January 2024" in spike.statement
        assert "not lasting interest" in spike.statement

    def test_two_bursting_months_in_a_row_are_not_back_the_next_month(self) -> None:
        burst = {40: 5.0, 41: 4.5}
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * burst.get(k, 1))]))
        spike = found["spike:astronomy/uk"].statement
        assert spike.startswith("From January 2024 to February 2024")
        assert "for 2 months, then it was back" in spike
        assert "the next month it was back" not in spike

    def test_a_burst_in_the_latest_month_is_not_said_to_be_over(self) -> None:
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * (8 if k == MONTHS - 1 else 1))]))
        spike = found["spike:astronomy/uk"].statement
        assert "whether it lasts is not known yet" in spike
        assert "it was back" not in spike

    def test_a_flat_abrupt_plateau_looks_automated(self) -> None:
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * (5 if 20 <= k < 40 else 1))]))
        unusual = found["unusual:astronomy/uk"]
        assert unusual.weight is Weight.CAUTION
        assert "probably automated traffic" in unusual.statement
        assert "spike:astronomy/uk" not in found

    @pytest.mark.parametrize("growth", [15, 30])
    def test_a_steady_rise_is_neither_a_wave_nor_automated(self, growth: int) -> None:
        """Held to the median of all six years, its last months looked far above usual."""
        found = _by_id(observe([_history(lambda k, _m: 1_000.0 * growth ** (k / (MONTHS - 1)))]))
        assert not [oid for oid in found if oid.startswith(("wave:", "unusual:"))]
        assert "risen" in found["long_term:astronomy/uk"].statement

    def test_a_run_that_lasts_to_the_end_did_not_go_back(self) -> None:
        found = _by_id(observe([_history(lambda k, _m: 5_000.0 * (5 if k >= MONTHS - 10 else 1))]))
        assert not [oid for oid in found if oid.startswith(("wave:", "unusual:"))]

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

    @pytest.mark.parametrize(
        ("last_months", "expected"),
        [
            (0.5, "the rise stopped"),
            (0.66, "the rise levelled off"),  # +6 % after about +40 %: held, not "slower"
            (1.6, "the rise speeds up"),
        ],
    )
    def test_a_rise_is_told_as_a_fall_is(self, last_months: float, expected: str) -> None:
        def shape(k: int, m: date) -> float:
            base = 10_000.0 * math.pow(1.6, k / 12)
            return base * last_months if k >= MONTHS - 3 else base

        assert expected in _by_id(observe([_history(shape)]))["recent:astronomy/uk"].statement


class TestAcrossPairs:
    def test_two_editions_say_where_the_audience_and_the_interest_are(self) -> None:
        uk = _history(_flat(4_000.0))
        cs = _history(_flat(2_000.0), project="cs.wikipedia", edition=lambda _: EDITION / 4)
        found = _by_id(observe([uk, cs]))
        editions = found["editions:astronomy"].statement
        assert "the Ukrainian Wikipedia is the larger audience (about twice as much)" in editions
        # Twice the views, half the attention: the Czech Wikipedia is four times smaller.
        assert "it is the other way round: the Czech Wikipedia gives the topic more" in editions
        assert "(80.3 against 40.2 views per million" in editions
        assert "the article held attention share in both" in editions
        assert found["decision:editions:astronomy"].statement == (
            "The Ukrainian Wikipedia offers the larger existing audience, but neither edition "
            "shows growing interest in astronomy."
        )

    def test_a_substitute_is_never_set_against_the_topic(self) -> None:
        uk = _history(_flat(4_000.0))
        pl = replace(_history(_flat(9_000.0), project="pl.wikipedia"), substitute="Post")
        found = _by_id(observe([uk, pl]))
        assert "editions:astronomy" not in found
        assert "size:astronomy/pl" in found  # it keeps its own observations
        assert "Polish" not in found["headline:astronomy"].statement

    def test_an_order_of_magnitude_and_a_sharper_fall(self) -> None:
        ru = _history(_decline(80_000.0, 0.6), project="ru.wikipedia")
        uk = _history(_decline(6_000.0, 0.4), edition=lambda _: EDITION / 6)
        editions = _by_id(observe([ru, uk]))["editions:astronomy"].statement
        assert "the Russian Wikipedia is the much larger audience" in editions
        assert "the gap narrows" in editions
        assert "both are read less: the Russian Wikipedia −40 %, the Ukrainian Wikipedia −60 %" in (
            editions
        )
        assert "more sharply in the Ukrainian Wikipedia" in editions
        assert "lost attention share in both" in editions

    def test_a_small_audience_that_grows_is_an_early_signal(self) -> None:
        en = _history(
            _decline(20_000.0, 0.8), project="en.wikipedia", edition=lambda _: EDITION * 8
        )
        uk = _history(lambda k, _m: 900.0 * 1.3 ** (k / 12), edition=lambda _: EDITION / 8)
        found = _by_id(observe([en, uk]))
        editions = found["editions:astronomy"].statement
        assert "went down in the English Wikipedia (−20 %) and went up in the Ukrainian" in (
            editions
        )
        assert "lost attention share in the English Wikipedia and gained it in the Ukrainian" in (
            editions
        )
        hint = found["decision:editions:astronomy"].statement
        assert "only the Ukrainian Wikipedia grows: an early signal" in hint
        assert "small base" in hint

    def test_about_the_same_audiences_say_so(self) -> None:
        pl = _history(_flat(3_300.0), project="pl.wikipedia")
        uk = _history(_flat(3_000.0))
        found = _by_id(observe([pl, uk]))
        assert "opened about as often in" in found["editions:astronomy"].statement
        assert "about the same size, and neither grows" in (
            found["decision:editions:astronomy"].statement
        )

    def test_two_topics_in_one_edition_are_set_against_each_other(self) -> None:
        rising = _history(lambda k, _m: 1_000.0 * 1.5 ** (k / 12), topic="rust")
        falling = _history(_decline(), topic="python")
        found = _by_id(observe([rising, falling]))
        assert "gets the most attention" in found["topics:uk"].statement
        assert "rust is the stronger candidate" in found["decision:topics:uk"].statement


class TestSignals:
    """What Wikipedia signals for the next check: never a decision to invest."""

    @pytest.mark.parametrize(
        ("views", "edition", "expected"),
        [
            (1.3, 1.0, "grows, faster than its Wikipedia: a signal worth checking further"),
            (1.3, 1.3, "grows with its Wikipedia"),
            (1.3, 1.6, "grows, but more slowly than its Wikipedia: a weak signal"),
            (0.6, 1.0, "is shrinking, faster than its Wikipedia"),
            (0.8, 0.8, "read less, but no more than its Wikipedia"),
            (1.0, 0.7, "holds steady while its Wikipedia is read less"),
            (1.0, 1.0, "holds steady: Wikipedia shows neither growth nor a decline"),
            # Five years of a growing Wikipedia leave the share in a long decline.
            (1.0, 1.3, "holds steady now after a longer decline"),
        ],
    )
    def test_the_audience_and_its_share_make_the_signal(
        self, views: float, edition: float, expected: str
    ) -> None:
        history = _history(
            lambda k, _m: 5_000.0 * views ** (k / 12),
            edition=lambda k: EDITION * edition ** (k / 12),
        )
        verdict = _by_id(observe([history]))["decision:verdict:astronomy/uk"].statement
        assert expected in verdict
        assert "invest" not in verdict


class TestSeasonEvidence:
    def test_a_steady_fall_is_no_season(self) -> None:
        # Against its own year's median, the first months of every year of a fall look high.
        found = _by_id(observe([_history(_decline(10_000.0, 0.5))]))
        assert "decision:timing:astronomy/uk" not in found
        assert "no marked season" in found["season:astronomy/uk"].statement

    def test_three_years_are_limited_evidence(self) -> None:
        def january(k: int, m: date) -> float:
            return 1_000.0 * (1.6 if m.month == 1 else 1.0) * (1 + 0.02 * math.sin(k))

        found = _by_id(observe([_history(january, count=42)]))
        assert "decision:timing:astronomy/uk" not in found
        season = found["season:astronomy/uk"]
        assert season.weight is Weight.LOW
        assert "limited evidence" in season.statement

    def test_a_peak_that_moves_between_months_is_limited_evidence(self) -> None:
        def wandering(k: int, m: date) -> float:
            peak = 1 if m.year % 2 else 4  # January in odd years, April in even ones
            return 1_000.0 * (1.8 if m.month == peak else 1.0) * (1 + 0.02 * math.sin(k))

        found = _by_id(observe([_history(wandering)]))
        assert "decision:timing:astronomy/uk" not in found

    def test_a_school_rhythm_over_three_years_names_no_audience(self) -> None:
        found = _by_id(observe([_history(_school, count=42)]))
        assert "decision:audience:astronomy/uk" not in found
        assert "like the school year" in found["season:astronomy/uk"].statement


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

    def test_the_size_gives_the_attention_share_per_million(self) -> None:
        size = _by_id(observe([_history(_flat(5_000.0))]))["size:astronomy/uk"]
        assert size.weight is Weight.HIGH
        assert "views per million views of the edition" in size.statement
        assert any(q.value == 50.2 for q in size.numbers)

    def test_editions_are_named_by_their_language(self) -> None:
        assert edition_name("pl.wikipedia") == "the Polish Wikipedia"
        assert edition_name("xx.wikipedia") == "xx.wikipedia"
