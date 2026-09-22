"""Command-line entry point ``skill-evals``.

Commands are thin: parse options, build the provider and config, call the module that does
the work, print where the output went. All logic lives in the modules so it is testable
without a terminal.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from skill_evals.graders.judge import ClaudeCliJudge, Judge
from skill_evals.oracle import render_markdown as render_oracle_markdown
from skill_evals.oracle import run_oracle, uv_pipeline_runner
from skill_evals.providers.base import ModelProvider
from skill_evals.providers.claude_cli import (
    DEFAULT_ALLOWED_TOOLS,
    ClaudeCliProvider,
    expected_model_prefix,
    locate_claude_binary,
)
from skill_evals.providers.openrouter import OpenRouterProvider
from skill_evals.report import benchmark, write_report
from skill_evals.runner import RunConfig, run
from skill_evals.scenarios import ScenarioLoadError, load_scenarios
from skill_evals.trigger import TriggerConfig, run_trigger

__all__ = ["app"]

app = typer.Typer(
    help="Evaluate an Agent Skill with a real agent, grade the results, compare versions.",
    no_args_is_help=True,
    pretty_exceptions_enable=False,
)
_console = Console(stderr=True)
_DEFAULT_RUNS_ROOT = Path("runs")


def _make_provider(
    provider: str, model: str | None, max_turns: int, timeout_s: int, allowed_tools: str | None
) -> ModelProvider:
    if provider == "claude":
        tools = allowed_tools.split(",") if allowed_tools else list(DEFAULT_ALLOWED_TOOLS)
        return ClaudeCliProvider(
            model=model or "haiku",
            max_turns=max_turns,
            timeout_s=timeout_s,
            allowed_tools=tools,
        )
    if provider == "openrouter":
        if not model:
            raise typer.BadParameter("--model is required for the openrouter provider")
        return OpenRouterProvider(model, max_turns=max_turns, timeout_s=timeout_s)
    raise typer.BadParameter(f"unknown provider {provider!r}; use claude or openrouter")


@app.command("validate-scenarios")
def validate_scenarios(
    scenarios: Annotated[Path, typer.Argument(help="Path to evals.json")],
) -> None:
    """Validate evals.json against the schema and list the scenarios."""
    try:
        loaded = load_scenarios(scenarios)
    except ScenarioLoadError as exc:
        _console.print(f"[red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    for s in loaded.scenarios:
        _console.print(
            f"{s.id}: {len(s.turns)} turn(s), {len(s.assertions)} assertion(s), "
            f"{len(s.rubric)} rubric item(s), tags={s.tags}"
        )
    _console.print(
        f"[green]{len(loaded.scenarios)} scenario(s) valid for skill {loaded.skill_name!r}[/]"
    )


@app.command("run")
def run_command(
    scenarios: Annotated[Path, typer.Option("--scenarios", "-s", help="Path to evals.json")],
    skill: Annotated[Path, typer.Option("--skill", "-k", help="Skill directory (variant)")],
    name: Annotated[
        str, typer.Option("--name", "-n", help="Run name; output goes to runs/<name>/")
    ],
    variant: Annotated[
        str | None, typer.Option(help="Variant label in reports (default: name)")
    ] = None,
    provider: Annotated[str, typer.Option(help="claude | openrouter")] = "claude",
    model: Annotated[str | None, typer.Option(help="Model alias/id (claude: haiku)")] = None,
    reps: Annotated[int, typer.Option(min=1)] = 3,
    parallelism: Annotated[int, typer.Option(min=1)] = 2,
    runs_root: Annotated[
        Path, typer.Option(help="Where run directories live")
    ] = _DEFAULT_RUNS_ROOT,
    warm_cache: Annotated[
        Path | None, typer.Option(help="Seed each sandbox's .cache from here")
    ] = None,
    judge: Annotated[bool, typer.Option("--judge/--no-judge", help="Run the LLM judge")] = True,
    judge_model: Annotated[str, typer.Option()] = "sonnet",
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = True,
    keep_sandboxes: Annotated[bool, typer.Option("--keep-sandboxes/--delete-sandboxes")] = True,
    max_turns: Annotated[int, typer.Option(min=1)] = 30,
    timeout_s: Annotated[int, typer.Option(min=10)] = 900,
    allowed_tools: Annotated[str | None, typer.Option(help="Comma list for --allowedTools")] = None,
    only: Annotated[str | None, typer.Option(help="Comma list of scenario ids")] = None,
    tags: Annotated[str | None, typer.Option(help="Comma list of tags (any match)")] = None,
) -> None:
    """Run every scenario through the agent, grade, and write runs/<name>/results.jsonl."""
    model_provider = _make_provider(provider, model, max_turns, timeout_s, allowed_tools)
    judge_obj: Judge | None = ClaudeCliJudge(model=judge_model) if judge else None
    config = RunConfig(
        scenarios_path=scenarios,
        skill_path=skill,
        provider=model_provider,
        run_dir=runs_root / name,
        variant=variant or name,
        reps=reps,
        parallelism=parallelism,
        warm_cache=warm_cache,
        judge=judge_obj,
        resume=resume,
        keep_sandboxes=keep_sandboxes,
        only=frozenset(only.split(",")) if only else frozenset(),
        tags=frozenset(tags.split(",")) if tags else frozenset(),
        log=_console,
    )
    result = run(config)
    _console.print(
        f"[green]done:[/] {len(result.results)} result(s), {len(result.errors)} error(s), "
        f"{result.skipped} skipped; see {result.run_dir}"
    )
    if result.errors:
        raise typer.Exit(code=2)


@app.command("compare")
def compare(
    run_dirs: Annotated[list[Path], typer.Argument(help="Run directories; the first is the base")],
    out: Annotated[
        Path, typer.Option("--out", "-o", help="Where to write benchmark.md/json")
    ] = _DEFAULT_RUNS_ROOT / "_benchmarks",
) -> None:
    """Aggregate run directories into benchmark.md and benchmark.json."""
    report = benchmark(run_dirs)
    md, js = write_report(report, out)
    _console.print(f"wrote {md} and {js}")
    for note in report.notes:
        _console.print(f"- {note}")


@app.command("oracle")
def oracle(
    scenarios: Annotated[Path, typer.Option("--scenarios", "-s", help="Path to evals.json")],
    skill: Annotated[Path, typer.Option("--skill", "-k", help="Skill directory")],
    oracle_dir: Annotated[
        Path | None, typer.Option("--oracle-dir", help="Default: <evals.json dir>/oracle")
    ] = None,
    out: Annotated[Path, typer.Option("--out", "-o")] = _DEFAULT_RUNS_ROOT / "_oracle",
) -> None:
    """Check the graders: an ideal answer must pass every assertion, "I don't know" must fail.

    Runs the skill's pipeline on hand-written requests (no model, no cost) and exits 1 when an
    assertion is too strict or does not discriminate.
    """
    try:
        loaded = load_scenarios(scenarios)
    except ScenarioLoadError as exc:
        _console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=2) from exc
    report = run_oracle(
        loaded.scenarios,
        oracle_dir or scenarios.parent / "oracle",
        out,
        uv_pipeline_runner(skill),
    )
    out.mkdir(parents=True, exist_ok=True)
    (out / "oracle.md").write_text(render_oracle_markdown(report), encoding="utf-8")
    (out / "oracle.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _console.print(render_oracle_markdown(report))
    raise typer.Exit(code=0 if report.healthy else 1)


@app.command("trigger")
def trigger(
    cases: Annotated[Path, typer.Option("--cases", "-c", help="Path to trigger_evals.json")],
    skill: Annotated[Path, typer.Option("--skill", "-k")],
    name: Annotated[str, typer.Option("--name", "-n")],
    model: Annotated[str, typer.Option()] = "haiku",
    reps: Annotated[int, typer.Option(min=1)] = 3,
    parallelism: Annotated[int, typer.Option(min=1)] = 2,
    runs_root: Annotated[Path, typer.Option()] = _DEFAULT_RUNS_ROOT,
    max_turns: Annotated[int, typer.Option(min=1)] = 4,
    timeout_s: Annotated[int, typer.Option(min=10)] = 300,
    resume: Annotated[bool, typer.Option("--resume/--no-resume")] = True,
) -> None:
    """Check whether the skill description triggers on the right queries."""
    provider = ClaudeCliProvider(
        model=model,
        max_turns=max_turns,
        timeout_s=timeout_s,
        allowed_tools=["Skill", "Read", "Glob"],
    )
    config = TriggerConfig(
        cases_path=cases,
        skill_path=skill,
        provider=provider,
        run_dir=runs_root / name,
        reps=reps,
        parallelism=parallelism,
        resume=resume,
        log=_console,
    )
    report = run_trigger(config)
    _console.print(
        f"precision {report.precision}, recall {report.recall}; "
        f"{len(report.confusions)} confusion(s); see {config.run_dir / 'trigger.md'}"
    )


@app.command("smoke")
def smoke(
    model: Annotated[str, typer.Option()] = "haiku",
    timeout_s: Annotated[int, typer.Option(min=10)] = 120,
) -> None:
    """One trivial claude -p call: prints binary, served model, cost and visible skills."""
    binary = locate_claude_binary()
    _console.print(f"binary: {binary}")
    argv = [
        str(binary),
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--tools",
        "",
        "--no-session-persistence",
        "--setting-sources",
        "project",
    ]
    completed = subprocess.run(
        argv,
        input=b"Reply with exactly: OK",
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    stdout = completed.stdout.decode("utf-8", errors="replace").strip().lstrip("﻿")
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError:
        _console.print(
            f"[red]no JSON from the CLI (exit {completed.returncode})[/]\n{stdout[:800]}"
        )
        _console.print(completed.stderr.decode("utf-8", errors="replace")[-800:])
        raise typer.Exit(code=1) from None
    served = next(iter(envelope.get("modelUsage", {})), None)
    ok = served is not None and str(served).startswith(expected_model_prefix(model))
    _console.print(f"served model: {served} ({'matches' if ok else 'MISMATCH'} {model!r})")
    _console.print(f"result: {str(envelope.get('result'))[:100]!r}")
    _console.print(
        f"cost: {envelope.get('total_cost_usd')} USD, turns: {envelope.get('num_turns')}"
    )
    _console.print(f"session: {envelope.get('session_id')}, is_error: {envelope.get('is_error')}")
    raise typer.Exit(code=0 if ok and not envelope.get("is_error") else 1)


if __name__ == "__main__":
    app()
