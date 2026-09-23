"""Runner: results/errors split, resume, artifacts, judge wiring, rate-limit pause."""

from __future__ import annotations

import json
import os
from pathlib import Path

from rich.console import Console

from skill_evals.graders.deterministic import GradeContext
from skill_evals.graders.judge import JudgeContext, JudgeVerdict
from skill_evals.providers.base import (
    ModelMismatchError,
    ProviderTimeoutError,
    RateLimitedError,
    ToolCall,
    Trajectory,
)
from skill_evals.records import CaseResult, ErrorRecord, read_jsonl
from skill_evals.runner import RateLimitGate, RunConfig, case_status, latest_reference, regrade, run
from tests.conftest import FakeProvider, make_summary, make_trajectory, write_summary

SCENARIOS = {
    "skill_name": "demo-skill",
    "scenarios": [
        {
            "id": "b-second",
            "name": "second",
            "turns": ["second prompt"],
            "assertions": [{"type": "max_turns", "n": 5}],
        },
        {
            "id": "a-first",
            "name": "first",
            "tags": ["core"],
            "turns": ["first prompt", "follow-up"],
            "assertions": [
                {"type": "tool_called", "pattern": "run\\.py"},
                {"type": "file_exists", "glob": "**/summary.json"},
                {"type": "numbers_grounded"},
            ],
            "rubric": [{"id": "answers", "criterion": "Answers."}],
        },
    ],
}


def _write_scenarios(tmp_path: Path) -> Path:
    path = tmp_path / "evals.json"
    path.write_text(json.dumps(SCENARIOS), encoding="utf-8")
    return path


def _good_first(workdir: Path) -> Trajectory:
    """Simulates the agent running the pipeline and writing a bundle into the workspace."""
    write_summary(workdir / "workspace" / "runs" / "s" / "r1", make_summary())
    (workdir / "workspace" / "runs" / "s" / "r1" / "summary.md").write_text("ref", encoding="utf-8")
    call = ToolCall(
        name="Bash", input={"command": "python scripts/run.py"}, command="python scripts/run.py"
    )
    return make_trajectory(
        "Growth 23.4 % with 1 234 views", tool_calls=[call], prompts=("first prompt", "follow-up")
    )


class StubJudge:
    model = "sonnet"

    def __init__(self) -> None:
        self.contexts: list[JudgeContext] = []

    def judge(self, criterion: str, context: JudgeContext) -> JudgeVerdict:
        self.contexts.append(context)
        return JudgeVerdict(passed=True, evidence=f"ok: {criterion}")


def _config(
    tmp_path: Path, skill_dir: Path, provider: FakeProvider, **overrides: object
) -> RunConfig:
    base: dict[str, object] = {
        "scenarios_path": _write_scenarios(tmp_path),
        "skill_path": skill_dir,
        "provider": provider,
        "run_dir": tmp_path / "runs" / "v1",
        "variant": "v1",
        "reps": 2,
        "parallelism": 1,
        "sleep": lambda _: None,
        "log": Console(quiet=True),
    }
    base.update(overrides)
    return RunConfig(**base)  # type: ignore[arg-type]


def test_run_writes_results_in_deterministic_order_with_artifacts(
    tmp_path: Path, skill_dir: Path
) -> None:
    provider = FakeProvider({"first prompt": _good_first})
    judge = StubJudge()
    result = run(_config(tmp_path, skill_dir, provider, judge=judge))
    assert [r.scenario_id for r in result.results] == ["a-first", "a-first", "b-second", "b-second"]
    assert [r.rep for r in result.results] == [1, 2, 1, 2]
    assert result.errors == []
    first = result.results[0]
    assert first.status == "ok"
    assert first.pass_rate == 1.0
    assert [g.kind for g in first.grades] == ["deterministic"] * 3 + ["judge"]
    assert first.served_models == ["claude-haiku-4-5-20251001"]
    assert first.skill_hash
    case_dir = Path(first.case_dir)
    assert (case_dir / "trajectory.json").exists()
    assert (case_dir / "events.jsonl").exists()
    assert (case_dir / "grades.json").exists()
    assert (case_dir / "artifacts" / "workspace" / "runs" / "s" / "r1" / "summary.json").exists()
    assert judge.contexts[0].reference == "ref"
    assert list(judge.contexts[0].turns) == ["first prompt", "follow-up"]
    assert list(judge.contexts[0].earlier_answers) == ["intermediate"]
    written = read_jsonl(result.run_dir / "results.jsonl", CaseResult)
    assert len(written) == 4
    assert json.loads((result.run_dir / "run.json").read_text(encoding="utf-8"))["variant"] == "v1"
    assert (
        result.run_dir / "sandboxes" / "a-first-rep-1" / ".claude" / "skills" / "demo-skill"
    ).is_dir()


