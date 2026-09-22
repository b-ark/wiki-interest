"""Number extraction from prose and from ``summary.json``, and the grounding check.

The ``numbers_grounded`` assertion embodies the design rule "code thinks, the agent relays":
every figure in the agent's answer must come from the pipeline output. Prose is messy
(``12,3 %``, ``1 234``, ``1.2k``, ``−5 %``, Ukrainian/Russian suffixes), so extraction returns
several candidate interpretations for ambiguous tokens (``1,234`` is 1234 or 1.234) and a
number is grounded if any candidate matches any leaf. Rounding is tolerated at the precision
the author used (``1.2k`` means 1200 ± 50) in addition to the configured tolerances.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

__all__ = [
    "ExtractedNumber",
    "GroundingReport",
    "extract_numbers",
    "ground_numbers",
    "summary_numeric_leaves",
]

_YEAR_MIN, _YEAR_MAX = 1900, 2100
_YEAR_DIGITS = 4

# Tokens blanked out before extraction: dates, times, paths and identifiers such as run ids.
_BLANK_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?\b"),
    re.compile(r"\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"),
    re.compile(r"\b\d{1,2}[./]\d{4}\b"),
    re.compile(r"\b\d{1,2}:\d{2}\b"),
    re.compile(r"\S*[/\\_]\S*\d\S*"),
    re.compile(r"\b[A-Za-z]+\d+\b"),
)

_NUMBER = re.compile(
    r"""
    (?<![\w.,])
    (?P<sign>[-−+])?
    (?P<body>
        \d{1,3}(?:[   ]\d{3})+(?:[.,]\d+)?   # 1 234  |  1 234,5
      | \d{1,3}(?:,\d{3})+(?:\.\d+)?                    # 1,234,567.8
      | \d+(?:[.,]\d+)?                                 # 12 | 12.3 | 12,3
    )
    (?:
        (?P<suffix_word>\s?(?:тис\.|тыс\.|млн\.?|thousand|million))
      | (?P<suffix_letter>[kKM])
    )?
    (?P<percent>\s?(?:%|percent|відсотк\w*|процент\w*|п\.\s?п\.|pp\b))?
    (?![\w.,]\d)(?![A-Za-zА-Яа-яЁёІіЇїЄє])
    """,
    re.VERBOSE,
)

_MULTIPLIERS = {
    "k": 1_000.0,
    "K": 1_000.0,
    "M": 1_000_000.0,
    "тис.": 1_000.0,
    "тыс.": 1_000.0,
    "млн": 1_000_000.0,
    "млн.": 1_000_000.0,
    "thousand": 1_000.0,
    "million": 1_000_000.0,
}


@dataclass(frozen=True, slots=True)
class ExtractedNumber:
    """One numeric token from prose with every plausible reading of it.

    Attributes:
        text: The matched text.
        values: Candidate values after separators and suffixes are applied.
        is_percent: Whether the token was written as a percentage.
        precision: Half a unit of the last written digit (times any suffix), the rounding
            slack the author implied.
    """

    text: str
    values: tuple[float, ...]
    is_percent: bool
    precision: float


@dataclass(frozen=True, slots=True)
class GroundingReport:
    """Result of checking prose numbers against summary leaves."""

    checked: tuple[ExtractedNumber, ...]
    ungrounded: tuple[ExtractedNumber, ...]

    @property
    def passed(self) -> bool:
        """True when every checked number was found in the summary."""
        return not self.ungrounded


def extract_numbers(text: str, *, ignore_below: int = 10) -> list[ExtractedNumber]:
    """Extract numeric claims from prose.

    Ignored on purpose: dates and times, path-like tokens, four-digit years, and integers
    smaller than ``ignore_below`` (counts such as "3 charts" are not data claims). Percentages
    and non-integers are never ignored.
    """
    cleaned = text
    for pattern in _BLANK_PATTERNS:
        cleaned = pattern.sub(lambda m: " " * len(m.group(0)), cleaned)
    numbers: list[ExtractedNumber] = []
    for match in _NUMBER.finditer(cleaned):
        number = _to_number(match)
        if number is not None and not _ignorable(number, match, ignore_below):
            numbers.append(number)
    return numbers


def _to_number(match: re.Match[str]) -> ExtractedNumber | None:
    body = match.group("body")
    negative = match.group("sign") in {"-", "−"}
    suffix = (match.group("suffix_word") or match.group("suffix_letter") or "").strip()
    multiplier = _MULTIPLIERS.get(suffix, 1.0)
    readings = _readings(body)
    if not readings:
        return None
    sign = -1.0 if negative else 1.0
    values = tuple(sign * value * multiplier for value, _ in readings)
    decimals = min(d for _, d in readings)
    precision = 0.5 * multiplier / (10**decimals)
    return ExtractedNumber(
        text=match.group(0).strip(),
        values=values,
        is_percent=match.group("percent") is not None,
        precision=precision,
    )


def _readings(body: str) -> list[tuple[float, int]]:
    """All plausible (value, decimals) readings of a numeric body."""
    if re.search(r"[   ]", body):
        compact = re.sub(r"[   ]", "", body).replace(",", ".")
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


def _ignorable(number: ExtractedNumber, match: re.Match[str], ignore_below: int) -> bool:
    if number.is_percent or match.group("suffix_word") or match.group("suffix_letter"):
        return False
    body = match.group("body")
    if not body.isdigit():
        return False
    value = int(body)
    if len(body) == _YEAR_DIGITS and _YEAR_MIN <= value <= _YEAR_MAX:
        return True
    return value < ignore_below


def summary_numeric_leaves(data: object) -> list[float]:
    """Collect every number in a JSON document, including numbers written inside strings.

    Strings are included because the pipeline already formats figures into localised prose
    (verdict headline, check messages); an agent quoting those is grounded by definition.
    """
    leaves: list[float] = []
    _collect(data, leaves)
    return leaves


def _collect(node: object, out: list[float]) -> None:
    if isinstance(node, bool):
        return
    if isinstance(node, int | float):
        out.append(float(node))
    elif isinstance(node, str):
        for number in extract_numbers(node, ignore_below=0):
            out.extend(number.values)
    elif isinstance(node, dict):
        for value in node.values():
            _collect(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect(value, out)


def ground_numbers(
    text: str,
    leaves: Iterable[float],
    *,
    tolerance_rel: float = 0.02,
    tolerance_abs: float = 0.5,
    ignore_below: int = 10,
) -> GroundingReport:
    """Check that every number in ``text`` matches some leaf within tolerance.

    A percentage ``p`` also matches a leaf ``l`` when ``p ≈ l × 100`` (fractions in the
    summary, percentages in prose). Tolerance for a comparison is the largest of
    ``tolerance_abs``, ``tolerance_rel × |leaf|`` and the author's implied rounding precision.
    """
    pool = list(leaves)
    checked = tuple(extract_numbers(text, ignore_below=ignore_below))
    ungrounded = tuple(n for n in checked if not _grounded(n, pool, tolerance_rel, tolerance_abs))
    return GroundingReport(checked=checked, ungrounded=ungrounded)


def _grounded(number: ExtractedNumber, pool: list[float], rel: float, abs_tol: float) -> bool:
    targets = [(v, False) for v in number.values]
    if number.is_percent:
        targets += [(v / 100.0, True) for v in number.values]
    for value, scaled in targets:
        precision = number.precision / 100.0 if scaled else number.precision
        for leaf in pool:
            slack = max(abs_tol if not scaled else abs_tol / 100.0, rel * abs(leaf), precision)
            if abs(value - leaf) <= slack:
                return True
    return False
