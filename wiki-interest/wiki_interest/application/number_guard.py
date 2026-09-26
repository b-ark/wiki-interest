"""Use-case: every number of the report's text is a field of the result, or the render stops.

The agent's text is checked against the observations it cites before it is accepted; the
code's own lines (the headline, the verdict, trust and recommendation lines) are built from
fields. This guard checks the final text as it goes into the PDF, whoever wrote it: each
number must match a value of the summary (an observation's number, a verdict's level or
slope, a trust metric) within the rounding its writing implies. A mismatch is a bug, and a
report with a number nobody computed must not be written.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from wiki_interest.contracts.summary import AnalysisSummary, TrendOut, TrustOut
from wiki_interest.domain.prose_numbers import extract_numbers, matches
from wiki_interest.errors import RenderError

__all__ = ["check_report_numbers", "report_number_problems"]

_ALWAYS = (1.0, 12.0, 24.0, 1_000_000.0)
"""Windows and units any text may name: "12 months", "per 1 000 000 views"."""
_PERCENT = 100.0


@dataclass(frozen=True, slots=True)
class _Value:
    value: float
    percent: bool


def report_number_problems(summary: AnalysisSummary) -> list[str]:
    """Each number of the report's text that no field of ``summary`` holds, with its block."""
    allowed = list(_values(summary))
    names = _names(summary)
    problems: list[str] = []
    for block, text in _texts(summary):
        for number in extract_numbers(_without(text, names)):
            if not any(matches(number, a.value, percent=a.percent) for a in allowed):
                problems.append(f"{block}: '{number.text}' in «{text[:100]}»")
    return problems


def check_report_numbers(summary: AnalysisSummary) -> None:
    """Stop the render when a number of the text is not in the result.

    Raises:
        RenderError: Listing the numbers no field holds.
    """
    problems = report_number_problems(summary)
    if problems:
        msg = "Numbers in the report text are not in the result: " + "; ".join(problems[:5])
        raise RenderError(
            msg, hint="A template or an accepted text quotes a number the code did not compute."
        )


def _names(summary: AnalysisSummary) -> list[str]:
    """Names the text may carry whole: topics and neighbouring articles ("S&P 500").

    A number inside a name is part of the name, not a claim about the data (stage16: the
    next check "Тесла, S&P 500" stopped every report on Tesla).
    """
    names = [n for r in summary.resolution for n in (r.label, r.query) if n]
    for rec in summary.recommendations:
        if rec.next_check is not None:
            names += [i.label for i in rec.next_check.items]
    return sorted({n for n in names if any(ch.isdigit() for ch in n)}, key=len, reverse=True)


def _without(text: str, names: list[str]) -> str:
    """``text`` with every name blanked out, so its digits are not read as numbers."""
    for name in names:
        text = text.replace(name, " ")
    return text


def _texts(summary: AnalysisSummary) -> Iterator[tuple[str, str]]:
    """Every block of text the report prints that may carry a claim about the data.

    Not the topic line: it names the item with its description ("the chemical element Hg
    with atomic number 80", stage16), and a name is not a claim.
    """
    yield "headline", summary.verdict.headline
    for item in summary.verdicts:
        yield "verdict", item.line
        if item.trust is not None:
            yield "trust", item.trust.line
    for rec in summary.recommendations:
        yield "recommendation", rec.line
        yield "next check", rec.next_line
    for paragraph in summary.happening:
        yield "story", paragraph
    decision = summary.decision
    if decision is not None:
        if decision.summary:
            yield "meaning", decision.summary
        for line in decision.lines:
            yield "recommendation", line
        yield "next check", decision.next_step


def _values(summary: AnalysisSummary) -> Iterator[_Value]:
    """Every value of the result a text may quote, on the scale the text writes it."""
    for constant in _ALWAYS:
        yield _Value(constant, percent=False)
    for o in summary.observations:
        for q in o.numbers:
            yield _Value(q.value, q.percent)
    band = summary.provenance.thresholds.get("trust_stable_pct_per_year")
    if isinstance(band, int | float):
        yield _Value(float(band), percent=True)
    for item in summary.verdicts:
        yield from _verdict_values(item)
        if item.trust is not None:
            yield from _trust_values(item.trust)


def _verdict_values(item: TrendOut) -> Iterator[_Value]:
    for plain in (item.level_start, item.level_end, item.views_avg):
        if plain is not None:
            yield _Value(plain, percent=False)
    for pct in (item.slope_pct_per_year, item.step_change):
        if pct is not None:
            yield _Value(pct, percent=True)


def _trust_values(trust: TrustOut) -> Iterator[_Value]:
    for count in (trust.yoy_down, trust.yoy_up, trust.yoy_months, trust.control_articles):
        yield _Value(float(count), percent=False)
    for plain in (trust.snr, trust.views_avg):
        if plain is not None:
            yield _Value(plain, percent=False)
    for pct in (trust.slope_pct_per_year, trust.control_change):
        if pct is not None:
            yield _Value(pct, percent=True)
    for bound in trust.ci90 or ():
        yield _Value(bound, percent=False)
        yield _Value(bound, percent=True)
    for reason in trust.reasons:
        for name, param in reason.params.items():
            if isinstance(param, int | float) and not isinstance(param, bool):
                yield _Value(float(param), percent=name in ("band", "change", "slope"))
                yield _Value(float(param), percent=False)
    if trust.max_day_share is not None:
        yield _Value(trust.max_day_share * _PERCENT, percent=True)
