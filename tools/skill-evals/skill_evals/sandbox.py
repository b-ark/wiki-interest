"""Isolated working directory for one agent run.

Every case runs in a fresh directory that contains a private copy of the skill under
``.claude/skills/<name>/`` (the location headless Claude Code scans for project skills) and an
empty ``workspace/`` the agent works in. Isolation is what makes repetitions independent:
no shared HTTP cache, no leftover ``runs/`` from a previous case, no chance that one variant's
files leak into another's. The manifest records a content hash of the skill so a result can
always be traced back to the exact skill bytes that produced it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["DEFAULT_EXCLUDES", "Sandbox", "hash_directory", "skill_name_from_frontmatter"]

DEFAULT_EXCLUDES: frozenset[str] = frozenset(
    {
        ".venv",
        ".cache",
        "runs",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".hypothesis",
        ".git",
        "evals",
    }
)
"""Directory names never copied into a sandbox.

``.venv`` is machine-specific and not relocatable; ``.cache`` and ``runs`` are runtime output
(a warm cache is seeded explicitly); ``evals`` is the scenario set itself, which the agent under
test must not be able to read.
"""


def skill_name_from_frontmatter(skill_path: Path) -> str:
    """Return the ``name`` from ``SKILL.md`` frontmatter, falling back to the directory name.

    Claude Code identifies a skill by its frontmatter name, so the sandbox directory must use
    the same spelling for the ``Skill`` tool call to be recognisable.
    """
    text = (skill_path / "SKILL.md").read_text(encoding="utf-8-sig")
    if text.startswith("---"):
        for line in text.split("\n")[1:]:
            if line.strip() == "---":
                break
            key, _, value = line.partition(":")
            if key.strip() == "name" and value.strip():
                return value.strip().strip("'\"")
    return skill_path.name


def hash_directory(root: Path, excludes: Iterable[str] = DEFAULT_EXCLUDES) -> str:
    """Hash every file under ``root`` (relative path and bytes) in sorted order.

    Sorted traversal makes the hash independent of filesystem order, so two copies of the same
    skill always hash the same and any edit to any file changes the hash.
    """
    excluded = set(excludes)
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in excluded for part in rel.parts) or not path.is_file():
            continue
        digest.update(rel.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class Sandbox:
    """A prepared run directory.

    Attributes:
        root: The sandbox directory (the agent's ``cwd``).
        skill_dir: Where the skill copy lives inside the sandbox.
        workspace: Empty directory the agent is pointed at for its own files.
        skill_name: Name from the skill's frontmatter.
        skill_hash: Content hash of the copied skill.
    """

    root: Path
    skill_dir: Path
    workspace: Path
    skill_name: str
    skill_hash: str

    @classmethod
    def create(
        cls,
        skill_path: Path,
        base_dir: Path,
        *,
        warm_cache_from: Path | None = None,
        excludes: Iterable[str] = DEFAULT_EXCLUDES,
    ) -> Sandbox:
        """Copy the skill into a fresh sandbox under ``base_dir``.

        Args:
            skill_path: Directory containing ``SKILL.md``.
            base_dir: Directory to create; must not exist yet (a stale sandbox would break
                isolation, so reuse is refused rather than merged).
            warm_cache_from: Optional directory copied to ``<skill>/.cache`` so the pipeline
                finds its HTTP cache warm. Use it to separate network effects from model
                effects between two runs.
            excludes: Directory names not copied from the skill.

        Returns:
            The created sandbox.

        Raises:
            FileExistsError: If ``base_dir`` already exists.
            FileNotFoundError: If ``skill_path`` has no ``SKILL.md``.
        """
        if base_dir.exists():
            msg = f"sandbox directory already exists: {base_dir}"
            raise FileExistsError(msg)
        if not (skill_path / "SKILL.md").is_file():
            msg = f"no SKILL.md in {skill_path}"
            raise FileNotFoundError(msg)
        excluded = set(excludes)
        name = skill_name_from_frontmatter(skill_path)
        skill_dir = base_dir / ".claude" / "skills" / name
        shutil.copytree(skill_path, skill_dir, ignore=shutil.ignore_patterns(*excluded))
        workspace = base_dir / "workspace"
        workspace.mkdir()
        if warm_cache_from is not None:
            shutil.copytree(warm_cache_from, skill_dir / ".cache")
        skill_hash = hash_directory(skill_path, excluded)
        sandbox = cls(base_dir, skill_dir, workspace, name, skill_hash)
        sandbox._write_manifest(skill_path, warm_cache_from)
        return sandbox

    def _write_manifest(self, skill_path: Path, warm_cache_from: Path | None) -> None:
        """Record provenance next to the sandbox so trajectories stay explainable."""
        manifest = {
            "skill_source": str(skill_path.resolve()),
            "skill_name": self.skill_name,
            "skill_hash": self.skill_hash,
            "skill_md_hash": hashlib.sha256((skill_path / "SKILL.md").read_bytes()).hexdigest(),
            "warm_cache_from": None if warm_cache_from is None else str(warm_cache_from),
            "created_at": datetime.now(UTC).isoformat(),
        }
        (self.root / "sandbox-manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    def remove(self) -> None:
        """Delete the sandbox. Only called when the run is configured not to keep evidence."""
        shutil.rmtree(self.root, ignore_errors=True)
