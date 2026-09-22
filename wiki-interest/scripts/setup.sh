#!/usr/bin/env bash
# Prepare a reproducible environment for the wiki-interest skill.
#
# Installs uv if it is missing, then syncs the locked dependencies (runtime only).
# Safe to run repeatedly. Usage: ./scripts/setup.sh [--dev]
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing it with the official installer (https://astral.sh/uv)..." >&2
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

if [[ "${1:-}" == "--dev" ]]; then
  uv sync
else
  uv sync --no-dev
fi

echo "Environment ready. Try: uv run scripts/run.py --help"
