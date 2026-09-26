"""Numbers written in prose, and whether they match known values.

The agent writes the report text; every figure in it must come from the facts the code
computed. Prose is messy (``12,3 %``, ``1 234``, ``−5 %``, ``27 proc.``, ``1.2k``), so a
token can have several readings (``1,234`` is 1234 or 1.234) and matches when any reading
is close to a known value, within the rounding the author implied (``38`` stands for 37.9).
"""

# ruff: noqa: RUF001, RUF002  -- the minus sign and narrow spaces are intentional.

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = ["ProseNumber", "extract_numbers", "matches"]

_YEAR_MIN, _YEAR_MAX = 1900, 2100
_YEAR_DIGITS = 4

# Dates, times, paths and identifiers (Q718, run ids) are not data claims.
_BLANK_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b"),
    re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}[./]\d{4}\b"),
    re.compile(r"\b\d{1,2}:\d{2}\b"),
    re.compile(r"\S*[/\\_]\S*\d\S*"),
    re.compile(r"\b[A-Za-z]+\d+\b"),
)

_SPACES = " \u00a0\u202f\u2009"  # space, no-break, narrow no-break, thin
_NUMBER = re.compile(
    rf"""
    (?<![\w.,])
    (?P<sign>[-−+])?
    (?P<body>
        \d{{1,3}}(?:[{_SPACES}]\d{{3}})+(?:[.,]\d+)?   # 1 234  |  1 234,5
      | \d{{1,3}}(?:,\d{{3}})+(?:\.\d+)?              # 1,234,567.8
      | \d+(?:[.,]\d+)?                             # 12 | 12.3 | 12,3
    )
    (?P<suffix>[kKM](?![\w]))?
    (?P<thousands>[{_SPACES}](?:тыс|тис|thousand|tys|tisíc|[Tt]ausend)\w*\.?)?
    (?P<percent>[{_SPACES}]?%|[{_SPACES}](?:percent|procent\w*|proc\.|процент\w*|проц\.
        |відсот\w*|відс\.|[Pp]rozent))?
    (?![\w.,]\d)
    """,
    re.VERBOSE,
)

_MULTIPLIERS = {"k": 1_000.0, "K": 1_000.0, "M": 1_000_000.0}
_THOUSAND = 1_000.0
"""The word in "18 тысяч" or "18 thousand" multiplies as "k" does."""


@dataclass(frozen=True, slots=True)
class ProseNumber:
    """One numeric token with every plausible reading of it.

    Attributes:
        text: The matched text.
        values: Candidate values; a percentage is kept as written (``12.5`` for ``12,5 %``).
        is_percent: Whether the token was written as a percentage.
        precisions: For each reading, half a unit of its last digit: the rounding the author
            implied. Each reading keeps its own: "1,234" read as 1.234 is exact to 0.0005, not
            to the 0.5 of its reading as 1234, which let it match anything from 0.73 to 1.73.
        signed: Whether the author wrote an explicit sign; unsigned numbers are magnitudes.
    """

    text: str
    values: tuple[float, ...]
    is_percent: bool
    precisions: tuple[float, ...]
    signed: bool = False

    @property
    def precision(self) -> float:
        """The coarsest rounding among the readings."""
        return max(self.precisions)


def extract_numbers(text: str, *, ignore_below: int = 10) -> list[ProseNumber]:
    """Numeric claims in ``text``.

    Ignored: dates, times, identifiers, four-digit years and integers below ``ignore_below``
    ("3 editions", "12 months" are counts, not data claims). Percentages and decimals are
    always kept.
    """
    cleaned = text
    for pattern in _BLANK_PATTERNS:
        cleaned = pattern.sub(lambda m: " " * len(m.group(0)), cleaned)
    out: list[ProseNumber] = []
    for match in _NUMBER.finditer(cleaned):
        number = _to_number(match)
        if number is not None and not _ignorable(match, ignore_below):
            out.append(number)
    return out


def matches(
    number: ProseNumber, value: float, *, percent: bool, tolerance_rel: float = 0.02
) -> bool:
    """Whether ``number`` states ``value``.

    Args:
        number: The token from prose.
        value: A known value on the scale prose writes it (``-19.5`` for a -0.195 change).
        percent: Whether ``value`` is a percentage; prose must write it as one.
        tolerance_rel: Relative slack on top of the author's rounding.
    """
    if number.is_percent != percent:
        return False
    target = value if number.signed else abs(value)
    return any(
        abs(reading - target) <= max(precision, tolerance_rel * abs(target))
        for reading, precision in zip(number.values, number.precisions, strict=True)
    )


def _to_number(match: re.Match[str]) -> ProseNumber | None:
    body = match.group("body")
    readings = _readings(body)
    if not readings:
        return None
    multiplier = _MULTIPLIERS.get(match.group("suffix") or "", 1.0)
    if match.group("thousands"):
        multiplier *= _THOUSAND
    sign = -1.0 if match.group("sign") in {"-", "−"} else 1.0
    return ProseNumber(
        text=match.group(0).strip(),
        values=tuple(sign * value * multiplier for value, _ in readings),
        is_percent=match.group("percent") is not None,
        precisions=tuple(0.5 * multiplier / (10**decimals) for _, decimals in readings),
        signed=match.group("sign") is not None,
    )


def _readings(body: str) -> list[tuple[float, int]]:
    """All plausible (value, decimals) readings of a numeric body."""
    if any(space in body for space in _SPACES):
        compact = re.sub(f"[{_SPACES}]", "", body).replace(",", ".")
        return [(float(compact), _decimals(compact))]
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", body):
        plain = body.replace(",", "")
        readings = [(float(plain), _decimals(plain))]
        if body.count(",") == 1 and "." not in body:
            decimal = body.replace(",", ".")
            readings.append((float(decimal), _decimals(decimal)))
        return readings
    if "," in body:
        decimal = body.replace(",", ".")
        return [(float(decimal), _decimals(decimal))]
    readings = [(float(body), _decimals(body))]
    if re.fullmatch(r"\d{1,3}\.\d{3}", body):
        readings.append((float(body.replace(".", "")), 0))
    return readings


def _decimals(text: str) -> int:
    return len(text.split(".")[1]) if "." in text else 0


def _ignorable(match: re.Match[str], ignore_below: int) -> bool:
    if any(match.group(g) for g in ("percent", "suffix", "thousands", "sign")):
        return False
    body = match.group("body")
    if not body.isdigit():
        return False
    value = int(body)
    if len(body) == _YEAR_DIGITS and _YEAR_MIN <= value <= _YEAR_MAX:
        return True
    return value < ignore_below
