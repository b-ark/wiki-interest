"""Benchmark report: per-variant statistics, pairwise deltas and an explicit noise floor.

The question the report answers is "did this change to the skill help?", and the honest
answer needs three things next to each other: the mean, how much it wobbles between
repetitions, and how big a difference could arise by chance. With ``n`` scenarios and ``R``
reps of a pass/fail measure the standard error of a mean is at most ``0.5/sqrt(n·R)``; we
report the conservative ``1/sqrt(n·R)`` as the noise floor and call a delta significant only
when it exceeds it. Errors are counted by class so a run with many of them is visibly
untrustworthy.
"""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from skill_evals.records import CaseResult, ErrorRecord, read_jsonl

_EPSILON = 1e-9
"""Below this, two pass rates are considered equal (float noise from averaging)."""

__all__ = [
    "BenchmarkReport",
    "PairwiseDelta",
    "ScenarioDelta",
    "VariantStats",
    "benchmark",
    "load_run",
    "noise_floor",
    "render_markdown",
    "write_report",
]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True)


class VariantStats(_Model):
    """Aggregates for one run directory (one skill variant)."""

    variant: str
    run_dir: str
    skill_hashes: list[str]
    requested_model: str
    served_models: list[str]
    n_scenarios: int
    reps: int
    n_results: int
    n_errors: int
    n_errors_resolved_by_resume: int
    errors_by_class: dict[str, int]
    status_counts: dict[str, int]
    pass_rate_mean: float | None
    pass_rate_std: float | None
    deterministic_pass_rate: float | None
    judge_pass_rate: float | None
    per_assertion: dict[str, float]
    per_rubric: dict[str, float]
    per_scenario: dict[str, float]
    mean_turns: float | None
    mean_input_tokens: float | None
    mean_output_tokens: float | None
    mean_cost_usd: float | None
    mean_duration_s: float | None
    noise_floor: float | None


class ScenarioDelta(_Model):
    """Per-scenario difference between two variants (``other - base``)."""

    scenario_id: str
    base_rate: float
    other_rate: float
    delta: float


class PairwiseDelta(_Model):
    """Comparison of two variants on the scenarios both have results for."""

    base: str
    other: str
    n_common_scenarios: int
    delta_overall: float | None
    noise_floor: float | None
    significant: bool
    per_scenario: list[ScenarioDelta]
    disagreements: list[ScenarioDelta]


class BenchmarkReport(_Model):
    """The whole comparison, serialisable to ``benchmark.json``."""

    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    variants: list[VariantStats]
    pairwise: list[PairwiseDelta]
    notes: list[str]


class _Run:
    """Loaded run directory."""

    def __init__(self, run_dir: Path, results: list[CaseResult], errors: list[ErrorRecord]) -> None:
        self.run_dir = run_dir
        self.results = results
        self.errors = errors
        manifest_path = run_dir / "run.json"
        self.manifest: dict[str, object] = (
            json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            if manifest_path.exists()
            else {}
        )

    @property
    def variant(self) -> str:
        if self.results:
            return self.results[0].variant
        value = self.manifest.get("variant")
        return str(value) if value else self.run_dir.name


def load_run(run_dir: Path) -> _Run:
    """Read ``results.jsonl`` and ``errors.jsonl`` of one run directory."""
    return _Run(
        run_dir,
        read_jsonl(run_dir / "results.jsonl", CaseResult),
        read_jsonl(run_dir / "errors.jsonl", ErrorRecord),
    )


def noise_floor(n_scenarios: int, reps: int) -> float | None:
    """Conservative standard error of a pass-rate mean over ``n_scenarios × reps`` cases."""
    cases = n_scenarios * reps
    return None if cases <= 0 else 1.0 / (cases**0.5)


def _mean(values: Iterable[float]) -> float | None:
    items = list(values)
    return statistics.fmean(items) if items else None


def _std(values: Sequence[float]) -> float | None:
    if len(values) < 2:  # noqa: PLR2004 - a sample std needs two points
        return 0.0 if values else None
    return statistics.stdev(values)


def _per_scenario(results: Sequence[CaseResult]) -> dict[str, float]:
    """Mean pass rate per scenario over its reps (scenarios without grades are skipped)."""
    by_id: dict[str, list[float]] = defaultdict(list)
    for r in results:
        if r.pass_rate is not None:
            by_id[r.scenario_id].append(r.pass_rate)
    return {sid: statistics.fmean(v) for sid, v in sorted(by_id.items())}


def _rep_means(results: Sequence[CaseResult]) -> list[float]:
    """Mean pass rate of each rep across scenarios; their spread is the rep-to-rep noise."""
    by_rep: dict[int, list[float]] = defaultdict(list)
    for r in results:
        if r.pass_rate is not None:
            by_rep[r.rep].append(r.pass_rate)
    return [statistics.fmean(v) for _, v in sorted(by_rep.items())]


