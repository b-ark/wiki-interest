"""Grader sanity check: an ideal answer must pass, a useless one must fail.

Before any paid run, the deterministic graders are exercised on two synthetic agents per
scenario, without calling a model:

* the **oracle** runs the skill's own pipeline on hand-written requests
  (``evals/oracle/<scenario>.json``) exactly as a perfect agent would, and answers with the
  generated ``summary.md`` verbatim;
* the **null** agent calls no tools, produces no files and answers "I don't know".

An assertion the oracle fails is too strict or wrongly written; an assertion the null agent
passes does not discriminate. Budget and prohibition assertions (``max_turns``,
``no_tool_called``...) pass for the null agent by design and are reported as such, not as
defects. The oracle requests live next to the scenarios but outside the sandbox copy of the
skill, so the agent under test never sees them.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from skill_evals.graders.deterministic import GradeContext, grade
from skill_evals.providers.base import ToolCall, Trajectory, TurnRecord
from skill_evals.scenarios import Assertion, Scenario

__all__ = [
    "NULL_ANSWER",
    "NULL_NEUTRAL_TYPES",
    "AssertionCheck",
    "OracleReport",
    "OracleSpec",
    "PipelineRunner",
    "ScenarioCheck",
    "load_oracle_spec",
    "render_markdown",
    "run_oracle",
    "uv_pipeline_runner",
]

NULL_ANSWER = "I don't know."
NULL_NEUTRAL_TYPES = frozenset(
    {"no_tool_called", "answer_not_contains", "max_turns", "max_cost_usd"}
)
"""Assertion types that forbid or bound behaviour; doing nothing trivially satisfies them."""

CLARIFICATION_REPLY = "Which of these do you mean?"
"""What an ideal agent adds after relaying the candidates of a clarification summary."""

_ORACLE_TURNS_PER_REQUEST = 3
"""Model turns an efficient agent needs per request: write request.json, run, answer."""


class OracleSpec(BaseModel):
    """Requests a perfect agent would send, one per user turn."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requests: list[dict[str, object]] = Field(min_length=1)


def load_oracle_spec(path: Path) -> OracleSpec:
    """Read one ``evals/oracle/<scenario>.json`` file."""
    return OracleSpec.model_validate_json(path.read_text(encoding="utf-8"))


@dataclass(frozen=True, slots=True)
class PipelineOutput:
    """What one pipeline invocation returned."""

    exit_code: int
    payload: dict[str, object]


PipelineRunner = Callable[[Path, Path], PipelineOutput]
"""``(request_file, runs_dir) -> output``; injected so tests need no real skill."""


