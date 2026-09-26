"""Grader sanity check: an ideal answer must pass, a useless one must fail.

Before any paid run, the deterministic graders are exercised on two synthetic agents per
scenario, without calling a model:

* the **oracle** runs the skill's own pipeline on hand-written requests
  (``evals/oracle/<scenario>.json``) exactly as a perfect agent would; after a finished run
  it has the code's own report text rendered (``render.py --narrative``, as an agent sends
  its text) and answers with the chat answer that returns, else with ``summary.md``;
* the **null** agent calls no tools, produces no files and answers "I don't know".

An assertion the oracle fails is too strict or wrongly written; an assertion the null agent
passes does not discriminate. Budget and prohibition assertions (``max_turns``,
``no_tool_called``...) pass for the null agent by design and are reported as such, not as
defects. The oracle requests live next to the scenarios but outside the sandbox copy of the
skill, so the agent under test never sees them.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from skill_evals.graders.deterministic import GradeContext, grade
from skill_evals.providers.base import ToolCall, Trajectory, TurnRecord
from skill_evals.scenarios import STAGE_ENV, Assertion, Scenario

__all__ = [
    "NULL_ANSWER",
    "NULL_NEUTRAL_TYPES",
    "AssertionCheck",
    "Narrator",
    "OracleReport",
    "OracleSpec",
    "PipelineRunner",
    "ScenarioCheck",
    "load_oracle_spec",
    "render_markdown",
    "run_oracle",
    "uv_narrator",
    "uv_pipeline_runner",
]

NULL_ANSWER = "I don't know."
NULL_NEUTRAL_TYPES = frozenset(
    {
        "no_tool_called",
        "answer_not_contains",
        "max_turns",
        "max_cost_usd",
        "chat_answer_relayed",
        "question_relayed",
    }
)
"""Assertion types that forbid or bound behaviour, or hold only once something was produced
(a relayed text, a relayed question); doing nothing trivially satisfies them."""

MODEL_ONLY_TYPES = frozenset({"narrative_accepted", "chat_answer_relayed", "answer_contains"})
"""Checks of the report text. The oracle sends the code's own text, written in English; in a
report in another language the skill rightly rejects it, and only a model that writes in the
user's language can pass these, so the oracle marks them instead of failing them."""

_LANGUAGE_PROBLEM = "in the report language"
"""Words of the skill's rejection of a text in the wrong language (narrative_check)."""

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


PipelineRunner = Callable[[Path, Path, Mapping[str, str]], PipelineOutput]
"""``(request_file, runs_dir, extra_env) -> output``; injected so tests need no real skill.
``extra_env`` carries the scenario's stage (see ``Scenario.stage``)."""


def uv_pipeline_runner(skill_dir: Path, *, timeout_s: int = 600) -> PipelineRunner:
    """Run ``scripts/run.py`` of ``skill_dir`` through ``uv``, as the agent would."""
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv is not on PATH; the oracle runs the skill's pipeline with it"
        raise RuntimeError(msg)

    def run(request_file: Path, runs_dir: Path, extra_env: Mapping[str, str]) -> PipelineOutput:
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"} | dict(extra_env)
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
            env=env,
        )
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError:
            payload = {"error": completed.stdout[-500:] + completed.stderr[-500:]}
        return PipelineOutput(completed.returncode, payload)

    return run


Narrator = Callable[[Path], PipelineOutput]
"""Renders the code's own report text for a finished run directory, as an agent would."""

_TEMPLATE_SCRIPT = """
import json, sys
from pathlib import Path
from wiki_interest.application.facts import template_narrative
from wiki_interest.application.runs import load_summary
from wiki_interest.i18n import Translator
run_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
facts = json.loads((run_dir / "facts.json").read_text(encoding="utf-8"))
summary = load_summary(run_dir)
text = template_narrative(summary, Translator(summary.request.report.language), ui=facts["ui"])
out.write_text(text.model_dump_json(), encoding="utf-8")
"""
"""Writes the text the code composes for a run (the one the skill falls back to)."""