def _grade_rates(results: Sequence[CaseResult], kind: str, key: str) -> dict[str, float]:
    hits: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        for g in r.grades:
            if g.kind == kind:
                hits[getattr(g, key)].append(g.passed)
    return {k: sum(v) / len(v) for k, v in sorted(hits.items())}


def _kind_rate(results: Sequence[CaseResult], kind: str) -> float | None:
    flags = [g.passed for r in results for g in r.grades if g.kind == kind]
    return sum(flags) / len(flags) if flags else None


def _variant_stats(run: _Run) -> VariantStats:
    results = run.results
    per_scenario = _per_scenario(results)
    measured = {(r.scenario_id, r.rep) for r in results}
    unresolved = [e for e in run.errors if (e.scenario_id, e.rep) not in measured]
    reps = max((r.rep for r in results), default=int(str(run.manifest.get("reps", 0)) or 0))
    n_scenarios = len(per_scenario)
    rep_means = _rep_means(results)
    return VariantStats(
        variant=run.variant,
        run_dir=str(run.run_dir),
        skill_hashes=sorted({r.skill_hash for r in results}),
        requested_model=results[0].requested_model
        if results
        else str(run.manifest.get("requested_model", "")),
        served_models=sorted({m for r in results for m in r.served_models}),
        n_scenarios=n_scenarios,
        reps=reps,
        n_results=len(results),
        n_errors=len(unresolved),
        n_errors_resolved_by_resume=len(run.errors) - len(unresolved),
        errors_by_class=dict(sorted(Counter(e.failure_class for e in unresolved).items())),
        status_counts=dict(sorted(Counter(r.status for r in results).items())),
        pass_rate_mean=_mean(per_scenario.values()),
        pass_rate_std=_std(rep_means),
        deterministic_pass_rate=_kind_rate(results, "deterministic"),
        judge_pass_rate=_kind_rate(results, "judge"),
        per_assertion=_grade_rates(results, "deterministic", "type"),
        per_rubric=_grade_rates(results, "judge", "id"),
        per_scenario=per_scenario,
        mean_turns=_mean(float(r.num_turns) for r in results),
        mean_input_tokens=_mean(
            float(r.usage.input_tokens + r.usage.cache_read_tokens + r.usage.cache_creation_tokens)
            for r in results
        ),
        mean_output_tokens=_mean(float(r.usage.output_tokens) for r in results),
        mean_cost_usd=_mean(r.cost_usd for r in results if r.cost_usd is not None),
        mean_duration_s=_mean(r.duration_s for r in results),
        noise_floor=noise_floor(n_scenarios, reps),
    )


def _pairwise(base: VariantStats, other: VariantStats) -> PairwiseDelta:
    common = sorted(set(base.per_scenario) & set(other.per_scenario))
    deltas = [
        ScenarioDelta(
            scenario_id=sid,
            base_rate=base.per_scenario[sid],
            other_rate=other.per_scenario[sid],
            delta=other.per_scenario[sid] - base.per_scenario[sid],
        )
        for sid in common
    ]
    overall = _mean(d.delta for d in deltas)
    floor = noise_floor(len(common), min(base.reps, other.reps))
    significant = overall is not None and floor is not None and abs(overall) > floor
    return PairwiseDelta(
        base=base.variant,
        other=other.variant,
        n_common_scenarios=len(common),
        delta_overall=overall,
        noise_floor=floor,
        significant=significant,
        per_scenario=deltas,
        disagreements=[d for d in deltas if abs(d.delta) > _EPSILON],
    )


def benchmark(run_dirs: Sequence[Path]) -> BenchmarkReport:
    """Aggregate one or more run directories; the first is the base for pairwise deltas."""
    runs = [load_run(d) for d in run_dirs]
    variants = [_variant_stats(r) for r in runs]
    pairwise = [_pairwise(a, b) for a, b in combinations(variants, 2)]
    return BenchmarkReport(variants=variants, pairwise=pairwise, notes=_notes(variants, pairwise))