def test_provider_calls_get_fresh_sandbox_and_all_turns(tmp_path: Path, skill_dir: Path) -> None:
    provider = FakeProvider({"first prompt": _good_first})
    run(_config(tmp_path, skill_dir, provider))
    assert len(provider.calls) == 4
    turns, workdir = provider.calls[0]
    assert turns == ["first prompt", "follow-up"]
    assert (workdir / ".claude" / "skills" / "demo-skill" / "SKILL.md").exists()
    assert len({str(w) for _, w in provider.calls}) == 4


def test_infra_errors_go_to_errors_not_results(tmp_path: Path, skill_dir: Path) -> None:
    provider = FakeProvider(
        {
            "first prompt": ProviderTimeoutError("too slow"),
            "second prompt": ModelMismatchError("wrong"),
        }
    )
    result = run(_config(tmp_path, skill_dir, provider))
    assert result.results == []
    classes = sorted(e.failure_class for e in result.errors)
    assert classes == ["model_mismatch", "model_mismatch", "timeout", "timeout"]
    assert not (result.run_dir / "results.jsonl").exists()
    assert len(read_jsonl(result.run_dir / "errors.jsonl", ErrorRecord)) == 4


def test_harness_crash_is_recorded_not_raised(tmp_path: Path, skill_dir: Path) -> None:
    def explode(workdir: Path) -> Trajectory:
        raise RuntimeError("bug in fake")

    provider = FakeProvider({"first prompt": explode})
    result = run(_config(tmp_path, skill_dir, provider, only=frozenset({"a-first"})))
    assert result.results == []
    assert {e.failure_class for e in result.errors} == {"harness_error"}
    assert "bug in fake" in result.errors[0].message


def test_resume_skips_done_cases(tmp_path: Path, skill_dir: Path) -> None:
    provider = FakeProvider({"first prompt": _good_first})
    first = run(_config(tmp_path, skill_dir, provider, only=frozenset({"a-first"})))
    assert len(first.results) == 2
    second = run(_config(tmp_path, skill_dir, provider))
    assert second.skipped == 2
    assert [r.scenario_id for r in second.results] == ["b-second", "b-second"]
    assert len(read_jsonl(second.run_dir / "results.jsonl", CaseResult)) == 4
    third = run(_config(tmp_path, skill_dir, provider, resume=False))
    assert third.skipped == 0
    assert len(read_jsonl(third.run_dir / "results.jsonl", CaseResult)) == 8


def test_tags_filter(tmp_path: Path, skill_dir: Path) -> None:
    provider = FakeProvider({"first prompt": _good_first})
    result = run(_config(tmp_path, skill_dir, provider, tags=frozenset({"core"}), reps=1))
    assert [r.scenario_id for r in result.results] == ["a-first"]


def test_rate_limit_pauses_and_retries_then_records_error(tmp_path: Path, skill_dir: Path) -> None:
    attempts: list[int] = []

    def limited(workdir: Path) -> Trajectory:
        attempts.append(1)
        if len(attempts) < 3:
            raise RateLimitedError("quota", retry_after_s=0.01)
        return _good_first(workdir)

    provider = FakeProvider({"first prompt": limited, "second prompt": RateLimitedError("quota")})
    slept: list[float] = []
    config = _config(
        tmp_path,
        skill_dir,
        provider,
        reps=1,
        max_rate_limit_retries=2,
        rate_limit_pause_s=0.01,
        sleep=slept.append,
    )
    result = run(config)
    assert [r.scenario_id for r in result.results] == ["a-first"]
    assert [e.failure_class for e in result.errors] == ["rate_limited"]
    assert slept


