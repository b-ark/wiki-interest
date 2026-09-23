"""Use-cases over past runs: list a session's runs and explain what changed between two.

Follow-up questions are the normal case, not the exception: a user changes the period, adds
an edition or excludes an article and wants to know what that did to the conclusion. Both
operations work purely on saved ``summary.json`` files, so they need no network.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from wiki_interest.contracts.summary import AnalysisSummary, MetricsOut

__all__ = [
    "SUMMARY_FILENAME",
    "MetricDelta",
    "PairDiff",
    "RunDiff",
    "RunRecord",
    "diff_runs",
    "list_runs",
    "load_summary",
]

SUMMARY_FILENAME = "summary.json"

_COMPARED_METRICS: tuple[str, ...] = (
    "views_avg",
    "per_million_avg",
    "growth_yoy",
    "growth_halves",
    "slope_per_year",
    "trend_p_value",
    "spike_share",
    "completeness",
)


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One past run, as much as a listing needs."""

    run_id: str
    session: str | None
    run_dir: Path
    generated_at: datetime
    status: str
    question_type: str
    topics: tuple[str, ...]
    projects: tuple[str, ...]
    period: str

    def to_dict(self) -> dict[str, object]:
        """JSON-ready representation."""
        return {
            "run_id": self.run_id,
            "session": self.session,
            "run_dir": str(self.run_dir),
            "generated_at": self.generated_at.isoformat(),
            "status": self.status,
            "question_type": self.question_type,
            "topics": list(self.topics),
            "projects": list(self.projects),
            "period": self.period,
        }


def load_summary(run_dir: Path) -> AnalysisSummary:
    """Read and validate the summary of a run directory.

    Raises:
        FileNotFoundError: If the directory has no summary file.
        pydantic.ValidationError: If the file does not match the current schema.
    """
    path = run_dir / SUMMARY_FILENAME
    return AnalysisSummary.model_validate_json(path.read_text(encoding="utf-8"))


def list_runs(runs_root: Path, session: str | None = None) -> tuple[RunRecord, ...]:
    """List runs under ``runs_root`` (optionally one session), newest first.

    Directories without a readable summary are skipped: a crashed run must not break the
    listing of the successful ones.
    """
    session_dirs = [runs_root / session] if session else sorted(_subdirs(runs_root))
    records: list[RunRecord] = []
    for session_dir in session_dirs:
        for run_dir in _subdirs(session_dir):
            record = _record(run_dir)
            if record is not None:
                records.append(record)
    return tuple(sorted(records, key=lambda r: r.generated_at, reverse=True))


def _subdirs(path: Path) -> Iterable[Path]:
    if not path.is_dir():
        return ()
    return sorted(p for p in path.iterdir() if p.is_dir())


def _record(run_dir: Path) -> RunRecord | None:
    try:
        summary = load_summary(run_dir)
    except (OSError, ValueError):
        return None
    period = summary.period
    return RunRecord(
        run_id=summary.run_id,
        session=summary.session,
        run_dir=run_dir,
        generated_at=summary.provenance.generated_at,
        status=summary.status,
        question_type=summary.request.question_type,
        topics=tuple(t.id or t.query for t in summary.request.topics),
        projects=tuple(summary.request.projects),
        period=f"{period.start:%Y-%m}..{period.end:%Y-%m}",
    )


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class MetricDelta:
    """One metric before and after."""

    name: str
    before: float | None
    after: float | None

    @property
    def delta(self) -> float | None:
        """``after - before`` when both are known."""
        if self.before is None or self.after is None:
            return None
        return self.after - self.before


@dataclass(frozen=True, slots=True)
class PairDiff:
    """Changes for one (topic, project) pair present in both runs."""

    topic_id: str
    project: str
    metrics: tuple[MetricDelta, ...]
    reliability_before: str | None
    reliability_after: str | None
    articles_added: tuple[str, ...]
    articles_removed: tuple[str, ...]

    @property
    def changed(self) -> bool:
        """Whether anything at all differs."""
        return (
            any(d.before != d.after for d in self.metrics)
            or self.reliability_before != self.reliability_after
            or bool(self.articles_added)
            or bool(self.articles_removed)
        )


