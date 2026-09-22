"""Description-triggering check: does the skill activate for the right queries and only those?

Claude Code decides whether to load a skill from its frontmatter ``description``. This module
sends each query from ``trigger_evals.json`` to a sandbox where only the skill under test is
installed and looks for an invocation in the trajectory. Detection is deliberately generous
about *how* the skill was used (the ``Skill`` tool, or reading ``SKILL.md``, or running
anything under the skill directory) and strict about *which* skill, so a namespaced or
similarly named skill does not count.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from rich.console import Console

from skill_evals.providers.base import ModelProvider, ProviderError, RateLimitedError, Trajectory
from skill_evals.records import ErrorRecord, append_jsonl, read_jsonl
from skill_evals.runner import RateLimitGate
from skill_evals.sandbox import Sandbox

__all__ = [
    "InvocationEvidence",
    "TriggerCase",
    "TriggerConfig",
    "TriggerObservation",
    "TriggerReport",
    "detect_skill_invocation",
    "load_trigger_cases",
    "render_trigger_markdown",
    "run_trigger",
]


class TriggerCase(BaseModel):
    """One query and whether the skill should activate for it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(min_length=1)
    should_trigger: bool


def load_trigger_cases(path: Path) -> list[TriggerCase]:
    """Load ``trigger_evals.json`` (a JSON list of ``{"query", "should_trigger"}``)."""
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        msg = f"{path}: expected a JSON list"
        raise ValueError(msg)
    return [TriggerCase.model_validate(item) for item in raw]


@dataclass(frozen=True, slots=True)
class InvocationEvidence:
    """Whether and how the skill was used."""

    invoked: bool
    how: str


def detect_skill_invocation(trajectory: Trajectory, skill_name: str) -> InvocationEvidence:
    """Decide from tool calls whether ``skill_name`` was invoked.

    Counts as invoked (first match wins, in this order):

    1. a ``Skill`` tool call whose ``skill`` argument is the name (or ``plugin:name``);
    2. a ``Read`` of ``.../skills/<name>/SKILL.md``;
    3. any other tool call whose command or input mentions ``skills/<name>/``.

    Prose mentions of the skill in the answer do not count: the point is whether the
    mechanism fired, not whether the model talked about it.
    """
    name = re.escape(skill_name)
    dir_pattern = re.compile(rf"skills[\\/]{name}[\\/]", re.IGNORECASE)
    md_pattern = re.compile(rf"skills[\\/]{name}[\\/]SKILL\.md", re.IGNORECASE)
    for call in trajectory.tool_calls:
        if call.name == "Skill":
            target = str(call.input.get("skill", "")).strip().lower()
            if target == skill_name.lower() or target.endswith(f":{skill_name.lower()}"):
                return InvocationEvidence(True, f"Skill tool: {target}")
        elif call.name == "Read" and md_pattern.search(call.signature()):
            return InvocationEvidence(True, "Read SKILL.md")
        elif dir_pattern.search(call.signature()):
            return InvocationEvidence(True, f"{call.name} touched the skill directory")
    return InvocationEvidence(False, "no Skill call, SKILL.md read or skill-directory access")


@dataclass(frozen=True, slots=True)
class TriggerConfig:
    """Inputs of a trigger run; see :class:`skill_evals.runner.RunConfig` for the shared fields."""

    cases_path: Path
    skill_path: Path
    provider: ModelProvider
    run_dir: Path
    reps: int = 3
    parallelism: int = 2
    resume: bool = True
    keep_sandboxes: bool = True
    rate_limit_pause_s: float = 300.0
    max_rate_limit_retries: int = 6
    log: Console = field(default_factory=lambda: Console(stderr=True))


class TriggerObservation(BaseModel):
    """One (query, rep) outcome."""

    model_config = ConfigDict(frozen=True)

    index: int
    query: str
    should_trigger: bool
    rep: int
    invoked: bool
    how: str
    served_models: list[str]
    num_turns: int
    cost_usd: float | None


class TriggerReport(BaseModel):
    """Precision/recall of the description plus the confusion list."""

    model_config = ConfigDict(frozen=True)

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    n_queries: int
    reps: int
    true_positive: int
    false_positive: int
    false_negative: int
    true_negative: int
    precision: float | None
    recall: float | None
    accuracy: float | None
    confusions: list[TriggerObservation]
    observations: list[TriggerObservation]
    errors_by_class: dict[str, int]


def run_trigger(config: TriggerConfig) -> TriggerReport:
    """Run every (query, rep), detect invocations and compute precision/recall."""
    cases = load_trigger_cases(config.cases_path)
    config.run_dir.mkdir(parents=True, exist_ok=True)
    obs_path = config.run_dir / "observations.jsonl"
    done = (
        {(o.index, o.rep) for o in read_jsonl(obs_path, TriggerObservation)}
        if config.resume
        else set()
    )
    todo = [
        (i, case, rep)
        for i, case in enumerate(cases)
        for rep in range(1, config.reps + 1)
        if (i, rep) not in done
    ]
    config.log.log(f"trigger: {len(todo)} case(s) to run, {len(done)} already done")
    gate = RateLimitGate()
    lock = threading.Lock()

    def work(item: tuple[int, TriggerCase, int]) -> None:
        outcome = _run_one(item, config, gate)
        with lock:
            if isinstance(outcome, TriggerObservation):
                append_jsonl(obs_path, outcome)
            else:
                append_jsonl(config.run_dir / "errors.jsonl", outcome)

    with ThreadPoolExecutor(max_workers=max(1, config.parallelism)) as pool:
        list(pool.map(work, todo))
    observations = read_jsonl(obs_path, TriggerObservation)
    errors = read_jsonl(config.run_dir / "errors.jsonl", ErrorRecord)
    report = _summarise(observations, errors, len(cases), config.reps)
    (config.run_dir / "trigger.json").write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (config.run_dir / "trigger.md").write_text(
        render_trigger_markdown(report), encoding="utf-8", newline="\n"
    )
    return report


