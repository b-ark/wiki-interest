"""Every deterministic grader on a positive and a negative example."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest
from pypdf import PdfWriter

from skill_evals.graders.deterministic import GradeContext, describe, grade, resolve_path
from skill_evals.providers.base import ToolCall
from skill_evals.scenarios import (
    AnswerContains,
    AnswerNotContains,
    CaveatsRelayed,
    ClarificationAsked,
    FileExists,
    MaxCostUsd,
    MaxTurns,
    NoToolCalled,
    NumbersGrounded,
    PdfPages,
    SummaryField,
    ToolCalled,
)
from tests.conftest import make_summary, make_trajectory, write_summary

RUN_PY = ToolCall(
    name="Bash",
    input={"command": "python scripts/run.py request.json"},
    command="python scripts/run.py request.json",
)
SKILL = ToolCall(name="Skill", input={"skill": "wiki-interest"}, command="wiki-interest")


def _pdf(path: Path, pages: int) -> Path:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def _ctx(
    tmp_path: Path,
    answer: str = "",
    *,
    tool_calls: Sequence[ToolCall] = (),
    num_turns: int = 3,
    cost: float | None = 0.01,
) -> GradeContext:
    trajectory = make_trajectory(answer, tool_calls=tool_calls, num_turns=num_turns, cost=cost)
    return GradeContext(case_dir=tmp_path / "artifacts", trajectory=trajectory)


def test_file_exists_positive_and_negative(tmp_path: Path) -> None:
    write_summary(tmp_path / "artifacts" / "runs" / "s" / "r1", make_summary())
    ctx = _ctx(tmp_path)
    assert grade(FileExists(type="file_exists", glob="**/summary.json"), ctx).passed
    assert not grade(FileExists(type="file_exists", glob="**/report.pdf"), ctx).passed
    assert not grade(
        FileExists(type="file_exists", glob="**/summary.json", min_count=2), ctx
    ).passed


def test_pdf_pages_positive_and_negative(tmp_path: Path) -> None:
    _pdf(tmp_path / "artifacts" / "one" / "report.pdf", 1)
    ctx = _ctx(tmp_path)
    assert grade(PdfPages(type="pdf_pages", glob="one/report.pdf"), ctx).passed
    _pdf(tmp_path / "artifacts" / "two" / "report.pdf", 2)
    outcome = grade(PdfPages(type="pdf_pages", glob="**/report.pdf", max_pages=1), ctx)
    assert not outcome.passed
    assert "2 page(s)" in outcome.evidence
    assert not grade(PdfPages(type="pdf_pages", glob="none/*.pdf"), ctx).passed


def test_pdf_pages_unreadable_file_fails(tmp_path: Path) -> None:
    bad = tmp_path / "artifacts" / "report.pdf"
    bad.parent.mkdir(parents=True)
    bad.write_bytes(b"not a pdf")
    assert not grade(PdfPages(type="pdf_pages", glob="report.pdf"), _ctx(tmp_path)).passed


def test_numbers_grounded_positive_and_negative(tmp_path: Path) -> None:
    write_summary(tmp_path / "artifacts" / "runs" / "s" / "r1", make_summary())
    good = _ctx(tmp_path, "Average 1 234 views/month, growth +23.4 % (p = 0.012).")
    assert grade(NumbersGrounded(type="numbers_grounded"), good).passed
    bad = _ctx(tmp_path, "Average 9 999 views/month, growth +23.4 %.")
    outcome = grade(NumbersGrounded(type="numbers_grounded"), bad)
    assert not outcome.passed
    assert "9 999" in outcome.evidence


def test_numbers_grounded_fails_without_summary(tmp_path: Path) -> None:
    outcome = grade(NumbersGrounded(type="numbers_grounded"), _ctx(tmp_path, "grew 50 %"))
    assert not outcome.passed
    assert "no summary.json" in outcome.evidence


def test_numbers_grounded_unions_all_summaries(tmp_path: Path) -> None:
    write_summary(tmp_path / "artifacts" / "r1", make_summary(views_avg=100.0))
    write_summary(tmp_path / "artifacts" / "r2", make_summary(views_avg=555.0))
    ctx = _ctx(tmp_path, "first run 100 views, second run 555 views")
    assert grade(NumbersGrounded(type="numbers_grounded"), ctx).passed


def test_answer_contains_all_and_any(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "Polish grows faster than Czech.")
    assert grade(AnswerContains(type="answer_contains", patterns=["polish", "czech"]), ctx).passed
    assert not grade(
        AnswerContains(type="answer_contains", patterns=["polish", "german"]), ctx
    ).passed
    assert grade(
        AnswerContains(type="answer_contains", patterns=["polish", "german"], mode="any"), ctx
    ).passed


def test_answer_not_contains(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "I computed the growth myself.")
    assert not grade(AnswerNotContains(type="answer_not_contains", patterns=["myself"]), ctx).passed
    assert grade(AnswerNotContains(type="answer_not_contains", patterns=["pineapple"]), ctx).passed


def test_tool_called_matches_command_and_skill(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "", tool_calls=[SKILL, RUN_PY])
    assert grade(ToolCalled(type="tool_called", pattern=r"run\.py"), ctx).passed
    assert grade(ToolCalled(type="tool_called", pattern=r"^Skill wiki-interest"), ctx).passed
    assert not grade(ToolCalled(type="tool_called", pattern=r"pip install"), ctx).passed


def test_no_tool_called(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "", tool_calls=[RUN_PY])
    assert grade(NoToolCalled(type="no_tool_called", pattern=r"curl"), ctx).passed
    assert not grade(NoToolCalled(type="no_tool_called", pattern=r"run\.py"), ctx).passed


def test_max_turns(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "", num_turns=7)
    assert grade(MaxTurns(type="max_turns", n=7), ctx).passed
    assert not grade(MaxTurns(type="max_turns", n=6), ctx).passed


def test_max_cost(tmp_path: Path) -> None:
    ctx = _ctx(tmp_path, "", cost=0.05)
    assert grade(MaxCostUsd(type="max_cost_usd", value=0.05), ctx).passed
    assert not grade(MaxCostUsd(type="max_cost_usd", value=0.04), ctx).passed
    unknown = grade(MaxCostUsd(type="max_cost_usd", value=0.01), _ctx(tmp_path, "", cost=None))
    assert unknown.passed
    assert "no cost" in unknown.evidence


def test_summary_field_equals_and_regex(tmp_path: Path) -> None:
    write_summary(tmp_path / "artifacts" / "r1", make_summary(level="medium"))
    ctx = _ctx(tmp_path)
    assert grade(
        SummaryField(type="summary_field", path="reliability[0].level", equals="medium"), ctx
    ).passed
    assert grade(
        SummaryField(type="summary_field", path="reliability.0.level", regex="^med"), ctx
    ).passed
    assert grade(
        SummaryField(type="summary_field", path="metrics[0].growth_yoy", equals=0.234), ctx
    ).passed
    assert not grade(
        SummaryField(type="summary_field", path="reliability[0].level", equals="high"), ctx
    ).passed
    missing = grade(SummaryField(type="summary_field", path="nope.x", equals=1), ctx)
    assert not missing.passed
    assert "<missing>" in missing.evidence


def test_resolve_path_variants() -> None:
    data = {"a": [{"b": {"c": 5}}]}
    assert resolve_path(data, "a[0].b.c") == 5
    assert resolve_path(data, "a.0.b.c") == 5
    with pytest.raises(KeyError):
        resolve_path(data, "a.0.z")


CHECKS: list[dict[str, object]] = [
    {
        "name": "spike_share",
        "status": "warn",
        "message": "Growth is driven by news spikes.",
        "reason_key": "spike_share_warn",
    },
    {
        "name": "period",
        "status": "pass",
        "message": "Period is long enough.",
        "reason_key": "period_ok",
    },
    {
        "name": "completeness",
        "status": "fail",
        "message": "Only 60 % of months have data.",
        "reason_key": "completeness_fail",
    },
]


def test_caveats_relayed_positive_negative_and_vacuous(tmp_path: Path) -> None:
    write_summary(tmp_path / "artifacts" / "r1", make_summary(level="low", checks=CHECKS))
    relayed = _ctx(
        tmp_path, "Caution: the growth is mostly driven by news spikes, so trust is low."
    )
    assert grade(CaveatsRelayed(type="caveats_relayed"), relayed).passed
    silent = _ctx(tmp_path, "Interest is growing strongly. Invest now.")
    outcome = grade(CaveatsRelayed(type="caveats_relayed"), silent)
    assert not outcome.passed
    assert "0/2" in outcome.evidence
    assert not grade(CaveatsRelayed(type="caveats_relayed", min_reasons=2), relayed).passed


def test_caveats_relayed_vacuous_when_high(tmp_path: Path) -> None:
    write_summary(tmp_path / "artifacts" / "r1", make_summary(level="high", checks=CHECKS))
    outcome = grade(CaveatsRelayed(type="caveats_relayed"), _ctx(tmp_path, "All good."))
    assert outcome.passed
    assert "nothing to relay" in outcome.evidence


def test_clarification_asked(tmp_path: Path) -> None:
    asked = _ctx(tmp_path, "Did you mean the planet or the element?")
    assert grade(ClarificationAsked(type="clarification_asked"), asked).passed
    stated = _ctx(tmp_path, "I picked the planet.")
    assert not grade(ClarificationAsked(type="clarification_asked"), stated).passed
    _pdf(tmp_path / "artifacts" / "runs" / "x" / "report.pdf", 1)
    assert not grade(ClarificationAsked(type="clarification_asked"), asked).passed


def test_describe_is_readable() -> None:
    text = describe(MaxTurns(type="max_turns", n=5))
    assert text == "max_turns(n=5)"
