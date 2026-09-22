"""OpenRouter provider: tool loop over a fake transport, retries, sandbox confinement."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import httpx
import pytest

from skill_evals.providers.base import (
    MalformedOutputError,
    ModelMismatchError,
    RateLimitedError,
    TransportError,
)
from skill_evals.providers.openrouter import OpenRouterProvider, SandboxTools, build_system_prompt
from skill_evals.sandbox import Sandbox

MODEL = "test/model:free"


def _completion(
    content: str | None = None,
    tool_calls: list[dict[str, object]] | None = None,
    *,
    model: str = MODEL,
    cost: float = 0.0,
) -> dict[str, object]:
    message: dict[str, object] = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {
        "id": "x",
        "model": model,
        "choices": [{"message": message, "finish_reason": "tool_calls" if tool_calls else "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": cost},
    }


def _call(name: str, arguments: dict[str, object], call_id: str = "c1") -> dict[str, object]:
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments)},
    }


def _provider(
    responses: list[httpx.Response],
    requests: list[dict[str, object]],
    **kwargs: object,
) -> OpenRouterProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return responses.pop(0)

    return OpenRouterProvider(
        MODEL,
        api_key="k",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
        **kwargs,  # type: ignore[arg-type]
    )


def _messages(request: dict[str, object]) -> list[dict[str, str]]:
    return cast("list[dict[str, str]]", request["messages"])


def test_system_prompt_contains_skill_md_and_path(skill_dir: Path) -> None:
    prompt = build_system_prompt(skill_dir)
    assert "Run `python scripts/run.py request.json`" in prompt
    assert str(skill_dir.resolve()) in prompt


def test_tool_loop_executes_tools_and_records_trajectory(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    requests: list[dict[str, object]] = []
    responses = [
        httpx.Response(200, json=_completion(tool_calls=[_call("list_dir", {"path": "."})])),
        httpx.Response(
            200,
            json=_completion(
                tool_calls=[
                    _call("write_file", {"path": "workspace/out.txt", "content": "hi"}, "c2")
                ]
            ),
        ),
        httpx.Response(200, json=_completion("Final answer 42", cost=0.002)),
    ]
    provider = _provider(responses, requests)
    trajectory = provider.run(["do it"], sandbox.root, tmp_path / "events.jsonl")
    assert trajectory.final_answer == "Final answer 42"
    assert [c.name for c in trajectory.tool_calls] == ["list_dir", "write_file"]
    assert "workspace/" in (trajectory.tool_calls[0].result or "")
    assert (sandbox.root / "workspace" / "out.txt").read_text(encoding="utf-8") == "hi"
    assert trajectory.num_turns == 3
    assert trajectory.usage.input_tokens == 30
    assert trajectory.cost_usd == pytest.approx(0.002)
    assert trajectory.served_models == [MODEL]
    system = _messages(requests[0])[0]
    assert system["role"] == "system"
    assert "SKILL.md" in system["content"]
    tool_msgs = [m for m in _messages(requests[2]) if m["role"] == "tool"]
    assert [m["tool_call_id"] for m in tool_msgs] == ["c1", "c2"]
    assert (tmp_path / "events.jsonl").exists()


def test_multi_turn_keeps_history(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    requests: list[dict[str, object]] = []
    responses = [
        httpx.Response(200, json=_completion("one")),
        httpx.Response(200, json=_completion("two")),
    ]
    trajectory = _provider(responses, requests).run(["a", "b"], sandbox.root, tmp_path / "e.jsonl")
    assert [t.final_answer for t in trajectory.turns] == ["one", "two"]
    roles = [m["role"] for m in _messages(requests[1])]
    assert roles == ["system", "user", "assistant", "user"]


def test_max_turns_marks_truncated(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    call = _completion(tool_calls=[_call("list_dir", {"path": "."})])
    responses = [httpx.Response(200, json=call), httpx.Response(200, json=call)]
    provider = _provider(responses, [], max_turns=2)
    trajectory = provider.run(["loop"], sandbox.root, tmp_path / "e.jsonl")
    assert trajectory.stop_reason == "max_turns"
    assert trajectory.final_answer == ""


def test_retries_on_5xx_then_succeeds(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    requests: list[dict[str, object]] = []
    responses = [httpx.Response(503, text="busy"), httpx.Response(200, json=_completion("ok"))]
    trajectory = _provider(responses, requests).run(["x"], sandbox.root, tmp_path / "e.jsonl")
    assert trajectory.final_answer == "ok"
    assert len(requests) == 2


def test_persistent_429_raises_rate_limited(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    responses = [httpx.Response(429, headers={"retry-after": "7"}, text="slow down")] * 3
    provider = _provider(responses, [], max_retries=2)
    with pytest.raises(RateLimitedError) as info:
        provider.run(["x"], sandbox.root, tmp_path / "e.jsonl")
    assert info.value.retry_after_s == 7.0


def test_4xx_is_transport_error_without_retry(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    requests: list[dict[str, object]] = []
    provider = _provider([httpx.Response(401, text="bad key")], requests)
    with pytest.raises(TransportError, match="401"):
        provider.run(["x"], sandbox.root, tmp_path / "e.jsonl")
    assert len(requests) == 1


def test_model_mismatch(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    provider = _provider([httpx.Response(200, json=_completion("x", model="other/model"))], [])
    with pytest.raises(ModelMismatchError):
        provider.run(["x"], sandbox.root, tmp_path / "e.jsonl")


def test_malformed_body(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    provider = _provider([httpx.Response(200, json={"choices": []})], [])
    with pytest.raises(MalformedOutputError):
        provider.run(["x"], sandbox.root, tmp_path / "e.jsonl")


def test_missing_api_key_fails_fast(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(TransportError, match="OPENROUTER_API_KEY"):
        OpenRouterProvider(MODEL)


def test_sandbox_tools_confine_paths_and_run_commands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SKILL_EVALS_SHELL", raising=False)
    tools = SandboxTools(tmp_path)
    assert tools.call("read_file", {"path": "../outside.txt"}).startswith("error:")
    assert tools.call("nope", {}).startswith("error:")
    (tmp_path / "f.txt").write_text("content", encoding="utf-8")
    assert tools.call("read_file", {"path": "f.txt"}) == "content"
    out = tools.call("bash", {"command": "echo hello"})
    assert out.startswith("[exit 0]")
    assert "hello" in out
