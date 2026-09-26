"""Locale-aware number formatting for reports.

Reports in Ukrainian, Russian, Polish and Czech use a space as the thousands separator and a
comma as the decimal separator; English uses the reverse. The functions here take an explicit
:class:`NumberStyle` so the rest of the code never consults the process locale (which would
make output depend on the machine that produced it).
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["NumberStyle", "format_number", "format_percent", "localise_separators", "style_for"]

NARROW_NO_BREAK_SPACE = "\u202f"
"""Thousands separator for the Slavic locales: keeps ``12 345`` on one line in PDF and HTML."""


@dataclass(frozen=True, slots=True)
class NumberStyle:
    """Separators used when printing numbers in one language."""

    thousands_sep: str
    decimal_sep: str


def style_for(language: str) -> NumberStyle:
    """Return the separators for ``language``; anything but English uses the space/comma style.

    Every supported non-English language of the skill (uk, ru, pl, cs) shares the same
    convention, so the mapping is a two-way switch rather than a per-language table.
    """
    if language == "en":
        return NumberStyle(thousands_sep=",", decimal_sep=".")
    return NumberStyle(thousands_sep=NARROW_NO_BREAK_SPACE, decimal_sep=",")


def localise_separators(text: str, style: NumberStyle) -> str:
    """Swap the Python-formatted separators (``,`` and ``.``) for those of ``style``.

    Expects the output of :func:`format` with a ``,`` grouping option, e.g. ``"1,234.5"``.
    A placeholder is used so a comma-decimal style does not collide with the grouping comma.
    """
    placeholder = "\0"
    return (
        text.replace(",", placeholder)
        .replace(".", style.decimal_sep)
        .replace(placeholder, style.thousands_sep)
    )


def format_number(value: float, style: NumberStyle, decimals: int = 0) -> str:
    """Format a number with grouping and ``decimals`` fractional digits in ``style``.

    A value that rounds to zero is written without a sign: "-0" read as a fall.
    """
    return localise_separators(f"{_unsigned_zero(value, decimals):,.{decimals}f}", style)


def format_percent(
    value: float, style: NumberStyle, decimals: int = 0, *, signed: bool = False
) -> str:
    """Format a fraction (``0.153``) as a percentage (``15%``), optionally with a leading sign.

    A thin space precedes the percent sign in the Slavic styles, following their typographic
    convention; English keeps ``15%``.
    """
    percent = _unsigned_zero(value * 100, decimals)
    sign = "+" if signed and percent > 0 else ""
    body = localise_separators(f"{percent:,.{decimals}f}", style)
    suffix = "%" if style.decimal_sep == "." else f"{NARROW_NO_BREAK_SPACE}%"
    return f"{sign}{body}{suffix}"


def _unsigned_zero(value: float, decimals: int) -> float:
    """``value`` rounded as it will be written, with no sign left on a zero ("-0 %", "+0 %")."""
    rounded = round(value, decimals)
    return 0.0 if rounded == 0 else rounded
