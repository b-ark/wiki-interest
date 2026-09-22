"""Sandbox: skill copied to the discovery path, junk excluded, cache seeded, manifest written."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skill_evals.sandbox import Sandbox, hash_directory, skill_name_from_frontmatter


def test_create_copies_skill_to_claude_skills_dir(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    assert sandbox.skill_dir == tmp_path / "sb" / ".claude" / "skills" / "demo-skill"
    assert (sandbox.skill_dir / "SKILL.md").is_file()
    assert (sandbox.skill_dir / "scripts" / "run.py").is_file()
    assert sandbox.workspace.is_dir()
    assert not any(sandbox.workspace.iterdir())


def test_create_excludes_venv_cache_and_evals(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    assert not (sandbox.skill_dir / ".venv").exists()
    assert not (sandbox.skill_dir / ".cache").exists()
    assert not (sandbox.skill_dir / "evals").exists()


def test_warm_cache_is_seeded(skill_dir: Path, tmp_path: Path) -> None:
    warm = tmp_path / "warm"
    warm.mkdir()
    (warm / "http.sqlite").write_bytes(b"warm")
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb", warm_cache_from=warm)
    assert (sandbox.skill_dir / ".cache" / "http.sqlite").read_bytes() == b"warm"


def test_manifest_records_hashes(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    manifest = json.loads((sandbox.root / "sandbox-manifest.json").read_text(encoding="utf-8"))
    assert manifest["skill_name"] == "demo-skill"
    assert manifest["skill_hash"] == sandbox.skill_hash
    assert len(manifest["skill_md_hash"]) == 64
    assert manifest["warm_cache_from"] is None


def test_hash_changes_when_skill_md_changes(skill_dir: Path) -> None:
    before = hash_directory(skill_dir)
    (skill_dir / "SKILL.md").write_text("changed", encoding="utf-8")
    assert hash_directory(skill_dir) != before


def test_hash_ignores_excluded_dirs(skill_dir: Path) -> None:
    before = hash_directory(skill_dir)
    (skill_dir / ".cache" / "new.sqlite").write_bytes(b"irrelevant")
    assert hash_directory(skill_dir) == before


def test_existing_sandbox_dir_is_refused(skill_dir: Path, tmp_path: Path) -> None:
    (tmp_path / "sb").mkdir()
    with pytest.raises(FileExistsError):
        Sandbox.create(skill_dir, tmp_path / "sb")


def test_missing_skill_md_is_refused(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    with pytest.raises(FileNotFoundError):
        Sandbox.create(tmp_path / "empty", tmp_path / "sb")


def test_skill_name_falls_back_to_directory_name(tmp_path: Path) -> None:
    root = tmp_path / "fallback-name"
    root.mkdir()
    (root / "SKILL.md").write_text("# no frontmatter", encoding="utf-8")
    assert skill_name_from_frontmatter(root) == "fallback-name"


def test_remove_deletes_sandbox(skill_dir: Path, tmp_path: Path) -> None:
    sandbox = Sandbox.create(skill_dir, tmp_path / "sb")
    sandbox.remove()
    assert not sandbox.root.exists()
