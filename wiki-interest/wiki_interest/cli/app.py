"""The ``wiki-interest`` command-line application.

Every command prints a machine-readable JSON document on stdout (agents parse it) and human
progress or errors on stderr. Exit codes follow :mod:`wiki_interest.errors`.
"""

from __future__ import annotations

import json
import sys
from typing import Annotated

import typer

from wiki_interest.cli.container import Container
from wiki_interest.cli.doctor import run_doctor

__all__ = ["app", "main"]

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Analyse Wikipedia pageview interest across topics and language editions.",
)

EXIT_PROBLEMS_FOUND = 1


@app.callback()
def _root() -> None:
    """Analyse Wikipedia pageview interest across topics and language editions.

    Every command prints JSON on stdout; progress and errors go to stderr.
    """


def _emit(payload: object) -> None:
    """Write one JSON document to stdout."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


@app.command()
def doctor(
    offline: Annotated[
        bool, typer.Option("--offline", help="Skip the checks that contact Wikimedia services.")
    ] = False,
) -> None:
    """Check the environment: Python, cache directory, fonts and (unless offline) the APIs."""
    with Container.build(persistent_cache=False) as container:
        report = run_doctor(container, online=not offline)
    _emit(report.to_dict())
    raise typer.Exit(code=0 if report.ok else EXIT_PROBLEMS_FOUND)


def main() -> None:
    """Entry point used by ``scripts/*.py`` and the console script."""
    app()
