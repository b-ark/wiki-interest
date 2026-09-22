"""Check that this environment can run analyses.

Usage:
    uv run scripts/doctor.py            # full check, including network probes
    uv run scripts/doctor.py --offline  # local checks only

Prints a JSON report to stdout; exit code 0 means everything passed.
"""

import sys

from wiki_interest.cli.app import app

if __name__ == "__main__":
    sys.exit(app(["doctor", *sys.argv[1:]]))
