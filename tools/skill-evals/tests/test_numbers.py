"""Number extraction edge cases and the grounding check."""

from __future__ import annotations

import pytest

from skill_evals.graders.numbers import extract_numbers, ground_numbers, summary_numeric_leaves


def _values(text: str, **kwargs: int) -> list[tuple[float, ...]]:
    return [n.values for n in extract_numbers(text, **kwargs)]


def test_plain_decimal_and_comma_decimal() -> None:
    assert _values("growth 12.3 and 12,3") == [(12.3,), (12.3,)]


def test_percent_with_and_without_space() -> None:
    numbers = extract_numbers("up 12,3 % then 5% and 7 percent")
    assert [n.values[0] for n in numbers] == [12.3, 5.0, 7.0]
    assert all(n.is_percent for n in numbers)


def test_space_thousands_separator_including_nbsp() -> None:
    assert _values("1 234 views and 2 345 more, 3 456") == [(1234.0,), (2345.0,), (3456.0,)]


def test_comma_thousands_is_ambiguous_with_one_group() -> None:
    assert _values("1,234 views") == [(1234.0, 1.234)]
    assert _values("1,234,567 views") == [(1234567.0,)]


def test_dot_thousands_is_ambiguous() -> None:
    assert _values("1.234 views") == [(1.234, 1234.0)]


def test_k_and_m_suffixes() -> None:
    assert _values("1.2k users, 3M views, 2 тис. переглядів, 1,5 млн") == [
        (1200.0,),
        (3_000_000.0,),
        (2000.0,),
        (1_500_000.0,),
    ]


def test_precision_reflects_written_digits() -> None:
    (n,) = extract_numbers("1.2k")
    assert n.precision == pytest.approx(50.0)
    (n,) = extract_numbers("12.34")
    assert n.precision == pytest.approx(0.005)


def test_negative_numbers_including_unicode_minus() -> None:
    assert _values("fell −5.4% and -12 %") == [(-5.4,), (-12.0,)]


def test_years_and_dates_are_ignored() -> None:
    assert _values("from 2024-09 to 2026-08, since 2015, on 01.09.2024 at 10:30") == []


def test_small_integers_are_ignored_by_default() -> None:
    assert _values("3 charts, 2 languages, 24 months") == [(24.0,)]
    assert _values("3 charts", ignore_below=0) == [(3.0,)]


def test_small_percentages_and_floats_are_kept() -> None:
    assert _values("5% and 3.5") == [(5.0,), (3.5,)]


def test_paths_and_identifiers_are_ignored() -> None:
    text = "see runs/s1/run-20260922-abc/report.pdf and Q1666254 and file_2024.json"
    assert _values(text) == []


def test_ranges_yield_both_ends() -> None:
    assert _values("between 10–15 and 100-200") == [(10.0,), (15.0,), (100.0,), (200.0,)]


def test_summary_leaves_include_numbers_inside_strings() -> None:
    leaves = summary_numeric_leaves(
        {"a": 1.5, "b": [2, {"c": True, "d": "grew 23.4 % to 1 200"}], "e": "2024-09"}
    )
    assert 1.5 in leaves
    assert 2.0 in leaves
    assert 23.4 in leaves
    assert 1200.0 in leaves
    assert 2024.0 not in leaves
    assert True not in [type(x) is bool for x in leaves]


def test_grounded_when_numbers_match_leaves_within_tolerance() -> None:
    report = ground_numbers("Average 1 235 views, growth 23 %", [1234.5, 0.234])
    assert report.passed
    assert len(report.checked) == 2


def test_percent_matches_fraction_times_100() -> None:
    assert ground_numbers("grew 23.4%", [0.234]).passed
    assert not ground_numbers("grew 33.4%", [0.234]).passed


def test_rounded_suffix_number_is_grounded() -> None:
    assert ground_numbers("about 1.2k views", [1234.0]).passed
    assert not ground_numbers("about 1.3k views", [1234.0]).passed


def test_ungrounded_number_is_reported() -> None:
    report = ground_numbers("views 999 and 1 234", [1234.0])
    assert not report.passed
    assert [n.text for n in report.ungrounded] == ["999"]


def test_empty_answer_is_trivially_grounded() -> None:
    assert ground_numbers("no numbers here", [1.0]).passed


def test_unsigned_magnitude_matches_a_negative_leaf() -> None:
    report = ground_numbers("interest fell by 45 % year over year", [-0.4497])
    assert report.passed


def test_explicit_sign_must_match() -> None:
    assert ground_numbers("growth of +45 %", [-0.4497]).ungrounded
    assert ground_numbers("growth of -45 %", [-0.4497]).passed
