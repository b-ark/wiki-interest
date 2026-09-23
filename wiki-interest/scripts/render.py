"""Render a saved run: with the agent's report text, or again from its summary.json.

Usage:
    uv run scripts/render.py runs/<session>/<run-id> --narrative narrative.json
    uv run scripts/render.py runs/<session>/<run-id>

With ``--narrative`` the text is checked against the run's facts.json first. Accepted: the
PDF and reports are rebuilt with it and stdout carries ``chat_answer`` (exit 0). Rejected:
stdout lists ``problems`` (exit 2); fix them and render again. A second rejection keeps the
template text (``status: fallback``, exit 0).

Without it, the reports are rebuilt from summary.json; no network access is needed.
"""

import sys

from wiki_interest.cli.app import app

if __name__ == "__main__":
    sys.exit(app(["render", *sys.argv[1:]]))