def uv_pipeline_runner(skill_dir: Path, *, timeout_s: int = 600) -> PipelineRunner:
    """Run ``scripts/run.py`` of ``skill_dir`` through ``uv``, as the agent would."""
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv is not on PATH; the oracle runs the skill's pipeline with it"
        raise RuntimeError(msg)

    def run(request_file: Path, runs_dir: Path) -> PipelineOutput:
        completed = subprocess.run(
            [
                uv,
                "run",
                "--directory",
                str(skill_dir),
                "scripts/run.py",
                str(request_file.resolve()),
                "--runs-dir",
                str(runs_dir.resolve()),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_s,
            check=False,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"error": completed.stdout[-500:] + completed.stderr[-500:]}
        return PipelineOutput(completed.returncode, payload)

    return run


@dataclass(frozen=True, slots=True)
class AssertionCheck:
    """One assertion graded for the oracle and the null agent."""

    index: int
    type: str
    oracle_passed: bool
    oracle_evidence: str
    null_passed: bool
    null_evidence: str

    @property
    def too_strict(self) -> bool:
        """The ideal answer fails: the assertion or the scenario is wrong."""
        return not self.oracle_passed

    @property
    def not_discriminating(self) -> bool:
        """Doing nothing passes an assertion that is supposed to require work."""
        return self.null_passed and self.type not in NULL_NEUTRAL_TYPES


@dataclass(frozen=True, slots=True)
class ScenarioCheck:
    """Oracle and null results for one scenario, or why it could not be checked."""

    scenario_id: str
    checks: tuple[AssertionCheck, ...] = ()
    error: str | None = None
    exit_codes: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class OracleReport:
    """All scenario checks plus the headline numbers."""

    scenarios: tuple[ScenarioCheck, ...]
    skipped: tuple[str, ...] = field(default_factory=tuple)

    @property
    def _checks(self) -> list[AssertionCheck]:
        return [c for s in self.scenarios for c in s.checks]

    @property
    def oracle_pass_rate(self) -> float | None:
        """Share of assertions the ideal answer passes (should be 1.0)."""
        checks = self._checks
        return sum(c.oracle_passed for c in checks) / len(checks) if checks else None

    @property
    def null_pass_rate(self) -> float | None:
        """Share of work-requiring assertions the null agent passes (should be 0.0)."""
        checks = [c for c in self._checks if c.type not in NULL_NEUTRAL_TYPES]
        return sum(c.null_passed for c in checks) / len(checks) if checks else None

    @property
    def healthy(self) -> bool:
        """No errors, nothing too strict, nothing non-discriminating."""
        return all(s.error is None for s in self.scenarios) and not any(
            c.too_strict or c.not_discriminating for c in self._checks
        )

    def to_dict(self) -> dict[str, object]:
        """JSON-ready representation."""
        return {
            "healthy": self.healthy,
            "oracle_pass_rate": self.oracle_pass_rate,
            "null_pass_rate": self.null_pass_rate,
            "skipped": list(self.skipped),
            "scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "error": s.error,
                    "exit_codes": list(s.exit_codes),
                    "checks": [
                        {
                            "index": c.index,
                            "type": c.type,
                            "oracle_passed": c.oracle_passed,
                            "oracle_evidence": c.oracle_evidence,
                            "null_passed": c.null_passed,
                            "null_evidence": c.null_evidence,
                        }
                        for c in s.checks
                    ],
                }
                for s in self.scenarios
            ],
        }


def run_oracle(
    scenarios: Sequence[Scenario],
    oracle_dir: Path,
    out_dir: Path,
    runner: PipelineRunner,
) -> OracleReport:
    """Grade every scenario that has an oracle spec, for the oracle and the null agent.

    Args:
        scenarios: Scenarios to check, in order.
        oracle_dir: Directory with ``<scenario-id>.json`` specs.
        out_dir: Where pipeline outputs are written (one subdirectory per scenario).
        runner: Executes one request; see :func:`uv_pipeline_runner`.

    Returns:
        The report; scenarios without a spec are listed in ``skipped``.
    """
    results: list[ScenarioCheck] = []
    skipped: list[str] = []
    for scenario in scenarios:
        spec_path = oracle_dir / f"{scenario.id}.json"
        if not spec_path.is_file():
            skipped.append(scenario.id)
            continue
        results.append(_check_scenario(scenario, load_oracle_spec(spec_path), out_dir, runner))
    return OracleReport(tuple(results), tuple(skipped))


def _check_scenario(
    scenario: Scenario, spec: OracleSpec, out_dir: Path, runner: PipelineRunner
) -> ScenarioCheck:
    if len(spec.requests) != len(scenario.turns):
        return ScenarioCheck(
            scenario.id,
            error=f"{len(spec.requests)} oracle requests for {len(scenario.turns)} turns",
        )
    case_dir = out_dir / scenario.id
    if case_dir.exists():
        shutil.rmtree(case_dir)
    artifacts = case_dir / "artifacts"
    requests_dir = case_dir / "requests"
    requests_dir.mkdir(parents=True)
    turns: list[TurnRecord] = []
    exit_codes: list[int] = []
    for index, (prompt, request) in enumerate(zip(scenario.turns, spec.requests, strict=True)):
        request_file = requests_dir / f"request-{index + 1}.json"
        request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        output = runner(request_file, artifacts / "runs")
        exit_codes.append(output.exit_code)
        answer = _ideal_answer(output)
        if answer is None:
            return ScenarioCheck(
                scenario.id,
                error=f"pipeline exit {output.exit_code}: {output.payload.get('error')}",
                exit_codes=tuple(exit_codes),
            )
        turns.append(_oracle_turn(prompt, request_file, answer))
    oracle = Trajectory(provider="oracle", requested_model="oracle", turns=turns)
    null = Trajectory(
        provider="null",
        requested_model="null",
        turns=[TurnRecord(prompt=p, final_answer=NULL_ANSWER, num_turns=1) for p in scenario.turns],
    )
    empty = case_dir / "null-artifacts"
    empty.mkdir()
    checks = tuple(
        _check(i, assertion, GradeContext(artifacts, oracle), GradeContext(empty, null))
        for i, assertion in enumerate(scenario.assertions)
    )
    return ScenarioCheck(scenario.id, checks, exit_codes=tuple(exit_codes))


