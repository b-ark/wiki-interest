"""Port ``ModelProvider`` and the ``Trajectory`` every adapter must produce.

Graders and reports only ever see a :class:`Trajectory`, so a scenario graded against headless
Claude Code and the same scenario graded against an OpenRouter model are compared on identical
evidence. Provider failures are typed: the runner maps them to failure classes in
``errors.jsonl`` instead of scoring them, which is the first rule of eval hygiene.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "MalformedOutputError",
    "ModelMismatchError",
    "ModelProvider",
    "ProviderError",
    "ProviderTimeoutError",
    "RateLimitedError",
    "ToolCall",
    "Trajectory",
    "TransportError",
    "TurnRecord",
    "Usage",
]


class ProviderError(Exception):
    """Base class for infrastructure failures.

    ``failure_class`` names the bucket the record lands in within ``errors.jsonl``.
    """

    failure_class = "provider_error"


class ProviderTimeoutError(ProviderError):
    """The agent process exceeded the wall-clock budget and was killed."""

    failure_class = "timeout"


class RateLimitedError(ProviderError):
    """The service refused the request because of quota; the runner pauses and retries."""

    failure_class = "rate_limited"

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s


class TransportError(ProviderError):
    """Process or network failure unrelated to the agent's behaviour."""

    failure_class = "transport"


class ModelMismatchError(ProviderError):
    """The served model is not the requested one; results would be mislabelled."""

    failure_class = "model_mismatch"


class MalformedOutputError(ProviderError):
    """The provider's output could not be parsed into a trajectory."""

    failure_class = "malformed_output"


class Usage(BaseModel):
    """Token accounting as reported by the provider (zeros when unknown)."""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_creation_tokens=self.cache_creation_tokens + other.cache_creation_tokens,
        )


class ToolCall(BaseModel):
    """One tool invocation with as much of its input and result as the provider exposes.

    ``command`` is the shell command for command-running tools so graders can pattern-match
    "did the agent run ``run.py``" without knowing each provider's input schema.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    input: dict[str, object] = Field(default_factory=dict)
    command: str | None = None
    result: str | None = None
    is_error: bool = False

    def signature(self) -> str:
        """Text that ``tool_called`` patterns are matched against: name plus command or input."""
        body = self.command if self.command is not None else _compact(self.input)
        return f"{self.name} {body}"


def _compact(value: dict[str, object]) -> str:
    """Render tool input as ``key=value`` pairs; JSON would add quoting noise to patterns."""
    return " ".join(f"{k}={v}" for k, v in value.items())


class TurnRecord(BaseModel):
    """What happened between one user message and the agent's answer to it."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    final_answer: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    served_model: str | None = None
    usage: Usage = Field(default_factory=Usage)
    cost_usd: float | None = None
    num_turns: int = 0
    duration_s: float = 0.0
    stop_reason: str | None = None
    session_id: str | None = None
    is_error: bool = False
    permission_denials: list[str] = Field(default_factory=list)


class Trajectory(BaseModel):
    """The full conversation of one case, in the shape graders consume."""

    model_config = ConfigDict(frozen=True)

    provider: str
    requested_model: str
    turns: list[TurnRecord]
    raw_events_path: str | None = None

    @property
    def final_answer(self) -> str:
        """The agent's answer to the last user message; empty if there were no turns."""
        return self.turns[-1].final_answer if self.turns else ""

    @property
    def tool_calls(self) -> list[ToolCall]:
        """All tool calls of all turns in order."""
        return [call for turn in self.turns for call in turn.tool_calls]

    @property
    def served_models(self) -> list[str]:
        """Distinct served model ids, in order of first appearance."""
        seen: dict[str, None] = {}
        for turn in self.turns:
            if turn.served_model:
                seen.setdefault(turn.served_model, None)
        return list(seen)

    @property
    def usage(self) -> Usage:
        """Token totals over all turns."""
        total = Usage()
        for turn in self.turns:
            total = total + turn.usage
        return total

    @property
    def cost_usd(self) -> float | None:
        """Total cost, or ``None`` when no turn reported a cost."""
        costs = [t.cost_usd for t in self.turns if t.cost_usd is not None]
        return sum(costs) if costs else None

    @property
    def num_turns(self) -> int:
        """Model turns summed over all user messages."""
        return sum(t.num_turns for t in self.turns)

    @property
    def duration_s(self) -> float:
        """Wall-clock seconds summed over all user messages."""
        return sum(t.duration_s for t in self.turns)

    @property
    def stop_reason(self) -> str | None:
        """Stop reason of the last turn."""
        return self.turns[-1].stop_reason if self.turns else None

    @property
    def session_id(self) -> str | None:
        """Session id of the conversation (from the first turn)."""
        return self.turns[0].session_id if self.turns else None


class ModelProvider(Protocol):
    """Runs a multi-turn conversation in a sandbox and returns the trajectory.

    Implementations must raise :class:`ProviderError` subclasses for infrastructure failures
    and must never fabricate an answer; an empty answer from a completed run is returned as is
    so graders can fail it on the evidence.
    """

    @property
    def name(self) -> str:
        """Short provider label recorded in results (``claude-cli``, ``openrouter``)."""
        ...

    @property
    def model(self) -> str:
        """The requested model id or alias."""
        ...

    def run(self, turns: Sequence[str], workdir: Path, events_path: Path) -> Trajectory:
        """Send ``turns`` one after another with ``workdir`` as the agent's cwd.

        Args:
            turns: User messages in order; later ones are follow-ups in the same session.
            workdir: Sandbox root; the agent's tools run here.
            events_path: Where raw provider events (JSON lines) are written for evidence.

        Returns:
            The trajectory of the whole conversation.

        Raises:
            ProviderError: On timeout, rate limit, transport failure, model mismatch or
                unparsable output.
        """
        ...
