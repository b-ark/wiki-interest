"""Shared fixtures: a tiny skill, a fake provider and a summary.json builder."""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest

from skill_evals.providers.base import ProviderError, ToolCall, Trajectory, TurnRecord, Usage

FIXTURES = Path(__file__).parent / "fixtures"

SKILL_MD = """---
name: demo-skill
description: Demo skill used by the harness tests.
---

# Demo

Run `python scripts/run.py request.json` and relay summary.md.
"""


@pytest.fixture
def skill_dir(tmp_path: Path) -> Path:
    """A minimal skill directory with SKILL.md, a script, and directories that must be excluded."""
    root = tmp_path / "demo-skill"
    (root / "scripts").mkdir(parents=True)
    (root / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    (root / "scripts" / "run.py").write_text("print('hi')\n", encoding="utf-8")
    (root / ".venv" / "Lib").mkdir(parents=True)
    (root / ".venv" / "Lib" / "big.bin").write_bytes(b"x" * 10)
    (root / ".cache").mkdir()
    (root / ".cache" / "stale.sqlite").write_bytes(b"old")
    (root / "evals").mkdir()
    (root / "evals" / "evals.json").write_text("{}", encoding="utf-8")
    return root


def make_summary(
    *,
    level: str = "high",
    checks: Sequence[dict[str, object]] = (),
    growth: float = 0.234,
    views_avg: float = 1234.5,
    headline: str = "Interest grew by 23.4 %",
    status: str = "ok",
) -> dict[str, object]:
    """A summary.json-shaped document with the fields the graders read."""
    return {
        "schema_version": "1",
        "status": status,
        "run_id": "run-20260922-abc",
        "period": {"start": "2024-09", "end": "2026-08"},
        "metrics": [
            {
                "topic_id": "t1",
                "project": "pl.wikipedia",
                "kind": "bundle",
                "views_avg": views_avg,
                "growth_yoy": growth,
                "per_million_avg": 8.75,
                "trend_p_value": 0.012,
            }
        ],
        "reliability": [
            {"topic_id": "t1", "project": "pl.wikipedia", "level": level, "checks": list(checks)}
        ],
        "verdict": {"headline": headline, "bullets": []},
        "limitations": ["Data before 2015-07 is not available."],
    }


def write_summary(target_dir: Path, summary: dict[str, object]) -> Path:
    """Write ``summary`` as ``summary.json`` under ``target_dir`` and return its path."""
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "summary.json"
    path.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return path


def make_trajectory(
    answer: str,
    *,
    tool_calls: Sequence[ToolCall] = (),
    num_turns: int = 3,
    cost: float | None = 0.01,
    stop_reason: str = "end_turn",
    served_model: str = "claude-haiku-4-5-20251001",
    prompts: Sequence[str] = ("hello",),
) -> Trajectory:
    """A trajectory whose last turn has ``answer`` and ``tool_calls``."""
    turns = [
        TurnRecord(
            prompt=p,
            final_answer=answer if i == len(prompts) - 1 else "intermediate",
            tool_calls=list(tool_calls) if i == len(prompts) - 1 else [],
            served_model=served_model,
            usage=Usage(input_tokens=100, output_tokens=50, cache_read_tokens=10),
            cost_usd=cost,
            num_turns=num_turns,
            duration_s=1.5,
            stop_reason=stop_reason,
            session_id="sess-1",
        )
        for i, p in enumerate(prompts)
    ]
    return Trajectory(provider="fake", requested_model="haiku", turns=turns)


class FakeProvider:
    """Provider that returns canned trajectories and optionally writes artifacts or fails.

    ``behaviour`` maps the first prompt to either a trajectory, an exception to raise, or a
    callable ``(workdir) -> Trajectory`` that may create files in the sandbox.
    """

    name = "fake"
    model = "haiku"

    def __init__(
        self,
        behaviour: dict[str, Trajectory | ProviderError | Callable[[Path], Trajectory]],
        default: Trajectory | None = None,
    ) -> None:
        self.behaviour = behaviour
        self.default = default or make_trajectory("default answer")
        self.calls: list[tuple[Sequence[str], Path]] = []

    def run(self, turns: Sequence[str], workdir: Path, events_path: Path) -> Trajectory:
        self.calls.append((list(turns), workdir))
        events_path.parent.mkdir(parents=True, exist_ok=True)
        events_path.write_text('{"type":"fake"}\n', encoding="utf-8")
        action = self.behaviour.get(turns[0], self.default)
        if isinstance(action, ProviderError):
            raise action
        if isinstance(action, Trajectory):
            return action
        return action(workdir)