def _ideal_answer(output: PipelineOutput) -> str | None:
    """``summary.md`` verbatim, plus the question an ideal agent asks after a clarification."""
    summary_md = output.payload.get("summary_md")
    if output.exit_code not in (0, 3) or not isinstance(summary_md, str):
        return None
    text = Path(summary_md).read_text(encoding="utf-8")
    if output.payload.get("status") == "needs_clarification":
        text = f"{text}\n\n{CLARIFICATION_REPLY}"
    return text


def _oracle_turn(prompt: str, request_file: Path, answer: str) -> TurnRecord:
    command = f"uv run scripts/run.py {request_file.name}"
    return TurnRecord(
        prompt=prompt,
        final_answer=answer,
        tool_calls=[ToolCall(name="Bash", input={"command": command}, command=command)],
        num_turns=_ORACLE_TURNS_PER_REQUEST,
        cost_usd=0.0,
    )


def _check(
    index: int, assertion: Assertion, oracle: GradeContext, null: GradeContext
) -> AssertionCheck:
    good = grade(assertion, oracle)
    bad = grade(assertion, null)
    return AssertionCheck(
        index=index,
        type=assertion.type,
        oracle_passed=good.passed,
        oracle_evidence=good.evidence,
        null_passed=bad.passed,
        null_evidence=bad.evidence,
    )


def render_markdown(report: OracleReport) -> str:
    """Human-readable report: headline, then only the problems, then a per-scenario table."""
    lines = [
        "# Grader sanity check (oracle vs null agent)",
        "",
        f"- Healthy: **{'yes' if report.healthy else 'no'}**",
        f"- Oracle pass rate (should be 100 %): {_pct(report.oracle_pass_rate)}",
        f"- Null pass rate on work-requiring assertions (should be 0 %): "
        f"{_pct(report.null_pass_rate)}",
    ]
    if report.skipped:
        lines.append(f"- Scenarios without an oracle spec: {', '.join(report.skipped)}")
    problems: list[str] = []
    for scenario in report.scenarios:
        for c in scenario.checks:
            where = f"- `{scenario.scenario_id}` a{c.index} `{c.type}`"
            if c.too_strict:
                problems.append(f"{where}: oracle FAILS: {c.oracle_evidence}")
            if c.not_discriminating:
                problems.append(f"{where}: null PASSES: {c.null_evidence}")
    errors = [f"- `{s.scenario_id}`: {s.error}" for s in report.scenarios if s.error]
    lines += ["", "## Problems", "", *(errors + problems or ["None."])]
    lines += [
        "",
        "## Per scenario",
        "",
        "| Scenario | Exit codes | Oracle | Null |",
        "|---|---|---|---|",
    ]
    for s in report.scenarios:
        total = len(s.checks)
        oracle_ok = sum(c.oracle_passed for c in s.checks)
        null_ok = sum(c.null_passed for c in s.checks)
        codes = ", ".join(map(str, s.exit_codes)) or "-"
        lines.append(f"| {s.scenario_id} | {codes} | {oracle_ok}/{total} | {null_ok}/{total} |")
    return "\n".join(lines) + "\n"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.0%}"
