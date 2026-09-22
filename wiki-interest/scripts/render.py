"""Re-render the charts and reports of a saved run from its summary.json.

Usage:
    uv run scripts/render.py runs/<session>/<run-id>

No network access is needed; use it after a report-template change or to regenerate a
deleted PDF.
"""

import sys

from wiki_interest.cli.app import app

if __name__ == "__main__":
    sys.exit(app(["render", *sys.argv[1:]]))