def _notes(variants: Sequence[VariantStats], pairwise: Sequence[PairwiseDelta]) -> list[str]:
    notes: list[str] = []
    for v in variants:
        if v.n_errors:
            notes.append(
                f"{v.variant}: {v.n_errors} case(s) could not be measured "
                f"({v.errors_by_class}); they are excluded from the scores, "
                "not counted as failures."
            )
        if len(v.skill_hashes) > 1:
            notes.append(
                f"{v.variant}: results come from {len(v.skill_hashes)} different skill hashes."
            )
        if len(v.served_models) > 1:
            notes.append(f"{v.variant}: more than one served model: {v.served_models}.")
    for p in pairwise:
        if p.delta_overall is not None and p.noise_floor is not None and not p.significant:
            notes.append(
                f"{p.other} vs {p.base}: delta {p.delta_overall:+.3f} is within the noise floor "
                f"{p.noise_floor:.3f}; do not conclude either is better."
            )
    return notes


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _num(value: float | None, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def render_markdown(report: BenchmarkReport) -> str:
    """Render the report as Markdown for ``benchmark.md``."""
    lines = [f"# Benchmark ({report.generated_at:%Y-%m-%d %H:%M} UTC)", ""]
    lines += _variant_table(report.variants)
    lines += _breakdown_tables(report.variants)
    for pair in report.pairwise:
        lines += _pair_section(pair)
    if report.notes:
        lines += ["## Notes", ""] + [f"- {n}" for n in report.notes] + [""]
    return "\n".join(lines)


def _variant_table(variants: Sequence[VariantStats]) -> list[str]:
    header = (
        "| Variant | Scenarios × reps | Pass rate (mean ± std over reps) | Noise floor "
        "| Deterministic | Judge | Turns | Tokens in/out | Cost USD | Duration s | Errors |"
    )
    rows = [header, "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v in variants:
        rows.append(
            f"| {v.variant} | {v.n_scenarios} × {v.reps} | {_pct(v.pass_rate_mean)} ± "
            f"{_pct(v.pass_rate_std)} | {_num(v.noise_floor, 3)} | "
            f"{_pct(v.deterministic_pass_rate)} "
            f"| {_pct(v.judge_pass_rate)} | {_num(v.mean_turns, 1)} | "
            f"{_num(v.mean_input_tokens, 0)}/{_num(v.mean_output_tokens, 0)} | "
            f"{_num(v.mean_cost_usd, 4)} | {_num(v.mean_duration_s, 0)} | {v.n_errors} |"
        )
    return ["## Variants", "", *rows, ""]


def _breakdown_tables(variants: Sequence[VariantStats]) -> list[str]:
    lines: list[str] = []
    for v in variants:
        lines += [f"## {v.variant}", ""]
        lines.append(f"- run dir: `{v.run_dir}`")
        lines.append(f"- requested model: `{v.requested_model}`; served: {v.served_models}")
        lines.append(f"- skill hash(es): {[h[:12] for h in v.skill_hashes]}")
        lines.append(
            f"- statuses: {v.status_counts}; unmeasured cases by class: {v.errors_by_class}; "
            f"errors later resolved by resume: {v.n_errors_resolved_by_resume}"
        )
        lines.append("")
        if v.per_assertion:
            lines += ["| Assertion type | Pass rate |", "|---|---|"]
            lines += [f"| {k} | {_pct(r)} |" for k, r in v.per_assertion.items()]
            lines.append("")
        if v.per_rubric:
            lines += ["| Rubric | Pass rate |", "|---|---|"]
            lines += [f"| {k} | {_pct(r)} |" for k, r in v.per_rubric.items()]
            lines.append("")
        if v.per_scenario:
            lines += ["| Scenario | Pass rate |", "|---|---|"]
            lines += [f"| {k} | {_pct(r)} |" for k, r in v.per_scenario.items()]
            lines.append("")
    return lines


def _pair_section(pair: PairwiseDelta) -> list[str]:
    verdict = "beyond the noise floor" if pair.significant else "within the noise floor"
    lines = [
        f"## {pair.other} vs {pair.base}",
        "",
        f"Overall delta (other − base): {_num(pair.delta_overall, 3)} on "
        f"{pair.n_common_scenarios} common scenario(s); noise floor {_num(pair.noise_floor, 3)} "
        f"({verdict}).",
        "",
    ]
    if pair.disagreements:
        lines += ["| Scenario | Base | Other | Delta |", "|---|---|---|---|"]
        lines += [
            f"| {d.scenario_id} | {_pct(d.base_rate)} | {_pct(d.other_rate)} | {d.delta:+.2f} |"
            for d in pair.disagreements
        ]
    else:
        lines.append("No scenario differs between the two variants.")
    lines.append("")
    return lines


def write_report(report: BenchmarkReport, target_dir: Path) -> tuple[Path, Path]:
    """Write ``benchmark.md`` and ``benchmark.json`` into ``target_dir``."""
    target_dir.mkdir(parents=True, exist_ok=True)
    md = target_dir / "benchmark.md"
    js = target_dir / "benchmark.json"
    md.write_text(render_markdown(report), encoding="utf-8", newline="\n")
    js.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8", newline="\n")
    return md, js
