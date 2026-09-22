"""CLI: the offline commands work end to end through typer."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from skill_evals.cli import app
from tests.test_scenarios import VALID

runner = CliRunner()


def test_validate_scenarios_ok(tmp_path: Path) -> None:
    path = tmp_path / "evals.json"
    path.write_text(json.dumps(VALID), encoding="utf-8")
    result = runner.invoke(app, ["validate-scenarios", str(path)])
    assert result.exit_code == 0, result.output


def test_validate_scenarios_bad(tmp_path: Path) -> None:
    path = tmp_path / "evals.json"
    path.write_text('{"skill_name": "x", "scenarios": []}', encoding="utf-8")
    result = runner.invoke(app, ["validate-scenarios", str(path)])
    assert result.exit_code == 1


def test_compare_writes_benchmark(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    result = runner.invoke(app, ["compare", str(tmp_path / "a"), "--out", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "out" / "benchmark.md").exists()
    assert (tmp_path / "out" / "benchmark.json").exists()


def test_run_rejects_unknown_provider(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["run", "-s", "x.json", "-k", str(tmp_path), "-n", "r", "--provider", "nope", "--no-judge"],
    )
    assert result.exit_code != 0
