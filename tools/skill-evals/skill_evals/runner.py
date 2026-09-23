"""Runner: sandboxes, repetitions, parallelism, resume and the results/errors split.

For every (scenario, rep) the runner creates a fresh sandbox, lets the provider run the
conversation, saves the trajectory and copies the artifacts the agent produced, grades them,
and appends one line to ``results.jsonl``. Anything that prevents measurement (provider
timeout, rate limit, model mismatch, a crash in the harness) is appended to ``errors.jsonl``
with a failure class instead, so a broken environment can never masquerade as a bad skill.
Case order is deterministic (sorted scenario ids, reps ascending) and the run is resumable:
cases already in ``results.jsonl`` are skipped.
"""

from __future__ import annotations

import json
import shutil
import threading
import time
import traceback
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Console

from skill_evals.graders.deterministic import GradeContext, grade
from skill_evals.graders.judge import Judge, JudgeContext
from skill_evals.providers.base import ModelProvider, ProviderError, RateLimitedError, Trajectory
from skill_evals.records import (
    CaseResult,
    CaseStatus,
    ErrorRecord,
    GradeRecord,
    append_jsonl,
    read_jsonl,
)
from skill_evals.sandbox import Sandbox, skill_name_from_frontmatter
from skill_evals.scenarios import (
    AGENT_SESSION_ENV,
    CACHE_PATH_ENV,
    STAGE_ENV,
    Scenario,
    load_scenarios,
)
from skill_evals.shared_env import prepare_shared_env, shared_env_variables

__all__ = [
    "DEFAULT_ARTIFACT_GLOBS",
    "RateLimitGate",
    "RunConfig",
    "RunResult",
    "case_status",
    "collect_artifacts",
    "grade_case",
    "latest_reference",
    "regrade",
    "run",
]

DEFAULT_ARTIFACT_GLOBS: tuple[str, ...] = (
    "**/summary.json",
    "**/summary.md",
    "**/facts.json",
    "**/narrative.json",
    "**/chat_brief.md",
    "**/method.md",
    "**/report.pdf",
    "**/request.json",
    "**/manifest.json",
    "**/charts/*",
    "**/*.png",
    "**/*.svg",
)
"""Files copied from the sandbox into the case directory after the run."""

FACTS_FILE = "facts.json"
_FACTS_INSTRUCTION_KEYS = frozenset(
    {"blocks", "rules", "ui_strings", "template_file", "follow_ups", "report_pdf", "schema_version"}
)
"""Keys of ``facts.json`` that tell the agent how to write, not what the data says."""

_ARTIFACT_SKIP_DIRS = frozenset({".claude", ".venv", ".cache", "__pycache__", ".git"})
"""Never copied as artifacts: the skill copy itself and machine-specific junk. ``runs`` is
deliberately not here because that is where the pipeline writes its bundles."""


