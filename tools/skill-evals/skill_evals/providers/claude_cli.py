"""Adapter that drives headless Claude Code (``claude -p``) as the agent under test.

This is the most honest provider: the skill is discovered by the real Skills mechanism from
``<cwd>/.claude/skills/``, and the agent uses the real Bash/Read tools. The CLI works on the
user's subscription, so the harness has no API key to manage but must respect rate limits.

We use ``--output-format stream-json`` rather than ``json`` because only the stream exposes
tool calls (``Skill``, ``Bash`` commands, tool results); the final ``result`` event carries the
same usage, cost and served-model fields as the ``json`` format. Verified on Claude Code
2.1.278 on 2026-09-22; see README for the recorded probe.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from http import HTTPStatus
from pathlib import Path

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

__all__ = [
    "DEFAULT_ALLOWED_TOOLS",
    "ClaudeCliProvider",
    "ParsedRun",
    "expected_model_prefix",
    "locate_claude_binary",
    "parse_stream",
    "primary_model",
]

BINARY_ENV = "SKILL_EVALS_CLAUDE_BIN"
_VSCODE_BUNDLE_GLOB = "anthropic.claude-code-*-win32-x64/resources/native-binary/claude.exe"
_MODEL_FAMILIES = {"haiku", "sonnet", "opus", "fable"}
_RATE_LIMIT_MARKERS = (
    "rate limit",
    "rate_limit",
    "usage limit",
    "limit reached",
    "out of extra usage",
    "too many requests",
    "overloaded",
)
DEFAULT_ALLOWED_TOOLS: tuple[str, ...] = (
    "Skill",
    "Bash",
    "PowerShell",
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
)
"""Tools pre-approved in the sandbox. With ``--permission-mode dontAsk`` anything else that would
prompt is denied automatically and listed in ``permission_denials``."""


def locate_claude_binary(explicit: Path | None = None) -> Path:
    """Find the Claude Code executable.

    Order: explicit argument, ``SKILL_EVALS_CLAUDE_BIN``, ``claude`` on PATH, then the VS Code
    extension bundle (highest version wins). The bundle fallback exists because on this
    machine the CLI is only shipped inside the extension and is not on PATH.

    Raises:
        FileNotFoundError: When no candidate exists.
    """
    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    env = os.environ.get(BINARY_ENV)
    if env:
        candidates.append(Path(env))
    on_path = shutil.which("claude")
    if on_path:
        candidates.append(Path(on_path))
    candidates.extend(_vscode_bundles())
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    msg = (
        "Claude Code CLI not found. Set SKILL_EVALS_CLAUDE_BIN, put `claude` on PATH, "
        "or install the VS Code extension."
    )
    raise FileNotFoundError(msg)


def _vscode_bundles() -> list[Path]:
    """VS Code extension bundles, newest version first (lexicographic on the version segment)."""
    root = Path.home() / ".vscode" / "extensions"
    if not root.is_dir():
        return []
    found = list(root.glob(_VSCODE_BUNDLE_GLOB))
    return sorted(found, key=_version_key, reverse=True)


def _version_key(path: Path) -> tuple[int, ...]:
    """Numeric version tuple from ``anthropic.claude-code-2.1.278-win32-x64``."""
    segment = path.parents[2].name.removeprefix("anthropic.claude-code-").split("-")[0]
    return tuple(int(p) for p in segment.split(".") if p.isdigit())


def expected_model_prefix(model: str) -> str:
    """Prefix the served model id must start with for the requested ``model``.

    Aliases such as ``haiku`` resolve to the family prefix ``claude-haiku-``; a full id is
    required verbatim. The check guards against silent fallback to another model, which would
    make a benchmark compare apples to oranges.
    """
    lowered = model.lower()
    if lowered in _MODEL_FAMILIES:
        return f"claude-{lowered}-"
    return lowered


@dataclass(slots=True)
class ParsedRun:
    """Everything one ``claude -p`` invocation told us, before it becomes a :class:`TurnRecord`."""

    served_model: str | None = None
    session_id: str | None = None
    skills: list[str] = field(default_factory=list)
    tool_calls: list[ToolCall] = field(default_factory=list)
    assistant_texts: list[str] = field(default_factory=list)
    result_text: str | None = None
    usage: Usage = field(default_factory=Usage)
    cost_usd: float | None = None
    num_turns: int = 0
    duration_s: float = 0.0
    stop_reason: str | None = None
    is_error: bool = False
    subtype: str | None = None
    api_error_status: int | None = None
    permission_denials: list[str] = field(default_factory=list)
    rate_limit_status: str | None = None
    rate_limit_resets_at: float | None = None
    has_result: bool = False

    @property
    def final_answer(self) -> str:
        """The ``result`` text when present, else the last assistant text block."""
        if self.result_text is not None:
            return self.result_text
        return self.assistant_texts[-1] if self.assistant_texts else ""


def parse_stream(lines: Iterable[str]) -> ParsedRun:
    """Parse ``stream-json`` lines into a :class:`ParsedRun`.

    Unknown event types are ignored so a CLI upgrade that adds events does not break parsing;
    a missing ``result`` event is reported through ``has_result`` and handled by the caller.

    Raises:
        MalformedOutputError: If a line is not JSON.
    """
    run = ParsedRun()
    pending: dict[str, int] = {}
    for raw in lines:
        line = raw.strip().lstrip("﻿")
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            msg = f"stream-json line is not JSON: {line[:120]!r}"
            raise MalformedOutputError(msg) from exc
        if isinstance(event, dict):
            _apply_event(run, event, pending)
    return run


def _apply_event(run: ParsedRun, event: dict[str, object], pending: dict[str, int]) -> None:
    """Route one event to the field(s) it updates."""
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
        _apply_init(run, event)
    elif kind == "rate_limit_event":
        _apply_rate_limit(run, event)
    elif kind in {"assistant", "user"}:
        _apply_message(run, event, pending)
    elif kind == "result":
        _apply_result(run, event)


def _apply_init(run: ParsedRun, event: dict[str, object]) -> None:
    run.served_model = _opt_str(event.get("model"))
    run.session_id = _opt_str(event.get("session_id"))
    skills = event.get("skills")
    if isinstance(skills, list):
        run.skills = [str(s) for s in skills]


def _apply_rate_limit(run: ParsedRun, event: dict[str, object]) -> None:
    info = event.get("rate_limit_info")
    if isinstance(info, dict):
        run.rate_limit_status = _opt_str(info.get("status"))
        resets = info.get("resetsAt")
        if isinstance(resets, int | float):
            run.rate_limit_resets_at = float(resets)


def _apply_message(run: ParsedRun, event: dict[str, object], pending: dict[str, int]) -> None:
    message = event.get("message")
    if not isinstance(message, dict):
        return
    model = _opt_str(message.get("model"))
    if model and event.get("type") == "assistant":
        run.served_model = model
    content = message.get("content")
    if isinstance(content, str):
        if event.get("type") == "assistant":
            run.assistant_texts.append(content)
        return
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict):
            _apply_block(run, block, pending)


def _apply_block(run: ParsedRun, block: dict[str, object], pending: dict[str, int]) -> None:
    kind = block.get("type")
    if kind == "text":
        run.assistant_texts.append(str(block.get("text", "")))
    elif kind == "tool_use":
        raw_input = block.get("input")
        tool_input: dict[str, object] = dict(raw_input) if isinstance(raw_input, dict) else {}
        name = str(block.get("name", ""))
        call = ToolCall(name=name, input=tool_input, command=_command_of(name, tool_input))
        pending[str(block.get("id", ""))] = len(run.tool_calls)
        run.tool_calls.append(call)
    elif kind == "tool_result":
        index = pending.get(str(block.get("tool_use_id", "")))
        if index is not None:
            call = run.tool_calls[index]
            run.tool_calls[index] = call.model_copy(
                update={
                    "result": _result_text(block.get("content")),
                    "is_error": bool(block.get("is_error", False)),
                }
            )


def _command_of(name: str, tool_input: dict[str, object]) -> str | None:
    """Shell text for command tools; ``Skill`` and file tools expose their key argument."""
    if name in {"Bash", "PowerShell"}:
        return _opt_str(tool_input.get("command"))
    if name == "Skill":
        return _opt_str(tool_input.get("skill"))
    if name in {"Read", "Write", "Edit"}:
        return _opt_str(tool_input.get("file_path"))
    return None


def _result_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [str(b.get("text", "")) for b in content if isinstance(b, dict) and "text" in b]
        return "\n".join(parts)
    return "" if content is None else json.dumps(content)


def _apply_result(run: ParsedRun, event: dict[str, object]) -> None:
    run.has_result = True
    run.result_text = _opt_str(event.get("result"))
    run.session_id = _opt_str(event.get("session_id")) or run.session_id
    run.cost_usd = _opt_float(event.get("total_cost_usd"))
    run.num_turns = int(_opt_float(event.get("num_turns")) or 0)
    run.duration_s = (_opt_float(event.get("duration_ms")) or 0.0) / 1000.0
    run.stop_reason = _opt_str(event.get("stop_reason"))
    run.is_error = bool(event.get("is_error", False))
    run.subtype = _opt_str(event.get("subtype"))
    status = event.get("api_error_status")
    run.api_error_status = int(status) if isinstance(status, int) else None
    denials = event.get("permission_denials")
    if isinstance(denials, list):
        run.permission_denials = [json.dumps(d, sort_keys=True) for d in denials]
    usage = event.get("usage")
    if isinstance(usage, dict):
        run.usage = Usage(
            input_tokens=int(_opt_float(usage.get("input_tokens")) or 0),
            output_tokens=int(_opt_float(usage.get("output_tokens")) or 0),
            cache_read_tokens=int(_opt_float(usage.get("cache_read_input_tokens")) or 0),
            cache_creation_tokens=int(_opt_float(usage.get("cache_creation_input_tokens")) or 0),
        )
    model_usage = event.get("modelUsage")
    if isinstance(model_usage, dict) and model_usage:
        # The result is authoritative about which model actually served the turn.
        run.served_model = primary_model(model_usage)


def primary_model(model_usage: Mapping[str, object]) -> str:
    """The model that did the work: the ``modelUsage`` entry with the highest cost.

    Claude Code makes small side calls (observed: a Haiku call of ~12 output tokens next to
    the real Sonnet judge call), so the first key is not the served model. Cost is the most
    robust signal; output tokens break ties when cost is missing.
    """

    def weight(item: tuple[str, object]) -> tuple[float, float]:
        stats = item[1] if isinstance(item[1], dict) else {}
        return (
            _opt_float(stats.get("costUSD")) or 0.0,
            _opt_float(stats.get("outputTokens")) or 0.0,
        )

    return str(max(model_usage.items(), key=weight)[0])


def _opt_str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _opt_float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


class ClaudeCliProvider:
    """Runs scenarios through ``claude -p`` in a sandbox and parses the stream into a trajectory.

    Args:
        binary: Explicit CLI path; otherwise :func:`locate_claude_binary` decides.
        model: Model alias or id passed to ``--model``.
        allowed_tools: Tools pre-approved via ``--allowedTools``.
        max_turns: ``--max-turns`` budget per user message; hitting it yields
            ``stop_reason="max_turns"`` and the case is graded as truncated, not errored.
        timeout_s: Wall-clock budget per user message; exceeding it kills the process tree
            and raises :class:`ProviderTimeoutError`.
        setting_sources: Value for ``--setting-sources``; ``project`` keeps the user's own
            skills and settings out of the sandbox so only the skill under test is visible.
        extra_args: Additional CLI flags appended verbatim.
        persist_sessions: Sessions must persist for ``--resume`` to work; single-turn
            scenarios may disable it to avoid littering ``~/.claude/projects``.
    """

    name = "claude-cli"

    def __init__(  # noqa: PLR0913 - configuration knobs, all keyword-only
        self,
        binary: Path | None = None,
        *,
        model: str = "haiku",
        allowed_tools: Sequence[str] = DEFAULT_ALLOWED_TOOLS,
        max_turns: int = 30,
        timeout_s: int = 900,
        setting_sources: str | None = "project",
        extra_args: Sequence[str] = (),
        persist_sessions: bool = True,
    ) -> None:
        self._binary = binary
        self._model = model
        self._allowed_tools = list(allowed_tools)
        self._max_turns = max_turns
        self._timeout_s = timeout_s
        self._setting_sources = setting_sources
        self._extra_args = list(extra_args)
        self._persist_sessions = persist_sessions

    @property
    def model(self) -> str:
        """The requested model alias or id."""
        return self._model

    @property
    def binary(self) -> Path:
        """Resolved CLI path (resolution is lazy so unit tests never need the binary)."""
        return locate_claude_binary(self._binary)

    def build_command(self, *, session_id: str, resume: bool) -> list[str]:
        """Assemble the ``claude -p`` argv; the prompt itself is sent on stdin.

        Stdin avoids the Windows command-line length limit and quoting of Cyrillic prompts.
        The session id is chosen by the harness so follow-up turns can ``--resume`` it and so
        the trajectory records a stable identifier.
        """
        cmd = [
            str(self.binary),
            "-p",
            "--model",
            self._model,
            "--output-format",
            "stream-json",
            "--verbose",
            "--max-turns",
            str(self._max_turns),
            "--permission-mode",
            "dontAsk",
        ]
        if self._allowed_tools:
            cmd += ["--allowedTools", ",".join(self._allowed_tools)]
        if self._setting_sources is not None:
            cmd += ["--setting-sources", self._setting_sources]
        cmd += ["--resume", session_id] if resume else ["--session-id", session_id]
        if not self._persist_sessions and not resume:
            cmd.append("--no-session-persistence")
        cmd += self._extra_args
        return cmd

    def run(self, turns: Sequence[str], workdir: Path, events_path: Path) -> Trajectory:
        """Send each turn as a separate ``claude -p`` call, resuming the same session."""
        session_id = str(uuid.uuid4())
        records: list[TurnRecord] = []
        for index, prompt in enumerate(turns):
            cmd = self.build_command(session_id=session_id, resume=index > 0)
            parsed = self._invoke(cmd, prompt, workdir, events_path, index)
            records.append(self._to_turn(parsed, prompt, session_id))
        return Trajectory(
            provider=self.name,
            requested_model=self._model,
            turns=records,
            raw_events_path=str(events_path),
        )

    def _invoke(
        self, cmd: list[str], prompt: str, workdir: Path, events_path: Path, index: int
    ) -> ParsedRun:
        """Run one CLI process, persist its raw output, and validate the outcome."""
        _append_event(events_path, {"type": "harness_turn", "index": index, "prompt": prompt})
        started = time.monotonic()
        stdout, stderr = self._communicate(cmd, prompt, workdir)
        elapsed = time.monotonic() - started
        lines = stdout.splitlines()
        with events_path.open("a", encoding="utf-8", newline="\n") as handle:
            for line in lines:
                if line.strip():
                    handle.write(line.lstrip("﻿").rstrip("\r\n") + "\n")
        parsed = parse_stream(lines)
        if parsed.duration_s == 0.0:
            parsed.duration_s = elapsed
        self._check_outcome(parsed, stderr)
        return parsed

    def _communicate(self, cmd: list[str], prompt: str, workdir: Path) -> tuple[str, str]:
        """Run the process with a hard timeout; on expiry kill the whole tree."""
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            msg = f"cannot start Claude CLI: {exc}"
            raise TransportError(msg) from exc
        try:
            out, err = proc.communicate(prompt.encode("utf-8"), timeout=self._timeout_s)
        except subprocess.TimeoutExpired as exc:
            _kill_tree(proc)
            msg = f"claude -p exceeded {self._timeout_s}s"
            raise ProviderTimeoutError(msg) from exc
        return out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")

    def _check_outcome(self, parsed: ParsedRun, stderr: str) -> None:
        """Turn CLI-level failures into typed errors; leave agent behaviour to the graders."""
        text = f"{parsed.final_answer}\n{stderr}".lower()
        limited = parsed.rate_limit_status not in {None, "allowed"}
        if parsed.api_error_status == HTTPStatus.TOO_MANY_REQUESTS or (
            parsed.is_error and _mentions_rate_limit(text)
        ):
            limited = True
        if (limited and not parsed.has_result) or (limited and parsed.is_error):
            retry = None
            if parsed.rate_limit_resets_at is not None:
                retry = max(0.0, parsed.rate_limit_resets_at - time.time())
            raise RateLimitedError(parsed.final_answer[:500] or stderr[-500:], retry_after_s=retry)
        if not parsed.has_result:
            msg = f"claude -p produced no result event; stderr tail: {stderr[-800:]!r}"
            raise TransportError(msg)
        if parsed.is_error and parsed.subtype not in {"error_max_turns", "success"}:
            msg = f"claude -p reported an error ({parsed.subtype}): {parsed.final_answer[:500]}"
            raise TransportError(msg)
        prefix = expected_model_prefix(self._model)
        if parsed.served_model is None or not parsed.served_model.lower().startswith(prefix):
            msg = f"requested {self._model!r} but served {parsed.served_model!r}"
            raise ModelMismatchError(msg)

    @staticmethod
    def _to_turn(parsed: ParsedRun, prompt: str, session_id: str) -> TurnRecord:
        stop = parsed.stop_reason
        if parsed.subtype == "error_max_turns":
            stop = "max_turns"
        return TurnRecord(
            prompt=prompt,
            final_answer=parsed.final_answer,
            tool_calls=parsed.tool_calls,
            served_model=parsed.served_model,
            usage=parsed.usage,
            cost_usd=parsed.cost_usd,
            num_turns=parsed.num_turns,
            duration_s=parsed.duration_s,
            stop_reason=stop,
            session_id=parsed.session_id or session_id,
            is_error=parsed.is_error,
            permission_denials=parsed.permission_denials,
        )


def _mentions_rate_limit(text: str) -> bool:
    return any(marker in text for marker in _RATE_LIMIT_MARKERS)


def _append_event(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _kill_tree(proc: subprocess.Popen[bytes]) -> None:
    """Kill the CLI and its children; ``proc.kill`` alone leaves grandchildren on Windows."""
    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
            check=False,
        )
    proc.kill()
    proc.communicate()
