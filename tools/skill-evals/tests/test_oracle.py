"""Oracle/null grader sanity check with a fake pipeline."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from skill_evals.oracle import (
    OracleReport,
    PipelineOutput,
    PipelineRunner,
    render_markdown,
    run_oracle,
)
from skill_evals.scenarios import Scenario

SUMMARY_MD = "**Answer:** interest grew by 25 % (1 250 views/month)."


def _scenario(**overrides: object) -> Scenario:
    data: dict[str, object] = {
        "id": "demo",
        "name": "demo",
        "turns": ["how is interest?"],
        "assertions": [
            {"type": "tool_called", "pattern": "run\\.py"},
            {"type": "file_exists", "glob": "**/summary.json"},
            {"type": "summary_field", "path": "status", "equals": "ok"},
            {"type": "no_tool_called", "pattern": "curl "},
            {"type": "answer_contains", "patterns": ["25"]},
        ],
    }
    data.update(overrides)
    return Scenario.model_validate(data)


def _fake_runner(status: str = "ok", exit_code: int = 0):  # type: ignore[no-untyped-def]
    def run(request_file: Path, runs_dir: Path, extra_env: Mapping[str, str]) -> PipelineOutput:
        run_dir = runs_dir / "s" / request_file.stem
        run_dir.mkdir(parents=True)
        (run_dir / "summary.md").write_text(SUMMARY_MD, encoding="utf-8")
        (run_dir / "summary.json").write_text(
            json.dumps({"status": status, "views": 1250.0, "growth": 0.25}), encoding="utf-8"
        )
        return PipelineOutput(
            exit_code, {"status": status, "summary_md": str(run_dir / "summary.md")}
        )

    return run


def _spec(tmp_path: Path, n: int = 1) -> Path:
    oracle_dir = tmp_path / "oracle"
    oracle_dir.mkdir()
    (oracle_dir / "demo.json").write_text(
        json.dumps({"requests": [{"question_type": "assess"}] * n}), encoding="utf-8"
    )
    return oracle_dir


def test_ideal_answer_passes_and_null_fails_work_requiring_assertions(tmp_path: Path) -> None:
    report = run_oracle([_scenario()], _spec(tmp_path), tmp_path / "out", _fake_runner())
    assert report.oracle_pass_rate == 1.0
    assert report.null_pass_rate == 0.0
    assert report.healthy
    checks = report.scenarios[0].checks
    assert [c.null_passed for c in checks] == [False, False, False, True, False]
    assert not checks[3].not_discriminating  # prohibitions pass for the null agent by design


def test_too_strict_assertion_is_reported(tmp_path: Path) -> None:
    scenario = _scenario(assertions=[{"type": "answer_contains", "patterns": ["99 %"]}])
    report = run_oracle([scenario], _spec(tmp_path), tmp_path / "out", _fake_runner())
    assert not report.healthy
    assert report.scenarios[0].checks[0].too_strict
    assert "oracle FAILS" in render_markdown(report)


def test_lenient_assertion_is_reported(tmp_path: Path) -> None:
    scenario = _scenario(assertions=[{"type": "answer_contains", "patterns": ["know"]}])
    report = run_oracle([scenario], _spec(tmp_path), tmp_path / "out", _fake_runner())
    assert report.scenarios[0].checks[0].not_discriminating
    assert "null PASSES" in render_markdown(report)


def test_clarification_oracle_asks_a_question(tmp_path: Path) -> None:
    scenario = _scenario(assertions=[{"type": "clarification_asked"}])
    report = run_oracle(
        [scenario], _spec(tmp_path), tmp_path / "out", _fake_runner("needs_clarification", 3)
    )
    assert report.scenarios[0].exit_codes == (3,)
    assert report.scenarios[0].checks[0].oracle_passed


def test_pipeline_failure_and_turn_mismatch_are_errors(tmp_path: Path) -> None:
    oracle_dir = _spec(tmp_path, n=2)
    report = run_oracle([_scenario()], oracle_dir, tmp_path / "out", _fake_runner())
    assert report.scenarios[0].error == "2 oracle requests for 1 turns"

    def broken(request_file: Path, runs_dir: Path, extra_env: Mapping[str, str]) -> PipelineOutput:
        return PipelineOutput(5, {"error": "boom"})

    two_turns = _scenario(turns=["a", "b"])
    report = run_oracle([two_turns], oracle_dir, tmp_path / "out2", broken)
    assert report.scenarios[0].error == "pipeline exit 5: boom"
    assert not report.healthy


def test_scenarios_without_spec_are_skipped_and_report_serialises(tmp_path: Path) -> None:
    report = run_oracle([_scenario(id="other")], _spec(tmp_path), tmp_path / "out", _fake_runner())
    assert report.skipped == ("other",)
    assert report.oracle_pass_rate is None
    assert json.loads(json.dumps(report.to_dict()))["skipped"] == ["other"]
    assert isinstance(report, OracleReport)


def test_resolve_stage_reaches_the_pipeline_as_environment(tmp_path: Path) -> None:
    seen: list[Mapping[str, str]] = []
    inner: PipelineRunner = _fake_runner()

    def spy(request_file: Path, runs_dir: Path, extra_env: Mapping[str, str]) -> PipelineOutput:
        seen.append(dict(extra_env))
        return inner(request_file, runs_dir, extra_env)

    oracle_dir = _spec(tmp_path, n=1)
    run_oracle([_scenario(stage="resolve")], oracle_dir, tmp_path / "out", spy)
    run_oracle([_scenario()], oracle_dir, tmp_path / "out2", spy)
    assert seen == [{"WIKI_INTEREST_STOP_AFTER": "resolve"}, {}]
