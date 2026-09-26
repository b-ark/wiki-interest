"""Records written to ``results.jsonl`` and ``errors.jsonl`` and read back by the report.

Keeping the two files separate is deliberate: a case that could not be measured (timeout,
rate limit, crashed harness) must never look like a case the agent failed. The report counts
errors by class next to the scores so a run with many errors is visibly untrustworthy.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from skill_evals.providers.base import Usage

__all__ = [
    "CaseResult",
    "CaseStatus",
    "ErrorRecord",
    "GradeRecord",
    "append_jsonl",
    "read_jsonl",
]

CaseStatus = Literal["ok", "truncated", "refused"]
"""``truncated``: the agent hit the turn budget; ``refused``: the model refused outright.
Both are still graded (the agent did produce a trajectory), unlike infrastructure errors."""


class GradeRecord(BaseModel):
    """Outcome of one assertion or rubric criterion."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: Literal["deterministic", "judge"]
    type: str
    text: str
    passed: bool
    evidence: str


class CaseResult(BaseModel):
    """One graded (scenario, rep) pair."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    rep: int
    variant: str
    skill_hash: str
    provider: str
    requested_model: str
    served_models: list[str]
    status: CaseStatus
    grades: list[GradeRecord]
    usage: Usage
    cost_usd: float | None
    num_turns: int
    duration_s: float
    grading_duration_s: float
    session_id: str | None
    case_dir: str
    final_answer: str
    finished_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    judge_error: str | None = None
    """Why the judge gave no verdicts: the agent's run and the deterministic grades are kept,
    and ``skill-evals regrade --judge`` adds the rubric later."""

    @property
    def pass_rate(self) -> float | None:
        """Share of passed grades, or ``None`` when the scenario has no grades at all."""
        if not self.grades:
            return None
        return sum(g.passed for g in self.grades) / len(self.grades)


class ErrorRecord(BaseModel):
    """A case that could not be measured; ``failure_class`` is the bucket the report counts."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    rep: int
    variant: str
    failure_class: str
    message: str
    case_dir: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def append_jsonl(path: Path, record: BaseModel) -> None:
    """Append one record as a JSON line (UTF-8, no BOM, so tools on any OS can read it)."""
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(record.model_dump_json())
        handle.write("\n")


def read_jsonl[T: BaseModel](path: Path, model: type[T]) -> list[T]:
    """Read every non-empty line of ``path`` as ``model``; a missing file is an empty list."""
    if not path.exists():
        return []
    records: list[T] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            records.append(model.model_validate(json.loads(line)))
    return records