def test_case_status_from_stop_reason() -> None:
    assert case_status(make_trajectory("x", stop_reason="max_turns")) == "truncated"
    assert case_status(make_trajectory("x", stop_reason="refusal")) == "refused"
    assert case_status(make_trajectory("x", stop_reason="end_turn")) == "ok"


def test_delete_sandboxes_option(tmp_path: Path, skill_dir: Path) -> None:
    provider = FakeProvider({"first prompt": _good_first})
    result = run(_config(tmp_path, skill_dir, provider, reps=1, keep_sandboxes=False))
    assert not (result.run_dir / "sandboxes" / "a-first-rep-1").exists()


def test_gate_waits_until_pause_elapses() -> None:
    slept: list[float] = []
    gate = RateLimitGate(sleep=slept.append)
    gate.wait()
    assert slept == []
    gate.pause(0.0)
    gate.wait()
    assert slept == []


def test_latest_reference_is_the_newest_summary(tmp_path: Path) -> None:
    first = tmp_path / "runs" / "s" / "b-first" / "summary.md"
    second = tmp_path / "runs" / "s" / "a-second" / "summary.md"
    for path, text, mtime in ((first, "two years", 1_000), (second, "five years", 2_000)):
        path.parent.mkdir(parents=True)
        path.write_text(text, encoding="utf-8")
        os.utime(path, (mtime, mtime))
    ctx = GradeContext(case_dir=tmp_path, trajectory=make_trajectory("x"))
    assert latest_reference(ctx, "**/summary.md") == "five years"
    assert latest_reference(ctx, "**/nothing.md") is None


def test_latest_reference_adds_the_data_of_the_same_runs_facts(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs" / "s" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "summary.md").write_text("summary", encoding="utf-8")
    facts = {"pairs": [{"display": "-0,5 %"}], "rules": ["write short"], "ui_strings": {}}
    (run_dir / "facts.json").write_text(json.dumps(facts), encoding="utf-8")
    ctx = GradeContext(case_dir=tmp_path, trajectory=make_trajectory("x"))
    reference = latest_reference(ctx, "**/summary.md")
    assert reference is not None
    assert reference.startswith("summary\n\nfacts.json")
    assert "-0,5 %" in reference
    assert "write short" not in reference


def test_regrade_rewrites_grades_and_keeps_a_backup(tmp_path: Path, skill_dir: Path) -> None:
    provider = FakeProvider({"first prompt": _good_first})
    config = _config(tmp_path, skill_dir, provider)
    run(config)
    judge = StubJudge()
    updated = regrade(config.run_dir, config.scenarios_path, judge)
    assert len(updated) == 4
    assert any(g.kind == "judge" for g in updated[0].grades)
    assert (config.run_dir / "results.before-regrade.jsonl").exists()
    reread = read_jsonl(config.run_dir / "results.jsonl", CaseResult)
    assert [r.grades for r in reread] == [r.grades for r in updated]
    assert reread[0].cost_usd == updated[0].cost_usd


def test_regrade_without_judge_drops_verdicts_of_removed_criteria(
    tmp_path: Path, skill_dir: Path
) -> None:
    provider = FakeProvider({"first prompt": _good_first})
    config = _config(tmp_path, skill_dir, provider, judge=StubJudge())
    run(config)
    renamed = json.loads(config.scenarios_path.read_text(encoding="utf-8"))
    renamed["scenarios"][1]["rubric"] = [{"id": "relays", "criterion": "Relays."}]
    config.scenarios_path.write_text(json.dumps(renamed), encoding="utf-8")
    updated = regrade(config.run_dir, config.scenarios_path, None)
    assert not [g for r in updated for g in r.grades if g.kind == "judge"]
