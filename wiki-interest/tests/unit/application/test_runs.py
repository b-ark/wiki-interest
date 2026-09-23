"""Listing past runs and diffing two summaries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from wiki_interest.application.runs import diff_runs, load_summary
from wiki_interest.contracts.request import AnalysisRequest, Period
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    ArticleOut,
    Artifacts,
    BundleOut,
    MetricsOut,
    Provenance,
    ReliabilityOut,
    TopicResolutionOut,
    Verdict,
)
from wiki_interest.domain.models import (
    ArticleRole,
    BundleStatus,
    ReliabilityLevel,
    ResolutionSource,
    TrendDirection,
)


def _metrics(project: str, *, growth: float | None = 0.1, views: float = 1000.0) -> MetricsOut:
    return MetricsOut(
        topic_id="astronomy",
        project=project,
        periods=24,
        completeness=1.0,
        views_total=views * 24,
        views_avg=views,
        per_million_avg=12.5,
        growth_yoy=growth,
        growth_halves=growth,
        slope_per_year=growth,
        trend_p_value=0.01,
        trend_direction=TrendDirection.RISING,
        seasonality_strength=None,
        spike_share=0.05,
        volatility_cv=0.1,
        automated_share=None,
    )


def _summary(
    run_id: str,
    *,
    projects: list[str],
    generated_at: datetime,
    period: tuple[str, str] = ("2024-09", "2026-08"),
    growth: float | None = 0.1,
    article: str = "Астрономія",
    level: ReliabilityLevel = ReliabilityLevel.HIGH,
    session: str | None = "astro",
) -> AnalysisSummary:
    request = AnalysisRequest.model_validate(
        {
            "question_type": "compare" if len(projects) > 1 else "assess",
            "topics": [{"query": "astronomy", "id": "astronomy"}],
            "projects": projects,
            "session": session,
        }
    )
    projects = list(request.projects)  # normalised spellings, as the pipeline writes them
    return AnalysisSummary(
        status="ok",
        run_id=run_id,
        session=session,
        request=request,
        period=Period.model_validate({"start": period[0], "end": period[1]}),
        resolution=[
            TopicResolutionOut(
                topic_id="astronomy",
                query="astronomy",
                label="astronomy",
                qid="Q333",
                bundles=[
                    BundleOut(
                        topic_id="astronomy",
                        project=p,
                        status=BundleStatus.FOUND,
                        articles=[
                            ArticleOut(
                                title=article,
                                role=ArticleRole.MAIN,
                                source=ResolutionSource.SITELINK,
                            )
                        ],
                    )
                    for p in projects
                ],
            )
        ],
        metrics=[_metrics(p, growth=growth) for p in projects],
        reliability=[
            ReliabilityOut(topic_id="astronomy", project=p, level=level, checks=[])
            for p in projects
        ],
        verdict=Verdict(headline="x"),
        artifacts=Artifacts(run_dir="/r", summary_json="/r/summary.json", summary_md="/r/s.md"),
        provenance=Provenance(
            code_version="0.1.0",
            generated_at=generated_at,
            data_through=period[1],
            user_agent="ua",
            sources=[],
        ),
    )


def _write(runs_root: Path, summary: AnalysisSummary) -> Path:
    run_dir = runs_root / (summary.session or "default") / summary.run_id
    run_dir.mkdir(parents=True)
    (run_dir / "summary.json").write_text(summary.model_dump_json(), encoding="utf-8")
    return run_dir


T1 = datetime(2026, 9, 22, 10, 0, tzinfo=UTC)
T2 = datetime(2026, 9, 22, 11, 0, tzinfo=UTC)


class TestLoadSummary:
    def test_load_summary_round_trips(self, tmp_path: Path) -> None:
        summary = _summary("run-1", projects=["uk"], generated_at=T1)
        run_dir = _write(tmp_path, summary)
        assert load_summary(run_dir) == summary


class TestDiffRuns:
    def test_reports_request_metric_reliability_and_bundle_changes(self) -> None:
        before = _summary("run-1", projects=["uk"], generated_at=T1, growth=0.10)
        after = _summary(
            "run-2",
            projects=["uk"],
            generated_at=T2,
            period=("2021-09", "2026-08"),
            growth=0.25,
            article="Астрономія (наука)",
            level=ReliabilityLevel.MEDIUM,
        )
        diff = diff_runs(before, after)
        assert diff.run_before == "run-1"
        assert diff.run_after == "run-2"
        assert diff.request_changes == {
            "period": (
                {"start": "2024-09", "end": "2026-08"},
                {"start": "2021-09", "end": "2026-08"},
            )
        }
        assert len(diff.pairs) == 1
        pair = diff.pairs[0]
        assert pair.changed
        growth = next(m for m in pair.metrics if m.name == "growth_yoy")
        assert growth.delta is not None
        assert growth.delta == 0.15
        assert (pair.reliability_before, pair.reliability_after) == ("high", "medium")
        assert pair.articles_added == ("Астрономія (наука)",)
        assert pair.articles_removed == ("Астрономія",)
        payload = json.loads(json.dumps(diff.to_dict()))
        assert payload["pairs"][0]["metrics"][2]["name"] == "growth_yoy"

    def test_identical_runs_show_no_changes(self) -> None:
        before = _summary("run-1", projects=["uk"], generated_at=T1)
        after = _summary("run-2", projects=["uk"], generated_at=T2)
        diff = diff_runs(before, after)
        assert diff.request_changes == {}
        assert not diff.pairs[0].changed

    def test_added_and_removed_pairs_are_listed_separately(self) -> None:
        before = _summary("run-1", projects=["uk", "pl"], generated_at=T1)
        after = _summary("run-2", projects=["uk", "cs"], generated_at=T2)
        diff = diff_runs(before, after)
        assert [p.project for p in diff.pairs] == ["uk.wikipedia"]
        assert diff.pairs_only_before == ("astronomy@pl.wikipedia",)
        assert diff.pairs_only_after == ("astronomy@cs.wikipedia",)

    def test_missing_metric_values_give_no_delta(self) -> None:
        before = _summary("run-1", projects=["uk"], generated_at=T1, growth=None)
        after = _summary("run-2", projects=["uk"], generated_at=T2, growth=0.2)
        growth = next(
            m for m in diff_runs(before, after).pairs[0].metrics if m.name == "growth_yoy"
        )
        assert growth.delta is None
        assert growth.before is None
        assert growth.after == 0.2
