"""Smoke tests for package metadata."""

import tomllib
from pathlib import Path

import skill_evals

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_matches_pyproject() -> None:
    project_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert skill_evals.__version__ == project_version
