"""Report math on synthetic results: means, rep std, deltas, noise floor, error counts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_evals.providers.base import Usage
from skill_evals.records import CaseResult, ErrorRecord, GradeRecord, append_jsonl
from skill_evals.report import benchmark, noise_floor, render_markdown, write_report


def _grade(
    gid: str, passed: bool, kind: str = "deterministic", gtype: str = "max_turns"
) -> GradeRecord:
    return GradeRecord(id=gid, kind=kind, type=gtype, text=gid, passed=passed, evidence="e")


def _result(
    variant: str, scenario: str, rep: int, grades: list[GradeRecord], cost: float = 0.1
) -> CaseResult:
    return CaseResult(
        scenario_id=scenario,
        rep=rep,
        variant=variant,
        skill_hash="h" + variant,
        provider="fake",
        requested_model="haiku",
        served_models=["claude-haiku-4-5-20251001"],
        status="ok",
        grades=grades,
        usage=Usage(input_tokens=100, output_tokens=20, cache_read_tokens=50),
        cost_usd=cost,
        num_turns=4,
        duration_s=10.0,
        grading_duration_s=0.1,
        session_id=None,
        case_dir="x",
        final_answer="a",
    )


def _write_run(
    root: Path, variant: str, scores: dict[str, list[list[bool]]], errors: int = 0
) -> Path:
    """``scores[scenario][rep] = [passed per grade]``; grade 0 is deterministic, grade 1 judge."""
    run_dir = root / variant
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(json.dumps({"variant": variant, "reps": 2}), encoding="utf-8")
    for scenario, reps in scores.items():
        for rep_index, flags in enumerate(reps, start=1):
            grades = [_grade("a0", flags[0]), _grade("answers", flags[1], "judge", "rubric")]
            append_jsonl(run_dir / "results.jsonl", _result(variant, scenario, rep_index, grades))
    for i in range(errors):
        append_jsonl(
            run_dir / "errors.jsonl",
            ErrorRecord(
                scenario_id=f"s{i}", rep=1, variant=variant, failure_class="timeout", message="m"
            ),
        )
    return run_dir


def test_noise_floor_formula() -> None:
    assert noise_floor(4, 4) == pytest.approx(0.25)
    assert noise_floor(0, 3) is None


def test_variant_stats_means_and_std(tmp_path: Path) -> None:
    run_dir = _write_run(
        tmp_path,
        "base",
        {"s1": [[True, True], [True, False]], "s2": [[False, False], [True, True]]},
        errors=1,
    )
    report = benchmark([run_dir])
    v = report.variants[0]
    assert v.variant == "base"
    assert (v.n_scenarios, v.reps, v.n_results) == (2, 2, 4)
    assert v.per_scenario == {"s1": pytest.approx(0.75), "s2": pytest.approx(0.5)}
    assert v.pass_rate_mean == pytest.approx(0.625)
    # rep 1 mean = (1.0 + 0.0)/2 = 0.5 ; rep 2 mean = (0.5 + 1.0)/2 = 0.75 -> sample std
    assert v.pass_rate_std == pytest.approx(0.1767767, abs=1e-6)
    assert v.per_assertion == {"max_turns": pytest.approx(0.75)}
    assert v.per_rubric == {"answers": pytest.approx(0.5)}
    assert v.deterministic_pass_rate == pytest.approx(0.75)
    assert v.judge_pass_rate == pytest.approx(0.5)
    assert v.errors_by_class == {"timeout": 1}
    assert v.mean_input_tokens == pytest.approx(150.0)
    assert v.mean_cost_usd == pytest.approx(0.1)
    assert v.noise_floor == pytest.approx(0.5)
    assert any("could not be measured" in n for n in report.notes)


def test_pairwise_delta_and_disagreements(tmp_path: Path) -> None:
    base = _write_run(
        tmp_path,
        "base",
        {
            "s1": [[True, True], [True, True]],
            "s2": [[False, False], [False, False]],
            "s3": [[True, False], [True, False]],
        },
    )
    other = _write_run(
        tmp_path,
        "other",
        {
            "s1": [[True, True], [True, True]],
            "s2": [[True, True], [True, True]],
            "s3": [[True, False], [True, False]],
        },
    )
    report = benchmark([base, other])
    (pair,) = report.pairwise
    assert (pair.base, pair.other) == ("base", "other")
    assert pair.n_common_scenarios == 3
    assert pair.delta_overall == pytest.approx(1 / 3)
    assert pair.noise_floor == pytest.approx(1 / (6**0.5))
    assert [d.scenario_id for d in pair.disagreements] == ["s2"]
    assert pair.disagreements[0].delta == pytest.approx(1.0)
    assert not pair.significant
    assert any("within the noise floor" in n for n in report.notes)


def test_significant_delta_when_beyond_floor(tmp_path: Path) -> None:
    scores_bad = {f"s{i}": [[False, False], [False, False]] for i in range(10)}
    scores_good = {f"s{i}": [[True, True], [True, True]] for i in range(10)}
    report = benchmark(
        [_write_run(tmp_path, "a", scores_bad), _write_run(tmp_path, "b", scores_good)]
    )
    assert report.pairwise[0].significant
    assert report.pairwise[0].delta_overall == pytest.approx(1.0)


def test_markdown_and_json_written(tmp_path: Path) -> None:
    base = _write_run(tmp_path, "base", {"s1": [[True, True]]})
    other = _write_run(tmp_path, "other", {"s1": [[False, True]]})
    report = benchmark([base, other])
    md, js = write_report(report, tmp_path / "out")
    text = md.read_text(encoding="utf-8")
    assert "## Variants" in text
    assert "| base |" in text
    assert "| other |" in text
    assert "## other vs base" in text
    assert "| s1 |" in text
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["variants"][0]["variant"] == "base"
    assert data["pairwise"][0]["per_scenario"][0]["delta"] == pytest.approx(-0.5)


def test_empty_run_dir_is_handled(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    report = benchmark([empty])
    v = report.variants[0]
    assert v.n_results == 0
    assert v.pass_rate_mean is None
    assert "n/a" in render_markdown(report)
