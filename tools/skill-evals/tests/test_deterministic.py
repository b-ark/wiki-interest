"""Every deterministic grader on a positive and a negative example."""

from __future__ import annotations

import os
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
    ChatAnswerRelayed,
    ClarificationAsked,
    FileExists,
    MaxCostUsd,
    MaxTurns,
    NarrativeAccepted,
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


def test_clarification_asked_by_request_without_question_mark(tmp_path: Path) -> None:
    request = _ctx(tmp_path, "Nothing was found. Please send a link to a Wikipedia article.")
    plain = ClarificationAsked(type="clarification_asked")
    by_link = ClarificationAsked(type="clarification_asked", request_patterns=["(?i)link"])
    assert not grade(plain, request).passed
    outcome = grade(by_link, request)
    assert outcome.passed
    assert outcome.evidence.startswith("request")


def test_describe_is_readable() -> None:
    text = describe(MaxTurns(type="max_turns", n=5))
    assert text == "max_turns(n=5)"


def test_caveats_come_from_the_newest_summary_only(tmp_path: Path) -> None:
    abandoned = tmp_path / "artifacts" / "r1"
    final = tmp_path / "artifacts" / "r2"
    write_summary(abandoned, make_summary(level="low", checks=CHECKS))
    write_summary(final, make_summary(level="high", checks=CHECKS))
    os.utime(abandoned / "summary.json", (1_000, 1_000))
    os.utime(final / "summary.json", (2_000, 2_000))
    outcome = grade(CaveatsRelayed(type="caveats_relayed"), _ctx(tmp_path, "All good."))
    assert outcome.passed, outcome.evidence


def _render(run_dir: str, status: str) -> ToolCall:
    command = f"uv run scripts/render.py {run_dir} --narrative narrative.json"
    output = f'{{"status": "{status}", "exit_code": 0, "run_dir": "{run_dir}"}}'
    return ToolCall(name="Bash", input={"command": command}, command=command, result=output)


def test_narrative_accepted_counts_the_last_status_of_each_run(tmp_path: Path) -> None:
    check = NarrativeAccepted(type="narrative_accepted")
    fixed = [_render("runs/s/r1", "rejected"), _render("runs/s/r1", "accepted")]
    outcome = grade(check, _ctx(tmp_path, tool_calls=fixed))
    assert outcome.passed
    assert outcome.evidence == "1/1 rendered run(s) accepted"
    follow_up_fell_back = [
        *fixed,
        _render("runs/s/r2", "rejected"),
        _render("runs/s/r2", "fallback"),
    ]
    outcome = grade(check, _ctx(tmp_path, tool_calls=follow_up_fell_back))
    assert not outcome.passed
    assert "1/2" in outcome.evidence
    assert "fallback" in outcome.evidence


def test_narrative_accepted_reads_the_powershell_listing_of_the_output(tmp_path: Path) -> None:
    command = "uv run scripts/render.py runs\\s\\20260923-171010-345b --narrative n.json"
    listing = (
        "status      : accepted\nexit_code   : 0\nrun_dir     : runs\\s\\20260923-17101\n  0-345b"
    )
    rejected = '{"status": "rejected", "run_dir": "runs/s/20260923-171010-345b"}'
    calls = [
        ToolCall(name="PowerShell", input={}, command=command, result=rejected),
        ToolCall(name="PowerShell", input={}, command=command, result=listing),
    ]
    outcome = grade(NarrativeAccepted(type="narrative_accepted"), _ctx(tmp_path, tool_calls=calls))
    assert outcome.passed, outcome.evidence
    assert outcome.evidence == "1/1 rendered run(s) accepted"


def test_narrative_accepted_needs_a_render_with_the_agents_text(tmp_path: Path) -> None:
    check = NarrativeAccepted(type="narrative_accepted")
    assert not grade(check, _ctx(tmp_path)).passed
    plain = ToolCall(
        name="Bash",
        input={},
        command="uv run scripts/render.py runs/s/r1",
        result='{"status": "ok", "run_dir": "runs/s/r1"}',
    )
    crashed = ToolCall(
        name="Bash", input={}, command="render.py r1 --narrative n.json", result="Traceback"
    )
    outcome = grade(check, _ctx(tmp_path, tool_calls=[plain, crashed]))
    assert not outcome.passed
    assert outcome.evidence == "no render with the agent's text"


def _summary_in(language: str) -> dict[str, object]:
    summary = make_summary(level="low", checks=CHECKS)
    summary["request"] = {"report": {"language": language}}
    return summary


def test_caveats_of_another_language_come_from_the_accepted_text(tmp_path: Path) -> None:
    run_dir = tmp_path / "artifacts" / "r1"
    write_summary(run_dir, _summary_in("uk"))
    brief = "Частка уваги в pl.wikipedia зростає; але дані неповні: зростання дають сплески."
    (run_dir / "chat_brief.md").write_text(brief, encoding="utf-8")
    check = CaveatsRelayed(type="caveats_relayed")
    assert grade(check, _ctx(tmp_path, brief)).passed
    outcome = grade(check, _ctx(tmp_path, "Інтерес зростає, інвестуйте."))
    assert not outcome.passed
    assert outcome.evidence == "accepted text not relayed"


def test_caveats_of_another_language_after_a_fallback_name_the_editions(tmp_path: Path) -> None:
    write_summary(tmp_path / "artifacts" / "r1", _summary_in("pl"))
    check = CaveatsRelayed(type="caveats_relayed")
    assert grade(check, _ctx(tmp_path, "W pl.wikipedia dane są niepełne.")).passed
    assert grade(check, _ctx(tmp_path, "Polska edycja (pl): dane są niepełne.")).passed
    outcome = grade(check, _ctx(tmp_path, "Zainteresowanie rośnie."))
    assert not outcome.passed
    assert "missing ['pl.wikipedia']" in outcome.evidence


ACCEPTED = (
    "Частка уваги до астрономії в uk.wikipedia падає: мінус сорок п'ять відсотків за рік, "
    "швидше за трафік розділу. Останні місяці показують можливий поворот. Перевірте попит "
    "через Google Trends. Звіт: report.pdf"
)


def test_chat_answer_relayed_as_it_is_passes_and_a_rewrite_fails(tmp_path: Path) -> None:
    run_dir = tmp_path / "artifacts" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "chat_brief.md").write_text(ACCEPTED, encoding="utf-8")
    check = ChatAnswerRelayed(type="chat_answer_relayed")
    assert grade(check, _ctx(tmp_path, ACCEPTED)).passed
    prefaced = "Here is the report I generated for you, with all the details below.\n\n" + ACCEPTED
    outcome = grade(check, _ctx(tmp_path, prefaced))
    assert not outcome.passed
    assert "comes from there" in outcome.evidence
    assert not grade(check, _ctx(tmp_path, "Астрономія падає. Звіт готовий.")).passed


def test_chat_answer_relayed_passes_without_an_accepted_text(tmp_path: Path) -> None:
    outcome = grade(ChatAnswerRelayed(type="chat_answer_relayed"), _ctx(tmp_path, "anything"))
    assert outcome.passed
    assert outcome.evidence == "no accepted text to relay"
