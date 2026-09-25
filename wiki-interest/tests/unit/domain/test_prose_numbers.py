"""Numbers in prose: readings, ignored tokens, matching within the author's rounding."""

# ruff: noqa: RUF001  -- the minus sign and Cyrillic words are intentional.

from __future__ import annotations

import pytest

from wiki_interest.domain.prose_numbers import extract_numbers, matches

NNBSP = chr(0x202F)


def _only(text: str) -> tuple[tuple[float, ...], bool, bool]:
    (number,) = extract_numbers(text)
    return number.values, number.is_percent, number.signed


@pytest.mark.parametrize(
    ("text", "values", "percent", "signed"),
    [
        ("share −19,5 %", (-19.5,), True, True),
        (f"+3,9{NNBSP}%", (3.9,), True, True),
        ("views 3 790 a month", (3790.0,), False, False),
        (f"views 3{NNBSP}790", (3790.0,), False, False),
        ("1,234 views", (1234.0, 1.234), False, False),
        ("37.9 per million", (37.9,), False, False),
        ("about 1.2k views", (1200.0,), False, False),
        ("+21%", (21.0,), True, True),
        ("около 18 тысяч просмотров", (18000.0,), False, False),
        ("1,3 тис. переглядів", (1300.0,), False, False),
        ("about 18 thousand views", (18000.0,), False, False),
        ("udział wzrósł o 27 proc. wobec", (27.0,), True, False),
        ("впала на 27 відс. за рік", (27.0,), True, False),
        ("упала на 27 проц. за год", (27.0,), True, False),
        ("klesl o 27 procent", (27.0,), True, False),
    ],
)
def test_readings(text: str, values: tuple[float, ...], percent: bool, signed: bool) -> None:
    assert _only(text) == (values, percent, signed)


@pytest.mark.parametrize(
    "text",
    [
        "in 2024-06 the views doubled",
        "from 03.09.2024",
        "item Q718",
        "over 2025",
        "3 editions and 9 months",
        "runs/astro/20260922-1200",
    ],
)
def test_dates_ids_years_and_small_counts_are_not_claims(text: str) -> None:
    assert extract_numbers(text) == []


def test_small_counts_are_claims_when_asked() -> None:
    assert [n.values for n in extract_numbers("3 months", ignore_below=0)] == [(3.0,)]


class TestMatches:
    def test_rounding_the_author_implied_is_accepted(self) -> None:
        (number,) = extract_numbers("−20 %")
        assert matches(number, -19.5, percent=True)
        (number,) = extract_numbers("38 per million")
        assert matches(number, 37.9, percent=False)

    def test_a_different_value_is_not(self) -> None:
        (number,) = extract_numbers("−25 %")
        assert not matches(number, -19.5, percent=True)

    def test_unsigned_numbers_are_magnitudes_signed_ones_keep_their_sign(self) -> None:
        (unsigned,) = extract_numbers("fell by 19,5 %")
        assert matches(unsigned, -19.5, percent=True)
        (signed,) = extract_numbers("+19,5 %")
        assert not matches(signed, -19.5, percent=True)

    def test_a_percentage_never_matches_a_plain_value(self) -> None:
        (number,) = extract_numbers("37,9 %")
        assert not matches(number, 37.9, percent=False)
