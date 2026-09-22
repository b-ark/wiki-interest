"""Resolve the topics of a request to article bundles without fetching pageviews.

Usage:
    uv run scripts/resolve.py request.json

Useful to check which articles a topic maps to in each edition before running the full
analysis, or to inspect candidates after a clarification (exit code 3).
"""

import sys

from wiki_interest.cli.app import app

if __name__ == "__main__":
    sys.exit(app(["resolve", *sys.argv[1:]]))
