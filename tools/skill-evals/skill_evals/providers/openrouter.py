"""Adapter that runs an OpenAI-compatible tool-using model (OpenRouter) as the agent.

Models outside Claude Code have no Skills mechanism, so activation is mimicked: the system
prompt carries ``SKILL.md`` verbatim plus the absolute skill path, and the model gets a
minimal tool set (``bash``, ``read_file``, ``list_dir``, ``write_file``) executed inside the
sandbox. The point is portability evidence ("does a similar model with tools cope?") and cheap
mass debugging, not parity with the Claude CLI provider.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from http import HTTPStatus
from pathlib import Path

import httpx

from skill_evals.providers.base import (
    MalformedOutputError,
    ModelMismatchError,
    ProviderTimeoutError,
    RateLimitedError,
    ToolCall,
    Trajectory,
    TransportError,
    TurnRecord,
    Usage,
)

__all__ = ["OpenRouterProvider", "SandboxTools", "build_system_prompt"]

API_KEY_ENV = "OPENROUTER_API_KEY"
SHELL_ENV = "SKILL_EVALS_SHELL"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_MAX_TOOL_OUTPUT = 8000
_RETRY_STATUSES = {429, 500, 502, 503, 504}

_PREAMBLE = (
    "You are a capable software agent working in a sandbox directory. You can run shell "
    "commands and read or write files with the provided tools. Follow the skill instructions "
    "below to answer the user's request; the skill's scripts do the analysis, you relay the "
    "results. When the task is done, reply with your final answer as plain text."
)

TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the sandbox and return stdout+stderr.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a UTF-8 text file (path relative to the sandbox).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List a directory (path relative to the sandbox).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write a UTF-8 text file (path relative to the sandbox).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
]


def build_system_prompt(skill_dir: Path) -> str:
    """Compose the system prompt that stands in for Skills activation."""
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8-sig")
    return (
        f"{_PREAMBLE}\n\n"
        f"The skill files are at: {skill_dir.resolve()}\n"
        f"Your current working directory is the sandbox root; the skill directory is inside it.\n\n"
        f"--- SKILL.md ---\n{skill_md}\n--- end of SKILL.md ---"
    )


class SandboxTools:
    """Executes the model's tool calls inside ``root`` and never outside it.

    Paths are confined to the sandbox because the model is untrusted input; shell commands
    are not confined (they are the same power a Claude Code agent has) but run with the
    sandbox as cwd and a timeout.
    """

    def __init__(self, root: Path, *, command_timeout_s: int = 600) -> None:
        self._root = root.resolve()
        self._timeout = command_timeout_s

    def call(self, name: str, arguments: dict[str, object]) -> str:
        """Dispatch one tool call; errors are returned as text so the model can recover."""
        try:
            if name == "bash":
                return self._bash(str(arguments.get("command", "")))
            if name == "read_file":
                return self._resolve(str(arguments.get("path", ""))).read_text(encoding="utf-8")
            if name == "list_dir":
                target = self._resolve(str(arguments.get("path", ".")))
                return "\n".join(
                    sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
                )
            if name == "write_file":
                target = self._resolve(str(arguments.get("path", "")))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(str(arguments.get("content", "")), encoding="utf-8")
                return f"wrote {target}"
        except (OSError, ValueError) as exc:
            return f"error: {exc}"
        return f"error: unknown tool {name!r}"

    def _resolve(self, relative: str) -> Path:
        target = (self._root / relative).resolve()
        if not target.is_relative_to(self._root):
            msg = f"path escapes the sandbox: {relative}"
            raise ValueError(msg)
        return target

    def _bash(self, command: str) -> str:
        argv, use_shell = _shell_argv(command)
        try:
            completed = subprocess.run(
                argv,
                cwd=self._root,
                shell=use_shell,
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return f"error: command timed out after {self._timeout}s"
        out = completed.stdout.decode("utf-8", errors="replace")
        err = completed.stderr.decode("utf-8", errors="replace")
        text = f"{out}\n[stderr]\n{err}" if err.strip() else out
        return _truncate(f"[exit {completed.returncode}]\n{text}")


def _shell_argv(command: str) -> tuple[list[str] | str, bool]:
    """Pick the shell for the ``bash`` tool.

    ``SKILL_EVALS_SHELL`` names an explicit shell (for example Git Bash on Windows). Otherwise
    ``bash`` from PATH is used on POSIX only: on Windows the ``bash.exe`` on PATH is often the
    WSL launcher, which is not a working shell for the sandbox, so the platform shell is used.
    """
    explicit = os.environ.get(SHELL_ENV)
    if explicit:
        return [explicit, "-c", command], False
    if sys.platform != "win32":
        bash = shutil.which("bash")
        if bash:
            return [bash, "-c", command], False
    return command, True


def _truncate(text: str, limit: int = _MAX_TOOL_OUTPUT) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n...[{len(text) - limit} chars truncated]...\n{text[-half:]}"


@dataclass(frozen=True, slots=True)
class _Reply:
    message: dict[str, object]
    tool_calls: list[dict[str, object]]
    usage: Usage
    cost_usd: float | None
    model: str | None
    finish_reason: str | None


class OpenRouterProvider:
    """Minimal tool-use loop over the OpenAI-compatible chat completions API.

    Args:
        model: OpenRouter model slug (for example ``qwen/qwen3-coder:free``).
        api_key: Defaults to ``OPENROUTER_API_KEY``.
        base_url: API root.
        max_turns: Maximum model calls per user message.
        timeout_s: Wall-clock budget per user message.
        transport: Injected ``httpx`` transport for tests (no network).
        sleep: Injected sleep for backoff (tests pass a no-op).
        expected_model_prefix: Served model must start with this; defaults to ``model``.
    """

    name = "openrouter"

    def __init__(  # noqa: PLR0913 - configuration knobs, all keyword-only
        self,
        model: str,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        max_turns: int = 30,
        timeout_s: int = 900,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        expected_model_prefix: str | None = None,
        max_retries: int = 4,
    ) -> None:
        key = api_key if api_key is not None else os.environ.get(API_KEY_ENV)
        if not key:
            msg = f"OpenRouter API key missing; set {API_KEY_ENV}"
            raise TransportError(msg)
        self._model = model
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {key}"},
            timeout=httpx.Timeout(120.0),
            transport=transport,
        )
        self._max_turns = max_turns
        self._timeout_s = timeout_s
        self._sleep = sleep
        self._expected_prefix = (expected_model_prefix or model).lower()
        self._max_retries = max_retries

    @property
    def model(self) -> str:
        """The requested model slug."""
        return self._model

    def run(self, turns: Sequence[str], workdir: Path, events_path: Path) -> Trajectory:
        """Run the conversation, keeping the message history across user turns."""
        skill_dir = _find_skill_dir(workdir)
        messages: list[dict[str, object]] = [
            {"role": "system", "content": build_system_prompt(skill_dir)}
        ]
        tools = SandboxTools(workdir)
        records = [self._run_turn(prompt, messages, tools, events_path) for prompt in turns]
        return Trajectory(
            provider=self.name,
            requested_model=self._model,
            turns=records,
            raw_events_path=str(events_path),
        )

    def _run_turn(
        self,
        prompt: str,
        messages: list[dict[str, object]],
        tools: SandboxTools,
        events_path: Path,
    ) -> TurnRecord:
        messages.append({"role": "user", "content": prompt})
        _append_event(events_path, {"type": "harness_turn", "prompt": prompt})
        started = time.monotonic()
        usage = Usage()
        cost: float | None = None
        calls: list[ToolCall] = []
        served: str | None = None
        stop: str | None = "max_turns"
        for _ in range(self._max_turns):
            self._check_deadline(started)
            reply = self._complete(messages, events_path)
            usage = usage + reply.usage
            cost = _add_cost(cost, reply.cost_usd)
            served = reply.model or served
            self._assert_model(served)
            messages.append(reply.message)
            if not reply.tool_calls:
                stop = reply.finish_reason or "stop"
                break
            for raw_call in reply.tool_calls:
                call, tool_message = self._execute(raw_call, tools)
                calls.append(call)
                messages.append(tool_message)
                _append_event(events_path, {"type": "tool_result", "message": tool_message})
        final = _content_text(messages[-1]) if messages[-1].get("role") == "assistant" else ""
        return TurnRecord(
            prompt=prompt,
            final_answer=final,
            tool_calls=calls,
            served_model=served,
            usage=usage,
            cost_usd=cost,
            num_turns=len([m for m in messages if m.get("role") == "assistant"]),
            duration_s=time.monotonic() - started,
            stop_reason=stop,
            session_id=None,
        )

    def _check_deadline(self, started: float) -> None:
        if time.monotonic() - started > self._timeout_s:
            msg = f"OpenRouter turn exceeded {self._timeout_s}s"
            raise ProviderTimeoutError(msg)

    def _assert_model(self, served: str | None) -> None:
        if served is not None and not served.lower().startswith(self._expected_prefix):
            msg = f"requested {self._model!r} but served {served!r}"
            raise ModelMismatchError(msg)

    def _execute(
        self, raw_call: dict[str, object], tools: SandboxTools
    ) -> tuple[ToolCall, dict[str, object]]:
        function = raw_call.get("function")
        fn: dict[str, object] = dict(function) if isinstance(function, dict) else {}
        name = str(fn.get("name", ""))
        arguments = _parse_arguments(fn.get("arguments"))
        result = tools.call(name, arguments)
        command = str(arguments.get("command")) if name == "bash" else None
        call = ToolCall(
            name=name,
            input=arguments,
            command=command,
            result=result,
            is_error=result.startswith("error:"),
        )
        tool_message: dict[str, object] = {
            "role": "tool",
            "tool_call_id": str(raw_call.get("id", "")),
            "content": result,
        }
        return call, tool_message

    def _complete(self, messages: list[dict[str, object]], events_path: Path) -> _Reply:
        """POST one chat completion with retries on 429/5xx and transport errors."""
        payload = {
            "model": self._model,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "usage": {"include": True},
        }
        delay = 2.0
        last_error = "no attempts made"
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.post("/chat/completions", json=payload)
            except httpx.HTTPError as exc:
                last_error = f"transport: {exc}"
            else:
                if response.status_code == HTTPStatus.OK:
                    return _parse_reply(response, events_path)
                last_error = f"HTTP {response.status_code}: {response.text[:300]}"
                if response.status_code not in _RETRY_STATUSES:
                    raise TransportError(last_error)
                if (
                    response.status_code == HTTPStatus.TOO_MANY_REQUESTS
                    and attempt == self._max_retries
                ):
                    raise RateLimitedError(last_error, retry_after_s=_retry_after(response))
            if attempt < self._max_retries:
                self._sleep(delay)
                delay *= 2
        raise TransportError(last_error)


def _parse_reply(response: httpx.Response, events_path: Path) -> _Reply:
    try:
        body = response.json()
    except ValueError as exc:
        msg = "OpenRouter response is not JSON"
        raise MalformedOutputError(msg) from exc
    _append_event(events_path, {"type": "completion", "body": body})
    choices = body.get("choices") if isinstance(body, dict) else None
    if not isinstance(choices, list) or not choices:
        msg = f"OpenRouter response has no choices: {json.dumps(body)[:300]}"
        raise MalformedOutputError(msg)
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict):
        msg = "OpenRouter choice has no message"
        raise MalformedOutputError(msg)
    raw_calls = message.get("tool_calls")
    tool_calls = (
        [dict(c) for c in raw_calls if isinstance(c, dict)] if isinstance(raw_calls, list) else []
    )
    usage_raw = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    usage = Usage(
        input_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
        output_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
    )
    cost_raw = usage_raw.get("cost")
    cost = float(cost_raw) if isinstance(cost_raw, int | float) else None
    model = body.get("model")
    finish = choice.get("finish_reason") if isinstance(choice, dict) else None
    return _Reply(
        message=dict(message),
        tool_calls=tool_calls,
        usage=usage,
        cost_usd=cost,
        model=str(model) if isinstance(model, str) else None,
        finish_reason=str(finish) if isinstance(finish, str) else None,
    )


def _parse_arguments(raw: object) -> dict[str, object]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw}
        return dict(parsed) if isinstance(parsed, dict) else {"_raw": raw}
    return {}


def _content_text(message: dict[str, object]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            str(b.get("text", "")) for b in content if isinstance(b, dict) and "text" in b
        )
    return ""


def _add_cost(total: float | None, part: float | None) -> float | None:
    if part is None:
        return total
    return part if total is None else total + part


def _retry_after(response: httpx.Response) -> float | None:
    header = response.headers.get("retry-after")
    try:
        return float(header) if header else None
    except ValueError:
        return None


def _find_skill_dir(workdir: Path) -> Path:
    """The single skill under ``.claude/skills``; the sandbox guarantees exactly one."""
    skills = workdir / ".claude" / "skills"
    candidates = (
        [p for p in skills.iterdir() if (p / "SKILL.md").is_file()] if skills.is_dir() else []
    )
    if len(candidates) != 1:
        msg = f"expected exactly one skill in {skills}, found {len(candidates)}"
        raise TransportError(msg)
    return candidates[0]


def _append_event(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