class RateLimitGate:
    """Shared pause that all workers respect after any of them is rate-limited.

    A subscription quota is global, so when one worker hits it the others would too; pausing
    everyone until the reset avoids a burst of identical failures.
    """

    def __init__(self, sleep: Callable[[float], None] = time.sleep) -> None:
        self._lock = threading.Lock()
        self._resume_at = 0.0
        self._sleep = sleep

    def pause(self, seconds: float) -> None:
        """Block new provider calls for ``seconds`` from now (never shortens an existing pause)."""
        with self._lock:
            self._resume_at = max(self._resume_at, time.monotonic() + seconds)

    def wait(self) -> None:
        """Sleep until the current pause (if any) has elapsed."""
        while True:
            with self._lock:
                remaining = self._resume_at - time.monotonic()
            if remaining <= 0:
                return
            self._sleep(min(remaining, 5.0))


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Everything one run needs; the provider and judge are injected objects.

    Attributes:
        scenarios_path: ``evals.json``.
        skill_path: The skill directory (a "variant").
        provider: Model provider under test.
        run_dir: Output directory ``runs/<name>/``; created if missing.
        variant: Label for this skill version in reports.
        reps: Repetitions per scenario.
        parallelism: Concurrent cases; 2 is safe for the CLI on a subscription.
        warm_cache: Optional ``.cache`` directory seeded into every sandbox.
        shared_env: Build the skill's Python environment once and let every sandbox use it
            (see :mod:`skill_evals.shared_env`); needed for high parallelism.
        judge: LLM judge for rubric items; ``None`` disables L3 grading.
        resume: Skip (scenario, rep) pairs already present in ``results.jsonl``.
        keep_sandboxes: Keep sandbox directories as evidence (default) or delete them.
        only: Restrict to these scenario ids (empty = all).
        tags: Restrict to scenarios having any of these tags (empty = all).
        artifact_globs: Patterns copied from the sandbox to the case directory.
        rate_limit_pause_s: Default pause when the provider gives no reset time.
        max_rate_limit_retries: Attempts per case before it is recorded as an error.
        reference_glob: Artifact shown to the judge as reference material.
        sleep: Injected sleep (tests pass a no-op).
        log: Console for progress output.
    """

    scenarios_path: Path
    skill_path: Path
    provider: ModelProvider
    run_dir: Path
    variant: str
    reps: int = 3
    parallelism: int = 2
    warm_cache: Path | None = None
    shared_env: bool = False
    judge: Judge | None = None
    resume: bool = True
    keep_sandboxes: bool = True
    only: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()
    artifact_globs: tuple[str, ...] = DEFAULT_ARTIFACT_GLOBS
    rate_limit_pause_s: float = 300.0
    max_rate_limit_retries: int = 6
    reference_glob: str = "**/summary.md"
    sleep: Callable[[float], None] = time.sleep
    log: Console = field(default_factory=lambda: Console(stderr=True))


@dataclass(frozen=True, slots=True)
class RunResult:
    """Outcome of :func:`run`: what was written and where."""

    run_dir: Path
    results: list[CaseResult]
    errors: list[ErrorRecord]
    skipped: int


@dataclass(frozen=True, slots=True)
class _Case:
    scenario: Scenario
    rep: int

    @property
    def key(self) -> tuple[str, int]:
        return (self.scenario.id, self.rep)

    @property
    def slug(self) -> str:
        return f"{self.scenario.id}-rep-{self.rep}"


def run(config: RunConfig) -> RunResult:
    """Execute every selected (scenario, rep) and write ``results.jsonl`` / ``errors.jsonl``."""
    scenario_file = load_scenarios(config.scenarios_path)
    selected = _select(scenario_file.scenarios, config)
    config.run_dir.mkdir(parents=True, exist_ok=True)
    done = _done_keys(config) if config.resume else set()
    cases = [
        _Case(s, rep)
        for s in selected
        for rep in range(1, config.reps + 1)
        if (s.id, rep) not in done
    ]
    _write_run_manifest(config, scenario_file.skill_name, len(selected))
    base_env: dict[str, str] = {}
    if config.shared_env and cases:
        config.log.log("building the shared Python environment")
        env_dir = prepare_shared_env(config.skill_path, config.run_dir / "_env")
        base_env = shared_env_variables(env_dir)
    config.log.log(f"run {config.variant}: {len(cases)} case(s) to run, {len(done)} already done")
    gate = RateLimitGate(config.sleep)
    lock = threading.Lock()
    results: list[CaseResult] = []
    errors: list[ErrorRecord] = []

    def work(case: _Case) -> None:
        outcome = _run_case(case, config, gate, base_env)
        with lock:
            if isinstance(outcome, CaseResult):
                append_jsonl(config.run_dir / "results.jsonl", outcome)
                results.append(outcome)
            else:
                append_jsonl(config.run_dir / "errors.jsonl", outcome)
                errors.append(outcome)

    with ThreadPoolExecutor(max_workers=max(1, config.parallelism)) as pool:
        list(pool.map(work, cases))
    return RunResult(config.run_dir, results, errors, len(done))


def _select(scenarios: Sequence[Scenario], config: RunConfig) -> list[Scenario]:
    chosen = [
        s
        for s in scenarios
        if (not config.only or s.id in config.only)
        and (not config.tags or config.tags & set(s.tags))
    ]
    return sorted(chosen, key=lambda s: s.id)


def _done_keys(config: RunConfig) -> set[tuple[str, int]]:
    existing = read_jsonl(config.run_dir / "results.jsonl", CaseResult)
    return {(r.scenario_id, r.rep) for r in existing}


def _write_run_manifest(config: RunConfig, skill_name: str, n_scenarios: int) -> None:
    manifest = {
        "variant": config.variant,
        "skill_name": skill_name,
        "skill_path": str(config.skill_path.resolve()),
        "scenarios_path": str(config.scenarios_path.resolve()),
        "n_scenarios": n_scenarios,
        "reps": config.reps,
        "provider": config.provider.name,
        "requested_model": config.provider.model,
        "judge_model": None if config.judge is None else config.judge.model,
        "warm_cache": None if config.warm_cache is None else str(config.warm_cache),
        "started_at": datetime.now(UTC).isoformat(),
    }
    (config.run_dir / "run.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _run_case(
    case: _Case, config: RunConfig, gate: RateLimitGate, base_env: Mapping[str, str]
) -> CaseResult | ErrorRecord:
    """Run one case with rate-limit retries; never raises."""
    case_dir = config.run_dir / "cases" / case.scenario.id / f"rep-{case.rep}"
    for attempt in range(config.max_rate_limit_retries + 1):
        gate.wait()
        try:
            return _attempt(case, config, case_dir, base_env)
        except RateLimitedError as exc:
            pause = exc.retry_after_s or config.rate_limit_pause_s
            config.log.log(f"[yellow]{case.slug}: rate limited, pausing {pause:.0f}s[/]")
            gate.pause(pause)
            if attempt == config.max_rate_limit_retries:
                return _error(case, config, exc.failure_class, str(exc), case_dir)
        except ProviderError as exc:
            config.log.log(f"[red]{case.slug}: {exc.failure_class}: {exc}[/]")
            return _error(case, config, exc.failure_class, str(exc), case_dir)
        except Exception as exc:
            config.log.log(f"[red]{case.slug}: harness error: {exc}[/]")
            detail = f"{exc}\n{traceback.format_exc()}"
            return _error(case, config, "harness_error", detail, case_dir)
    msg = "unreachable: retry loop always returns"
    raise AssertionError(msg)


def _error(
    case: _Case, config: RunConfig, failure_class: str, message: str, case_dir: Path
) -> ErrorRecord:
    return ErrorRecord(
        scenario_id=case.scenario.id,
        rep=case.rep,
        variant=config.variant,
        failure_class=failure_class,
        message=message[:4000],
        case_dir=str(case_dir),
    )


def _attempt(
    case: _Case, config: RunConfig, case_dir: Path, base_env: Mapping[str, str]
) -> CaseResult:
    """One full attempt: sandbox, provider, artifacts, grading."""
    if case_dir.exists():
        shutil.rmtree(case_dir)
    case_dir.mkdir(parents=True)
    sandbox_dir = config.run_dir / "sandboxes" / case.slug
    if sandbox_dir.exists():
        shutil.rmtree(sandbox_dir)
    env = {**AGENT_SESSION_ENV, **base_env, **STAGE_ENV.get(case.scenario.stage, {})}
    if base_env:
        skill_dir = (
            sandbox_dir / ".claude" / "skills" / skill_name_from_frontmatter(config.skill_path)
        )
        env[CACHE_PATH_ENV] = str((skill_dir / ".cache" / "http.sqlite").resolve())
    sandbox = Sandbox.create(
        config.skill_path,
        sandbox_dir,
        warm_cache_from=config.warm_cache,
        env=env,
    )
    config.log.log(f"{case.slug}: running")
    trajectory = config.provider.run(case.scenario.turns, sandbox.root, case_dir / "events.jsonl")
    (case_dir / "trajectory.json").write_text(
        trajectory.model_dump_json(indent=2), encoding="utf-8"
    )
    collect_artifacts(sandbox, case_dir / "artifacts", config.artifact_globs)
    started = time.monotonic()
    grades = _grade(case.scenario, trajectory, case_dir, config)
    grading_s = time.monotonic() - started
    if not config.keep_sandboxes:
        sandbox.remove()
    result = _result(
        case=case,
        config=config,
        sandbox=sandbox,
        trajectory=trajectory,
        grades=grades,
        case_dir=case_dir,
        grading_s=grading_s,
    )
    (case_dir / "grades.json").write_text(
        json.dumps([g.model_dump() for g in grades], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    rate = result.pass_rate
    shown = "n/a" if rate is None else f"{rate:.0%}"
    config.log.log(f"{case.slug}: {result.status}, pass rate {shown}")
    return result


def collect_artifacts(sandbox: Sandbox, target: Path, globs: Sequence[str]) -> list[Path]:
    """Copy files matching ``globs`` from the sandbox (and the skill's ``runs/``) to ``target``.

    The skill copy itself is skipped except for its ``runs/`` directory, because the pipeline
    may write bundles either under the agent's cwd or next to the skill.
    """
    roots = [sandbox.root, sandbox.skill_dir / "runs"]
    copied: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in globs:
            for path in sorted(root.glob(pattern)):
                rel = path.relative_to(root)
                if not path.is_file() or (root == sandbox.root and _skipped(rel)):
                    continue
                dest = target / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                copied.append(dest)
    return copied


def _skipped(rel: Path) -> bool:
    return any(part in _ARTIFACT_SKIP_DIRS for part in rel.parts)


def _grade(
    scenario: Scenario, trajectory: Trajectory, case_dir: Path, config: RunConfig
) -> list[GradeRecord]:
    return grade_case(scenario, trajectory, case_dir, config.judge, config.reference_glob)


def grade_case(
    scenario: Scenario,
    trajectory: Trajectory,
    case_dir: Path,
    judge: Judge | None,
    reference_glob: str = "**/summary.md",
) -> list[GradeRecord]:
    """Grade one case from its trajectory and copied artifacts.

    Used by :func:`run` right after the agent finishes and by :func:`regrade` when graders
    change, so a grader fix never requires paying for new agent runs.
    """
    ctx = GradeContext(case_dir=case_dir / "artifacts", trajectory=trajectory)
    grades = [
        GradeRecord(
            id=f"a{i}",
            kind="deterministic",
            type=assertion.type,
            text=outcome.text,
            passed=outcome.passed,
            evidence=outcome.evidence,
        )
        for i, assertion in enumerate(scenario.assertions)
        for outcome in [grade(assertion, ctx)]
    ]
    if judge is not None and scenario.rubric:
        grades.extend(_judge(scenario, trajectory, ctx, judge, reference_glob))
    return grades


def latest_reference(ctx: GradeContext, reference_glob: str) -> str | None:
    """Text of the most recently written reference artifact, or ``None``.

    In a multi-turn scenario every turn writes its own ``summary.md``; the final answer
    relays the last one. Picking the first match by path (verified 2026-09-23) showed the
    judge the first turn's two-year summary while it graded a five-year answer, and the
    judge then called correct numbers invented. Artifacts are copied with their
    modification times, so the newest file is the last turn's.
    """
    references = ctx.files(reference_glob)
    if not references:
        return None
    newest = max(references, key=lambda path: (path.stat().st_mtime, str(path)))
    text = newest.read_text(encoding="utf-8-sig")
    facts = _facts_reference(newest.parent / FACTS_FILE)
    return f"{text}\n\n{facts}" if facts else text


def _facts_reference(path: Path) -> str | None:
    """The data part of the run's ``facts.json``, or ``None`` when there is none.

    The agent writes its answer from ``facts.json``, which holds more than ``summary.md``
    (every month that stands out, recent-months changes). With ``summary.md`` alone the judge
    called such figures invented (verified 2026-09-23), although the skill had already
    checked every number against ``facts.json``. Keys that only instruct the agent are left
    out to keep the judge's input short.
    """
    if not path.is_file():
        return None
    try:
        facts = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return None
    if not isinstance(facts, dict):
        return None
    data = {k: v for k, v in facts.items() if k not in _FACTS_INSTRUCTION_KEYS}
    body = json.dumps(data, ensure_ascii=False, indent=1)
    return f"facts.json (the data the answer is written from):\n{body}"


def _judge(
    scenario: Scenario,
    trajectory: Trajectory,
    ctx: GradeContext,
    judge: Judge,
    reference_glob: str,
) -> list[GradeRecord]:
    """One judge call per rubric item; the judge sees no variant name or path."""
    context = JudgeContext(
        turns=scenario.turns,
        answer=trajectory.final_answer,
        reference=latest_reference(ctx, reference_glob),
        earlier_answers=[t.final_answer for t in trajectory.turns[:-1]],
    )
    records: list[GradeRecord] = []
    for item in scenario.rubric:
        verdict = judge.judge(item.criterion, context)
        records.append(
            GradeRecord(
                id=item.id,
                kind="judge",
                type="rubric",
                text=item.criterion,
                passed=verdict.passed,
                evidence=verdict.evidence,
            )
        )
    return records


def regrade(
    run_dir: Path,
    scenarios_path: Path,
    judge: Judge | None,
    *,
    reference_glob: str = "**/summary.md",
) -> list[CaseResult]:
    """Re-grade every finished case of a run with the current graders and scenarios.

    Trajectories, artifacts, usage and timings are kept; only ``grades`` change. Without a
    judge, only deterministic grades are recomputed and earlier judge verdicts are kept for
    the rubric criteria the scenario still has. The previous ``results.jsonl`` is preserved
    as ``results.before-regrade.jsonl`` so the effect of a grader change stays auditable.

    Raises:
        KeyError: If a result refers to a scenario no longer in ``scenarios_path``.
    """
    scenarios = {s.id: s for s in load_scenarios(scenarios_path).scenarios}
    results_path = run_dir / "results.jsonl"
    previous = read_jsonl(results_path, CaseResult)
    updated: list[CaseResult] = []
    for result in previous:
        case_dir = Path(result.case_dir)
        trajectory = Trajectory.model_validate_json(
            (case_dir / "trajectory.json").read_text(encoding="utf-8")
        )
        grades = grade_case(
            scenarios[result.scenario_id], trajectory, case_dir, judge, reference_glob
        )
        if judge is None:
            # Deterministic-only regrade: keep the verdicts the judge already gave on the
            # criteria the scenario still has; a removed or renamed criterion drops its verdict.
            rubric = {item.id for item in scenarios[result.scenario_id].rubric}
            grades += [g for g in result.grades if g.kind == "judge" and g.id in rubric]
        (case_dir / "grades.json").write_text(
            json.dumps([g.model_dump() for g in grades], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        updated.append(result.model_copy(update={"grades": grades}))
    backup = run_dir / "results.before-regrade.jsonl"
    shutil.copyfile(results_path, backup)
    results_path.write_text("", encoding="utf-8")
    for record in updated:
        append_jsonl(results_path, record)
    return updated


def case_status(trajectory: Trajectory) -> CaseStatus:
    """Classify a completed trajectory: truncated by the turn budget, refused, or ok."""
    stop = (trajectory.stop_reason or "").lower()
    if stop in {"max_turns", "error_max_turns"}:
        return "truncated"
    if stop == "refusal":
        return "refused"
    return "ok"


def _result(  # noqa: PLR0913 - a record builder; every field is needed
    *,
    case: _Case,
    config: RunConfig,
    sandbox: Sandbox,
    trajectory: Trajectory,
    grades: list[GradeRecord],
    case_dir: Path,
    grading_s: float,
) -> CaseResult:
    return CaseResult(
        scenario_id=case.scenario.id,
        rep=case.rep,
        variant=config.variant,
        skill_hash=sandbox.skill_hash,
        provider=trajectory.provider,
        requested_model=trajectory.requested_model,
        served_models=trajectory.served_models,
        status=case_status(trajectory),
        grades=grades,
        usage=trajectory.usage,
        cost_usd=trajectory.cost_usd,
        num_turns=trajectory.num_turns,
        duration_s=trajectory.duration_s,
        grading_duration_s=grading_s,
        session_id=trajectory.session_id,
        case_dir=str(case_dir),
        final_answer=trajectory.final_answer,
    )
