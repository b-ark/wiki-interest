"""Run the full analysis pipeline, or inspect past runs.

Usage:
    uv run scripts/run.py request.json               # analyse -> runs/<session>/<run-id>/
    uv run scripts/run.py request.json --session s1  # override the session slug
    uv run scripts/run.py --list-runs [session]      # list past runs, newest first
    uv run scripts/run.py --diff <run-a> <run-b>     # what changed between two runs

Prints one JSON document to stdout. Exit codes: 0 ok, 2 invalid request, 3 clarification
needed, 4 upstream failure, 5 internal error (see SKILL.md).
"""

import sys

from wiki_interest.cli.app import app

_ALIASES = {"--list-runs": "runs", "--diff": "diff"}

if __name__ == "__main__":
    argv = sys.argv[1:]
    command = _ALIASES.get(argv[0], "run") if argv else "run"
    rest = argv[1:] if argv and argv[0] in _ALIASES else argv
    sys.exit(app([command, *rest]))
