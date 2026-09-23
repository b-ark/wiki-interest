"""The ``wiki-interest`` command-line application.

Every command prints one machine-readable JSON document on stdout (agents parse it) and
human progress or errors on stderr. Exit codes follow :mod:`wiki_interest.errors`; an
error document always carries ``error``, ``exit_code`` and ``hint``.
"""

from __future__ import annotations

import json
import secrets
import sys
import traceback
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from wiki_interest.application.runs import diff_runs, load_summary
from wiki_interest.application.summary_builder import RunContext
from wiki_interest.cli.container import Container
from wiki_interest.cli.doctor import run_doctor
from wiki_interest.contracts.narrative import Narrative
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.errors import RequestValidationError, WikiInterestError

__all__ = ["app", "main"]

app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Analyse Wikipedia pageview interest across topics and language editions.",
)

EXIT_PROBLEMS_FOUND = 1
EXIT_INTERNAL = 5
DEFAULT_SESSION = "default"
SCHEMA_HINT = "See references/request-schema.md and assets/examples/ for valid requests."
NARRATIVE_HINT = "Start from facts.json's template in the run directory; keep its fields."

build_container: Callable[[], Container] = Container.build
"""Factory for the composition root; tests replace it with one built on fakes."""


@app.callback()
def _root() -> None:
    """Analyse Wikipedia pageview interest across topics and language editions.

    Every command prints JSON on stdout; progress and errors go to stderr.
    """


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------


def _emit(payload: object) -> None:
    """Write one JSON document to stdout, always as UTF-8.

    On Windows a piped stdout uses the ANSI code page (cp1251, cp1252), which cannot encode
    characters the reports use, such as the narrow no-break space that separates thousands
    in Russian and Ukrainian numbers; the whole run then failed with exit code 5 after the
    files were already written.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(encoding="utf-8")
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n")


def _fail(error: str, exit_code: int, hint: str | None, **extra: object) -> None:
    _emit({"error": error, "exit_code": exit_code, "hint": hint, **extra})
    raise typer.Exit(code=exit_code)


@contextmanager
def _guarded() -> Iterator[None]:
    """Map every failure to an error document and the documented exit code."""
    try:
        yield
    except typer.Exit:
        raise
    except WikiInterestError as exc:
        _fail(str(exc), exc.exit_code, exc.hint)
    except FileNotFoundError as exc:
        _fail(f"File not found: {exc.filename}", RequestValidationError.exit_code, SCHEMA_HINT)
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        _fail(f"{type(exc).__name__}: {exc}", EXIT_INTERNAL, "Run scripts/doctor.py and report it")


def load_request(path: Path) -> AnalysisRequest:
    """Read and validate a request file.

    Raises:
        RequestValidationError: For unreadable JSON or a request that violates the schema.
    """
    # utf-8-sig: Windows PowerShell 5.1 writes UTF-8 *with* a byte-order mark by default, and
    # an agent that writes the request through it must not fail on an invisible character.
    text = path.read_text(encoding="utf-8-sig")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        msg = f"{path} is not valid JSON: {exc}"
        raise RequestValidationError(msg, hint=SCHEMA_HINT) from exc
    try:
        return AnalysisRequest.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        location = ".".join(str(part) for part in first["loc"]) or "request"
        msg = f"Invalid request at {location}: {first['msg']}"
        raise RequestValidationError(msg, hint=SCHEMA_HINT) from exc


def load_narrative(path: Path) -> Narrative:
    """Read the agent's report text.

    Raises:
        RequestValidationError: For unreadable JSON or a file that violates the schema.
    """
    text = path.read_text(encoding="utf-8-sig")
    try:
        return Narrative.model_validate_json(text)
    except ValidationError as exc:
        problems = [
            f"{'.'.join(str(p) for p in e['loc']) or 'narrative'}: {e['msg']}"
            for e in exc.errors()[:5]
        ]
        msg = f"{path} does not match the narrative schema: {'; '.join(problems)}"
        raise RequestValidationError(msg, hint=NARRATIVE_HINT) from exc


def new_run_context(runs_dir: Path, session: str | None) -> RunContext:
    """Allocate a run id and directory: ``<runs_dir>/<session>/<timestamp>-<random>``."""
    now = datetime.now(UTC)
    run_id = f"{now:%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    return RunContext(
        run_id=run_id,
        session=session,
        run_dir=runs_dir / (session or DEFAULT_SESSION) / run_id,
        generated_at=now,
    )


RunsDirOption = Annotated[
    Path | None,
    typer.Option("--runs-dir", help="Where run directories are written (default: <skill>/runs)."),
]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def run(
    request_file: Annotated[Path, typer.Argument(help="Path to request.json.")],
    runs_dir: RunsDirOption = None,
    session: Annotated[
        str | None, typer.Option("--session", help="Override the session slug of the request.")
    ] = None,
) -> None:
    """Run the full analysis and write a run directory (summary, charts, reports)."""
    with _guarded(), build_container() as container:
        request = load_request(request_file)
        if session is not None:
            request = request.model_copy(update={"session": session})
        context = new_run_context(runs_dir or container.settings.runs_dir, request.session)
        outcome = container.pipeline().run(request, context)
        _emit(outcome.to_dict())
        raise typer.Exit(code=outcome.exit_code)


@app.command()
def render(
    run_dir: Annotated[Path, typer.Argument(help="A run directory containing summary.json.")],
    narrative: Annotated[
        Path | None,
        typer.Option(
            "--narrative", help="The agent's report text (narrative.json) to check and render."
        ),
    ] = None,
) -> None:
    """Re-render charts and reports from a saved summary.json, or with the agent's text."""
    with _guarded(), build_container() as container:
        if narrative is not None:
            outcome = container.pipeline().narrate(run_dir, load_narrative(narrative))
            _emit(outcome.to_dict())
            raise typer.Exit(code=outcome.exit_code)
        summary = load_summary(run_dir)
        rendered = container.pipeline().render(summary, run_dir)
        artifacts = rendered.artifacts
        _emit(
            {
                "status": "ok",
                "exit_code": 0,
                "run_dir": artifacts.run_dir,
                "summary_md": artifacts.summary_md,
                "report_pdf": artifacts.report_pdf,
                "charts": list(artifacts.charts),
            }
        )


@app.command()
def diff(
    run_before: Annotated[Path, typer.Argument(help="Earlier run directory.")],
    run_after: Annotated[Path, typer.Argument(help="Later run directory.")],
) -> None:
    """Explain what changed between two runs (request, metrics, reliability, bundles)."""
    with _guarded():
        result = diff_runs(load_summary(run_before), load_summary(run_after))
        _emit({"status": "ok", "exit_code": 0, **result.to_dict()})


@app.command()
def doctor(
    offline: Annotated[
        bool, typer.Option("--offline", help="Skip the checks that contact Wikimedia services.")
    ] = False,
) -> None:
    """Check the environment: Python, cache directory, fonts and (unless offline) the APIs."""
    with _guarded(), build_container() as container:
        report = run_doctor(container, online=not offline)
        _emit(report.to_dict())
        raise typer.Exit(code=0 if report.ok else EXIT_PROBLEMS_FOUND)


def main() -> None:
    """Entry point used by ``scripts/*.py`` and the console script."""
    app()
