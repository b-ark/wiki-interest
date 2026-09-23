"""One Python environment for every sandbox of a run.

Each sandbox is a fresh copy of the skill, so the first ``uv run`` inside it builds the
skill's environment from scratch. That takes about ten seconds alone, but fifty sandboxes
building at once took more than two minutes (verified 2026-09-23), and Claude Code moves a
command that runs longer than two minutes to the background. In ``claude -p`` the agent then
ends its turn with "waiting for results" and the case measures the machine's load, not the
skill.

With a shared environment the harness syncs the skill's locked dependencies once, before the
cases start, and every sandbox runs against it without syncing. The skill's first-run setup
is then not part of the measurement; use ``--own-env`` when that is what you want to test.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

__all__ = ["SharedEnvError", "prepare_shared_env", "shared_env_variables"]

UV_ENV_VAR = "UV_PROJECT_ENVIRONMENT"
UV_NO_SYNC_VAR = "UV_NO_SYNC"


class SharedEnvError(RuntimeError):
    """The shared environment could not be built."""


def prepare_shared_env(skill_path: Path, env_dir: Path, *, timeout_s: int = 900) -> Path:
    """Sync the skill's locked dependencies into ``env_dir`` and return it.

    Args:
        skill_path: Skill directory with ``pyproject.toml`` and ``uv.lock``.
        env_dir: Where the environment lives; reused (and re-checked) on resume.
        timeout_s: Upper bound for the sync.

    Raises:
        SharedEnvError: If ``uv`` is missing or the sync fails.
    """
    uv = shutil.which("uv")
    if uv is None:
        msg = "uv is not on PATH; it is needed to build the shared environment"
        raise SharedEnvError(msg)
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}
    env[UV_ENV_VAR] = str(env_dir.resolve())
    completed = subprocess.run(
        [uv, "sync", "--frozen", "--project", str(skill_path.resolve())],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        timeout=timeout_s,
        check=False,
    )
    if completed.returncode != 0:
        msg = f"uv sync failed ({completed.returncode}): {completed.stderr[-1000:]}"
        raise SharedEnvError(msg)
    return env_dir.resolve()


def shared_env_variables(env_dir: Path) -> dict[str, str]:
    """Variables that make ``uv run`` in a sandbox use ``env_dir`` as it is."""
    return {UV_ENV_VAR: str(env_dir), UV_NO_SYNC_VAR: "1"}