@dataclass(frozen=True, slots=True)
class RunDiff:
    """What changed between two runs: the request, then every shared pair."""

    run_before: str
    run_after: str
    request_changes: dict[str, tuple[object, object]] = field(default_factory=dict)
    pairs: tuple[PairDiff, ...] = ()
    pairs_only_before: tuple[str, ...] = ()
    pairs_only_after: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """JSON-ready representation."""
        return {
            "run_before": self.run_before,
            "run_after": self.run_after,
            "request_changes": {
                key: {"before": before, "after": after}
                for key, (before, after) in self.request_changes.items()
            },
            "pairs": [
                {
                    "topic_id": p.topic_id,
                    "project": p.project,
                    "changed": p.changed,
                    "reliability": {"before": p.reliability_before, "after": p.reliability_after},
                    "metrics": [
                        {"name": m.name, "before": m.before, "after": m.after, "delta": m.delta}
                        for m in p.metrics
                    ],
                    "articles_added": list(p.articles_added),
                    "articles_removed": list(p.articles_removed),
                }
                for p in self.pairs
            ],
            "pairs_only_before": list(self.pairs_only_before),
            "pairs_only_after": list(self.pairs_only_after),
        }


def diff_runs(before: AnalysisSummary, after: AnalysisSummary) -> RunDiff:
    """Compare two summaries pair by pair.

    Metrics are compared on the measured series (the main article). Pairs present in only
    one run are listed separately rather than diffed against nothing.
    """
    request_changes = _request_changes(before, after)
    before_metrics = _metrics(before)
    after_metrics = _metrics(after)
    shared = [key for key in before_metrics if key in after_metrics]
    pairs = tuple(_pair_diff(key, before, after) for key in shared)
    return RunDiff(
        run_before=before.run_id,
        run_after=after.run_id,
        request_changes=request_changes,
        pairs=pairs,
        pairs_only_before=tuple(
            f"{t}@{p}" for t, p in before_metrics if (t, p) not in after_metrics
        ),
        pairs_only_after=tuple(
            f"{t}@{p}" for t, p in after_metrics if (t, p) not in before_metrics
        ),
    )


def _request_changes(
    before: AnalysisSummary, after: AnalysisSummary
) -> dict[str, tuple[object, object]]:
    old = before.request.model_dump(mode="json")
    new = after.request.model_dump(mode="json")
    old["period"] = before.period.model_dump(mode="json")
    new["period"] = after.period.model_dump(mode="json")
    return {key: (old.get(key), new.get(key)) for key in old if old.get(key) != new.get(key)}


def _metrics(summary: AnalysisSummary) -> dict[tuple[str, str], MetricsOut]:
    return {(m.topic_id, m.project): m for m in summary.metrics}


def _pair_diff(key: tuple[str, str], before: AnalysisSummary, after: AnalysisSummary) -> PairDiff:
    topic_id, project = key
    old = _metrics(before)[key]
    new = _metrics(after)[key]
    metrics = tuple(
        MetricDelta(name, getattr(old, name), getattr(new, name)) for name in _COMPARED_METRICS
    )
    old_articles = _articles(before, key)
    new_articles = _articles(after, key)
    return PairDiff(
        topic_id=topic_id,
        project=project,
        metrics=metrics,
        reliability_before=_reliability(before, key),
        reliability_after=_reliability(after, key),
        articles_added=tuple(sorted(new_articles - old_articles)),
        articles_removed=tuple(sorted(old_articles - new_articles)),
    )


def _articles(summary: AnalysisSummary, key: tuple[str, str]) -> set[str]:
    topic_id, project = key
    for topic in summary.resolution:
        if topic.topic_id != topic_id:
            continue
        for bundle in topic.bundles:
            if bundle.project == project:
                return {a.title for a in bundle.articles}
    return set()


def _reliability(summary: AnalysisSummary, key: tuple[str, str]) -> str | None:
    topic_id, project = key
    for item in summary.reliability:
        if item.topic_id == topic_id and item.project == project:
            return str(item.level)
    return None
