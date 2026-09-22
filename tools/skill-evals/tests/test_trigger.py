"""Trigger check: invocation detection and precision/recall over a fake provider."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.console import Console

from skill_evals.providers.base import ProviderTimeoutError, ToolCall
from skill_evals.trigger import (
    TriggerConfig,
    detect_skill_invocation,
    load_trigger_cases,
    run_trigger,
)
from tests.conftest import FakeProvider, make_trajectory


def _skill_call(name: str) -> ToolCall:
    return ToolCall(name="Skill", input={"skill": name}, command=name)


def test_detects_skill_tool_call_exact_and_namespaced() -> None:
    assert detect_skill_invocation(
        make_trajectory("", tool_calls=[_skill_call("wiki-interest")]), "wiki-interest"
    ).invoked
    assert detect_skill_invocation(
        make_trajectory("", tool_calls=[_skill_call("plugin:wiki-interest")]), "wiki-interest"
    ).invoked
    assert not detect_skill_invocation(
        make_trajectory("", tool_calls=[_skill_call("wiki-interest-2")]), "wiki-interest"
    ).invoked
    assert not detect_skill_invocation(
        make_trajectory("", tool_calls=[_skill_call("pdf")]), "wiki-interest"
    ).invoked


def test_detects_reading_skill_md_and_directory_access() -> None:
    read = ToolCall(
        name="Read",
        input={"file_path": r"C:\sb\.claude\skills\wiki-interest\SKILL.md"},
        command=r"C:\sb\.claude\skills\wiki-interest\SKILL.md",
    )
    evidence = detect_skill_invocation(make_trajectory("", tool_calls=[read]), "wiki-interest")
    assert evidence.invoked
    assert evidence.how == "Read SKILL.md"
    bash = ToolCall(
        name="Bash",
        input={"command": "python .claude/skills/wiki-interest/scripts/run.py"},
        command="python .claude/skills/wiki-interest/scripts/run.py",
    )
    assert detect_skill_invocation(make_trajectory("", tool_calls=[bash]), "wiki-interest").invoked
    other = ToolCall(
        name="Read",
        input={"file_path": "/x/skills/other/SKILL.md"},
        command="/x/skills/other/SKILL.md",
    )
    assert not detect_skill_invocation(
        make_trajectory("", tool_calls=[other]), "wiki-interest"
    ).invoked


def test_prose_mention_does_not_count() -> None:
    assert not detect_skill_invocation(
        make_trajectory("I would use wiki-interest"), "wiki-interest"
    ).invoked


def test_load_trigger_cases_rejects_non_list(tmp_path: Path) -> None:
    path = tmp_path / "t.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="list"):
        load_trigger_cases(path)


def test_run_trigger_precision_recall_and_confusions(tmp_path: Path, skill_dir: Path) -> None:
    cases = tmp_path / "trigger.json"
    cases.write_text(
        json.dumps(
            [
                {"query": "positive hit", "should_trigger": True},
                {"query": "positive miss", "should_trigger": True},
                {"query": "negative clean", "should_trigger": False},
                {"query": "negative fp", "should_trigger": False},
                {"query": "broken", "should_trigger": True},
            ]
        ),
        encoding="utf-8",
    )
    invoked = make_trajectory("", tool_calls=[_skill_call("demo-skill")])
    provider = FakeProvider(
        {
            "positive hit": invoked,
            "negative fp": invoked,
            "broken": ProviderTimeoutError("slow"),
        },
        default=make_trajectory("plain answer"),
    )
    config = TriggerConfig(
        cases_path=cases,
        skill_path=skill_dir,
        provider=provider,
        run_dir=tmp_path / "trig",
        reps=2,
        parallelism=1,
        log=Console(quiet=True),
    )
    report = run_trigger(config)
    assert (report.true_positive, report.false_negative) == (2, 2)
    assert (report.true_negative, report.false_positive) == (2, 2)
    assert (report.precision, report.recall) == (0.5, 0.5)
    assert report.errors_by_class == {"timeout": 2}
    assert sorted({o.query for o in report.confusions}) == ["negative fp", "positive miss"]
    assert (config.run_dir / "trigger.md").read_text(encoding="utf-8").count("| negative fp |") == 2
    assert (config.run_dir / "trigger.json").exists()
    resumed = run_trigger(config)
    assert len(provider.calls) == 10 + 2  # only the two errored cases run again
    assert resumed.true_positive == 2
