"""Claude CLI provider: command construction, stream parsing on a recorded run, error mapping."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_evals.providers.base import (
    MalformedOutputError,
    ModelMismatchError,
    RateLimitedError,
    TransportError,
)
from skill_evals.providers.claude_cli import (
    BINARY_ENV,
    ClaudeCliProvider,
    agent_environment,
    expected_model_prefix,
    locate_claude_binary,
    parse_stream,
    primary_model,
)
from tests.conftest import FIXTURES

STREAM = (FIXTURES / "claude_stream_pineapple.jsonl").read_text(encoding="utf-8").splitlines()


def test_parse_recorded_stream_extracts_skill_invocation_and_result() -> None:
    parsed = parse_stream(STREAM)
    assert parsed.has_result
    assert parsed.served_model == "claude-haiku-4-5-20251001"
    assert parsed.session_id == "9c8ab926-ae0a-46c3-aef3-beb3a414cb00"
    assert "pineapple" in parsed.skills
    assert parsed.final_answer.startswith("PINEAPPLE")
    assert parsed.num_turns == 3
    assert parsed.cost_usd == pytest.approx(0.0309281)
    assert parsed.stop_reason == "end_turn"
    assert parsed.usage.output_tokens == 329
    assert parsed.usage.cache_read_tokens == 62691
    assert parsed.rate_limit_status == "allowed"
    assert parsed.permission_denials == []


def test_parse_recorded_stream_pairs_tool_use_with_result() -> None:
    parsed = parse_stream(STREAM)
    assert len(parsed.tool_calls) == 1
    call = parsed.tool_calls[0]
    assert call.name == "Skill"
    assert call.input == {"skill": "pineapple"}
    assert call.command == "pineapple"
    assert call.result == "Launching skill: pineapple"
    assert call.signature() == "Skill pineapple"


def test_parse_tolerates_bom_and_unknown_events() -> None:
    lines = ["﻿" + STREAM[0], json.dumps({"type": "something_new"}), *STREAM[1:]]
    assert parse_stream(lines).has_result


def test_parse_rejects_non_json() -> None:
    with pytest.raises(MalformedOutputError):
        parse_stream(["{not json"])


def test_bash_tool_call_exposes_command() -> None:
    event = {
        "type": "assistant",
        "message": {
            "model": "claude-haiku-4-5-20251001",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "Bash",
                    "input": {"command": "python scripts/run.py r.json"},
                }
            ],
        },
    }
    result = {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "t1",
                    "content": [{"type": "text", "text": "ok"}],
                    "is_error": False,
                }
            ]
        },
    }
    parsed = parse_stream([json.dumps(event), json.dumps(result)])
    assert parsed.tool_calls[0].command == "python scripts/run.py r.json"
    assert parsed.tool_calls[0].result == "ok"


@pytest.mark.parametrize(
    ("model", "prefix"),
    [
        ("haiku", "claude-haiku-"),
        ("Sonnet", "claude-sonnet-"),
        ("claude-haiku-4-5-20251001", "claude-haiku-4-5-20251001"),
    ],
)
def test_expected_model_prefix(model: str, prefix: str) -> None:
    assert expected_model_prefix(model) == prefix


def test_build_command_first_turn_and_resume(tmp_path: Path) -> None:
    binary = tmp_path / "claude.exe"
    binary.write_bytes(b"")
    provider = ClaudeCliProvider(
        binary, model="haiku", allowed_tools=["Skill", "Bash"], max_turns=12
    )
    first = provider.build_command(session_id="abc", resume=False)
    assert first[:2] == [str(binary), "-p"]
    assert first[first.index("--model") + 1] == "haiku"
    assert first[first.index("--output-format") + 1] == "stream-json"
    assert "--verbose" in first
    assert first[first.index("--max-turns") + 1] == "12"
    assert first[first.index("--permission-mode") + 1] == "dontAsk"
    assert first[first.index("--allowedTools") + 1] == "Skill,Bash"
    assert first[first.index("--setting-sources") + 1] == "project"
    assert first[first.index("--session-id") + 1] == "abc"
    assert "--resume" not in first
    follow = provider.build_command(session_id="abc", resume=True)
    assert follow[follow.index("--resume") + 1] == "abc"
    assert "--session-id" not in follow


def test_locate_binary_prefers_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = tmp_path / "claude.exe"
    fake.write_bytes(b"")
    monkeypatch.setenv(BINARY_ENV, str(fake))
    assert locate_claude_binary() == fake


def test_locate_binary_reports_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(BINARY_ENV, raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    with pytest.raises(FileNotFoundError, match="SKILL_EVALS_CLAUDE_BIN"):
        locate_claude_binary()


def _provider(tmp_path: Path, model: str = "haiku") -> ClaudeCliProvider:
    binary = tmp_path / "claude.exe"
    binary.write_bytes(b"")
    return ClaudeCliProvider(binary, model=model)


def _result_event(**overrides: object) -> str:
    base: dict[str, object] = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "result": "done",
        "session_id": "s",
        "num_turns": 1,
        "total_cost_usd": 0.001,
        "duration_ms": 10,
        "stop_reason": "end_turn",
        "modelUsage": {"claude-haiku-4-5-20251001": {}},
    }
    base.update(overrides)
    return json.dumps(base)


def test_model_mismatch_raises(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    parsed = parse_stream([_result_event(modelUsage={"claude-sonnet-4-5": {}})])
    with pytest.raises(ModelMismatchError):
        provider._check_outcome(parsed, "")


def test_rate_limit_in_error_result_raises(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    parsed = parse_stream(
        [_result_event(is_error=True, subtype="error", result="You have hit your usage limit")]
    )
    with pytest.raises(RateLimitedError):
        provider._check_outcome(parsed, "")


def test_rate_limit_event_without_result_raises_with_retry(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    event = json.dumps(
        {
            "type": "rate_limit_event",
            "rate_limit_info": {"status": "rejected", "resetsAt": 4102444800},
        }
    )
    parsed = parse_stream([event])
    with pytest.raises(RateLimitedError) as info:
        provider._check_outcome(parsed, "")
    assert info.value.retry_after_s is not None
    assert info.value.retry_after_s > 0


def test_missing_result_is_transport_error(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    with pytest.raises(TransportError, match="no result event"):
        provider._check_outcome(parse_stream([]), "boom")


def test_max_turns_result_is_not_an_error(tmp_path: Path) -> None:
    provider = _provider(tmp_path)
    parsed = parse_stream([_result_event(is_error=True, subtype="error_max_turns")])
    provider._check_outcome(parsed, "")
    turn = provider._to_turn(parsed, "p", "s")
    assert turn.stop_reason == "max_turns"


def test_run_end_to_end_with_stubbed_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provider = _provider(tmp_path)
    seen: list[tuple[list[str], str]] = []

    def fake_communicate(cmd: list[str], prompt: str, workdir: Path) -> tuple[str, str]:
        seen.append((cmd, prompt))
        return "\n".join(STREAM), ""

    monkeypatch.setattr(provider, "_communicate", fake_communicate)
    trajectory = provider.run(["first", "second"], tmp_path, tmp_path / "events.jsonl")
    assert len(trajectory.turns) == 2
    assert seen[0][1] == "first"
    assert "--session-id" in seen[0][0]
    assert "--resume" in seen[1][0]
    assert trajectory.served_models == ["claude-haiku-4-5-20251001"]
    assert trajectory.num_turns == 6
    events = (tmp_path / "events.jsonl").read_text(encoding="utf-8").splitlines()
    assert events[0].startswith('{"type": "harness_turn"')
    assert sum(1 for e in events if '"harness_turn"' in e) == 2


def test_primary_model_ignores_cheap_side_calls() -> None:
    usage = {
        "claude-haiku-4-5-20251001": {"costUSD": 0.001139, "outputTokens": 12},
        "claude-sonnet-5": {"costUSD": 0.0112688, "outputTokens": 108},
    }
    assert primary_model(usage) == "claude-sonnet-5"
    assert primary_model({"a": {"outputTokens": 5}, "b": {"outputTokens": 50}}) == "b"


def test_result_served_model_uses_primary_entry() -> None:
    usage = {"claude-haiku-4-5-20251001": {"costUSD": 0.001}, "claude-sonnet-5": {"costUSD": 0.01}}
    parsed = parse_stream([_result_event(modelUsage=usage)])
    assert parsed.served_model == "claude-sonnet-5"


def test_agent_environment_drops_the_harness_python_environment() -> None:
    env = agent_environment(
        {"PATH": "/bin", "VIRTUAL_ENV": "/h/.venv", "PYTHONPATH": "x", "HOME": "/home/u"}
    )
    assert env == {"PATH": "/bin", "HOME": "/home/u"}
