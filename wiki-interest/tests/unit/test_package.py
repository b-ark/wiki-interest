"""Smoke tests for package metadata and layout."""

import importlib
import tomllib
from pathlib import Path

import pytest

import wiki_interest

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
LAYERS = ["domain", "contracts", "ports", "application", "adapters", "cli"]


def test_version_matches_pyproject() -> None:
    """The package version is the single source of truth and must match the build metadata."""
    project_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    assert wiki_interest.__version__ == project_version


@pytest.mark.parametrize("layer", LAYERS)
def test_layer_package_imports_cleanly(layer: str) -> None:
    """Every architectural layer exists as an importable package with a module docstring."""
    module = importlib.import_module(f"wiki_interest.{layer}")
    assert module.__doc__, f"wiki_interest.{layer} must document its role"