def _run_one(
    item: tuple[int, TriggerCase, int], config: TriggerConfig, gate: RateLimitGate
) -> TriggerObservation | ErrorRecord:
    index, case, rep = item
    slug = f"q{index:03d}-rep-{rep}"
    for attempt in range(config.max_rate_limit_retries + 1):
        gate.wait()
        try:
            return _attempt(index, case, rep, slug, config)
        except RateLimitedError as exc:
            gate.pause(exc.retry_after_s or config.rate_limit_pause_s)
            if attempt == config.max_rate_limit_retries:
                return _error(slug, rep, exc.failure_class, str(exc))
        except ProviderError as exc:
            return _error(slug, rep, exc.failure_class, str(exc))
        except Exception as exc:
            return _error(slug, rep, "harness_error", f"{exc}\n{traceback.format_exc()}")
    msg = "unreachable"
    raise AssertionError(msg)


def _error(slug: str, rep: int, failure_class: str, message: str) -> ErrorRecord:
    return ErrorRecord(
        scenario_id=slug,
        rep=rep,
        variant="trigger",
        failure_class=failure_class,
        message=message[:4000],
    )


def _attempt(
    index: int, case: TriggerCase, rep: int, slug: str, config: TriggerConfig
) -> TriggerObservation:
    case_dir = config.run_dir / "cases" / slug
    sandbox_dir = config.run_dir / "sandboxes" / slug
    for path in (case_dir, sandbox_dir):
        if path.exists():
            shutil.rmtree(path)
    case_dir.mkdir(parents=True)
    sandbox = Sandbox.create(config.skill_path, sandbox_dir)
    config.log.log(f"{slug}: {case.query[:60]!r}")
    trajectory = config.provider.run([case.query], sandbox.root, case_dir / "events.jsonl")
    (case_dir / "trajectory.json").write_text(
        trajectory.model_dump_json(indent=2), encoding="utf-8"
    )
    if not config.keep_sandboxes:
        sandbox.remove()
    evidence = detect_skill_invocation(trajectory, sandbox.skill_name)
    config.log.log(f"{slug}: invoked={evidence.invoked} (expected {case.should_trigger})")
    return TriggerObservation(
        index=index,
        query=case.query,
        should_trigger=case.should_trigger,
        rep=rep,
        invoked=evidence.invoked,
        how=evidence.how,
        served_models=trajectory.served_models,
        num_turns=trajectory.num_turns,
        cost_usd=trajectory.cost_usd,
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _summarise(
    observations: list[TriggerObservation], errors: list[ErrorRecord], n_queries: int, reps: int
) -> TriggerReport:
    tp = sum(o.invoked and o.should_trigger for o in observations)
    fp = sum(o.invoked and not o.should_trigger for o in observations)
    fn = sum(not o.invoked and o.should_trigger for o in observations)
    tn = sum(not o.invoked and not o.should_trigger for o in observations)
    by_class: dict[str, int] = {}
    for e in errors:
        by_class[e.failure_class] = by_class.get(e.failure_class, 0) + 1
    return TriggerReport(
        n_queries=n_queries,
        reps=reps,
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        true_negative=tn,
        precision=_ratio(tp, tp + fp),
        recall=_ratio(tp, tp + fn),
        accuracy=_ratio(tp + tn, len(observations)),
        confusions=sorted(
            (o for o in observations if o.invoked != o.should_trigger),
            key=lambda o: (o.index, o.rep),
        ),
        observations=sorted(observations, key=lambda o: (o.index, o.rep)),
        errors_by_class=dict(sorted(by_class.items())),
    )


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def render_trigger_markdown(report: TriggerReport) -> str:
    """Render ``trigger.md``."""
    lines = [
        f"# Trigger check ({report.generated_at:%Y-%m-%d %H:%M} UTC)",
        "",
        f"{report.n_queries} queries × {report.reps} reps; "
        f"precision {_pct(report.precision)}, recall {_pct(report.recall)}, "
        f"accuracy {_pct(report.accuracy)}.",
        "",
        f"TP {report.true_positive} / FP {report.false_positive} / "
        f"FN {report.false_negative} / TN {report.true_negative}; errors: {report.errors_by_class}",
        "",
        "## Confusions",
        "",
    ]
    if report.confusions:
        lines += ["| Query | Expected | Invoked | Rep | How |", "|---|---|---|---|---|"]
        lines += [
            f"| {o.query} | {o.should_trigger} | {o.invoked} | {o.rep} | {o.how} |"
            for o in report.confusions
        ]
    else:
        lines.append("None.")
    lines.append("")
    return "\n".join(lines)