def uv_narrator(skill_dir: Path, *, timeout_s: int = 600) -> Narrator:
    """Write the code's own text for a run and render it with ``scripts/render.py``."""
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv is not on PATH; the oracle renders the report text with it"
        raise RuntimeError(msg)

    def call(args: list[str]) -> subprocess.CompletedProcess[str]:
        env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
        return subprocess.run(
            [uv, "run", "--directory", str(skill_dir), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_s,
            check=False,
            env=env,
        )

    def narrate(run_dir: Path) -> PipelineOutput:
        text = run_dir / "oracle-narrative.json"
        written = call(["python", "-c", _TEMPLATE_SCRIPT, str(run_dir.resolve()), str(text)])
        if written.returncode != 0:
            return PipelineOutput(written.returncode, {"error": written.stderr[-500:]})
        rendered = call(["scripts/render.py", str(run_dir.resolve()), "--narrative", str(text)])
        try:
            payload = json.loads(rendered.stdout)
        except json.JSONDecodeError:
            payload = {"error": rendered.stdout[-500:] + rendered.stderr[-500:]}
        return PipelineOutput(rendered.returncode, payload)

    return narrate


@dataclass(frozen=True, slots=True)
class AssertionCheck:
    """One assertion graded for the oracle and the null agent."""

    index: int
    type: str
    oracle_passed: bool
    oracle_evidence: str
    null_passed: bool
    null_evidence: str
    model_only: bool = False
    """The oracle cannot pass it: the report text must be in a language only a model writes."""

    @property
    def too_strict(self) -> bool:
        """The ideal answer fails: the assertion or the scenario is wrong."""
        return not self.oracle_passed and not self.model_only

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
                            "model_only": c.model_only,
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
    narrator: Narrator | None = None,
) -> OracleReport:
    """Grade every scenario that has an oracle spec, for the oracle and the null agent.

    Args:
        scenarios: Scenarios to check, in order.
        oracle_dir: Directory with ``<scenario-id>.json`` specs.
        out_dir: Where pipeline outputs are written (one subdirectory per scenario).
        runner: Executes one request; see :func:`uv_pipeline_runner`.
        narrator: Renders the report text of a finished run (:func:`uv_narrator`); without
            it the oracle answers with ``summary.md`` and sends no text.

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
        spec = load_oracle_spec(spec_path)
        results.append(_check_scenario(scenario, spec, out_dir, runner, narrator))
    return OracleReport(tuple(results), tuple(skipped))


def _check_scenario(
    scenario: Scenario,
    spec: OracleSpec,
    out_dir: Path,
    runner: PipelineRunner,
    narrator: Narrator | None = None,
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
    untranslated = False
    for index, (prompt, request) in enumerate(zip(scenario.turns, spec.requests, strict=True)):
        request_file = requests_dir / f"request-{index + 1}.json"
        request_file.write_text(json.dumps(request, ensure_ascii=False), encoding="utf-8")
        output = runner(request_file, artifacts / "runs", STAGE_ENV.get(scenario.stage, {}))
        exit_codes.append(output.exit_code)
        answer = _ideal_answer(output)
        if answer is None:
            return ScenarioCheck(
                scenario.id,
                error=f"pipeline exit {output.exit_code}: {output.payload.get('error')}",
                exit_codes=tuple(exit_codes),
            )
        render = _render(output, narrator)
        if render is not None and isinstance(render.payload.get("chat_answer"), str):
            answer = str(render.payload["chat_answer"])
        untranslated = untranslated or (render is not None and _only_language(render))
        turns.append(_oracle_turn(prompt, request_file, answer, render))
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
    if untranslated:
        checks = tuple(
            replace(c, model_only=True) if c.type in MODEL_ONLY_TYPES and not c.oracle_passed else c
            for c in checks
        )
    return ScenarioCheck(scenario.id, checks, exit_codes=tuple(exit_codes))


def _only_language(render: PipelineOutput) -> bool:
    """The code's text was rejected for its language alone, which only a model can write."""
    problems = render.payload.get("problems")
    return (
        render.payload.get("status") != "accepted"
        and isinstance(problems, list)
        and bool(problems)
        and all(
            isinstance(p, dict) and _LANGUAGE_PROBLEM in str(p.get("message", "")) for p in problems
        )
    )


def _ideal_answer(output: PipelineOutput) -> str | None:
    """``summary.md`` verbatim, plus the question an ideal agent asks after a clarification.

    A question the code composed (``clarification.ask_user``) is sent word for word, as the
    skill tells the agent to.
    """
    summary_md = output.payload.get("summary_md")
    if output.exit_code not in (0, 3) or not isinstance(summary_md, str):
        return None
    clarification = output.payload.get("clarification")
    if isinstance(clarification, dict) and isinstance(clarification.get("ask_user"), str):
        return str(clarification["ask_user"])
    text = Path(summary_md).read_text(encoding="utf-8")
    if output.payload.get("status") == "needs_clarification":
        text = f"{text}\n\n{CLARIFICATION_REPLY}"
    return text


def _render(output: PipelineOutput, narrator: Narrator | None) -> PipelineOutput | None:
    """The report text rendered for a finished run, when a narrator is given."""
    run_dir = output.payload.get("run_dir")
    if narrator is None or output.exit_code != 0 or not isinstance(run_dir, str):
        return None
    return narrator(Path(run_dir))


def _oracle_turn(
    prompt: str, request_file: Path, answer: str, render: PipelineOutput | None = None
) -> TurnRecord:
    command = f"uv run scripts/run.py {request_file.name}"
    calls = [ToolCall(name="Bash", input={"command": command}, command=command)]
    if render is not None:
        rendered = "uv run scripts/render.py <run_dir> --narrative oracle-narrative.json"
        calls.append(
            ToolCall(
                name="Bash",
                input={"command": rendered},
                command=rendered,
                result=json.dumps(render.payload, ensure_ascii=False),
            )
        )
    return TurnRecord(
        prompt=prompt,
        final_answer=answer,
        tool_calls=calls,
        num_turns=_ORACLE_TURNS_PER_REQUEST + (1 if render is not None else 0),
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
    model_only = [
        f"- `{s.scenario_id}` a{c.index} `{c.type}`"
        for s in report.scenarios
        for c in s.checks
        if c.model_only
    ]
    if model_only:
        lines += [
            "",
            "## Checks only a model can pass",
            "",
            "The report is not in English, and the oracle's text is the code's own English one.",
            "",
            *model_only,
        ]
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
