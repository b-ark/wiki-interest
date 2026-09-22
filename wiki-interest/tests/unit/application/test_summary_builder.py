"""Prose and structure of the summary built from an analysis."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fakes import AstronomyWorld, FakePage, astronomy_world, fake_container
from wiki_interest.application.analysis import analyse
from wiki_interest.application.summary_builder import (
    ProvenanceInput,
    RunContext,
    SummaryBuilder,
)
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.domain.models import EntityCandidate, WikiProject
from wiki_interest.errors import ClarificationNeededError
from wiki_interest.i18n import Translator

PROVENANCE = ProvenanceInput("0.1.0", "ua", ("src",), request_count=3, cache_hits=1)


def _build(
    tmp_path: Path,
    language: str = "en",
    world: AstronomyWorld | None = None,
    **overrides: object,
) -> AnalysisSummary:
    data: dict[str, object] = {
        "question_type": "compare",
        "topics": [{"query": "astronomy", "query_language": "en", "id": "astronomy"}],
        "projects": ["uk", "cs", "pl"],
        "period": {"start": "2024-09", "end": "2026-08"},
        "report": {"language": language},
    }
    data.update(overrides)
    request = AnalysisRequest.model_validate(data)
    container = fake_container(world or astronomy_world(), tmp_path)
    assert request.period is not None
    resolved = container.resolver().resolve_request(request)
    loaded = container.loader(request).load(resolved, request.period)
    analysis = analyse(
        resolved,
        loaded,
        weights=request.ranking_weights.to_domain(),
        settings=container.analysis_settings(request),
    )
    context = RunContext("run-1", None, tmp_path / "run-1", datetime(2026, 9, 22, tzinfo=UTC))
    return SummaryBuilder(Translator(language), context, PROVENANCE).build(
        request=request, period=request.period, resolved=resolved, analysis=analysis
    )


class TestCompare:
    def test_headline_names_the_leaders_and_bullets_cover_every_pair(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        assert summary.status == "ok"
        assert "uk.wikipedia" in summary.verdict.headline
        assert "per million" in summary.verdict.headline
        assert len(summary.verdict.bullets) == 3
        assert any("no article" in b for b in summary.verdict.bullets)

    def test_not_found_edition_is_explained_not_zeroed(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        pl = next(r for r in summary.comparison if r.project == "pl.wikipedia")
        assert pl.views_avg is None
        assert pl.note == "no article in this edition"
        assert any("pl.wikipedia" in lim and "no article" in lim for lim in summary.limitations)
        assert any("extra_titles" in step and "pl.wikipedia" in step for step in summary.next_steps)

    def test_reliability_messages_are_localised(self, tmp_path: Path) -> None:
        summary = _build(tmp_path, language="uk")
        uk = next(r for r in summary.reliability if r.project == "uk.wikipedia")
        messages = [c.message for c in uk.checks]
        assert any("місяців" in m for m in messages)
        assert all(c.reason_key for c in uk.checks)

    def test_series_and_metrics_cover_bundle_and_main(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        kinds = {(s.project, s.kind) for s in summary.series}
        assert ("uk.wikipedia", "bundle") in kinds
        assert ("uk.wikipedia", "main") in kinds
        assert ("pl.wikipedia", "bundle") not in kinds
        assert {(m.project, m.kind) for m in summary.metrics} >= {
            ("uk.wikipedia", "bundle"),
            ("uk.wikipedia", "main"),
        }
        bundle_series = next(
            s for s in summary.series if s.project == "uk.wikipedia" and s.kind == "bundle"
        )
        assert bundle_series.points[0].period == "2024-09"
        assert bundle_series.points[0].per_million is not None

    def test_charts_for_compare(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        assert [(c.id, c.kind) for c in summary.charts] == [
            ("interest-over-time", "lines"),
            ("growth", "bars"),
        ]
        lines = summary.charts[0]
        assert [s.label for s in lines.series] == ["uk.wikipedia", "cs.wikipedia"]
        assert lines.series[0].x[0] == "2024-09"
        assert summary.charts[1].series[0].y[1] == pytest.approx(0.0, abs=5.0)

    def test_artifacts_point_into_the_run_dir(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        assert summary.artifacts.run_dir == str(tmp_path / "run-1")
        assert summary.artifacts.charts == [
            str(tmp_path / "run-1" / "charts" / "interest-over-time.png"),
            str(tmp_path / "run-1" / "charts" / "growth.png"),
        ]
        assert summary.provenance.request_count == 3

    def test_search_fallback_reason_names_the_article_to_verify(self, tmp_path: Path) -> None:
        world = astronomy_world()
        pl = WikiProject("pl")
        world.mediawiki.add_page(pl, FakePage("Astronomia", qid=None))
        world.mediawiki.add_search(pl, "astronomy", ["Astronomia"])
        world.pageviews.set_article(pl, "Astronomia", dict.fromkeys(world.months, 500.0))
        world.pageviews.set_aggregate(pl, dict.fromkeys(world.months, 1e7))
        summary = _build(tmp_path, world=world, question_type="assess", projects=["pl"])
        pl_reliability = next(r for r in summary.reliability if r.project == "pl.wikipedia")
        check = next(c for c in pl_reliability.checks if c.name == "resolution")
        assert check.reason_key == "resolution.search_fallback"
        assert "Astronomia" in check.message
        assert check.params["title"] == "Astronomia"

    def test_absolute_mode_changes_wording_and_limitations(self, tmp_path: Path) -> None:
        summary = _build(tmp_path, normalization="absolute")
        assert "views/month" in summary.verdict.headline
        assert any("without normalising" in lim for lim in summary.limitations)
        assert any("per-million" in step for step in summary.next_steps)


class TestAssessAndRank:
    def test_assess_headline_states_direction_growth_and_trust(self, tmp_path: Path) -> None:
        summary = _build(tmp_path, question_type="assess", projects=["uk"])
        headline = summary.verdict.headline
        assert "astronomy" in headline
        assert "rising" in headline
        assert "trust: high" in headline or "trust: medium" in headline
        assert [c.kind for c in summary.charts] == ["trend", "bars"]
        assert summary.charts[0].trend_y is not None

    def test_rank_rows_have_rationales_and_research_suggestions(self, tmp_path: Path) -> None:
        summary = _build(tmp_path, question_type="rank")
        assert [r.rank for r in summary.ranking] == [1, 2, 3]
        assert summary.ranking[0].project == "uk.wikipedia"
        assert "growth" in summary.ranking[0].rationale
        assert summary.ranking[-1].rationale == "insufficient data for ranking"
        assert any(step.startswith("Research next") for step in summary.next_steps)
        assert summary.charts[-1].id == "ranking-score"


def test_clarification_summary_carries_candidates_and_question(tmp_path: Path) -> None:
    request = AnalysisRequest.model_validate(
        {
            "question_type": "assess",
            "topics": [{"query": "astro", "id": "astro"}],
            "projects": ["uk"],
            "period": {"start": "2024-09", "end": "2026-08"},
            "report": {"language": "ru"},
        }
    )
    error = ClarificationNeededError(
        "ambiguous",
        topic_id="astro",
        candidates=[
            EntityCandidate("Q333", "astronomy", "science"),
            EntityCandidate("Q999", "astrology"),
        ],
    )
    assert request.period is not None
    context = RunContext("r", None, tmp_path, datetime(2026, 9, 22, tzinfo=UTC))
    summary = SummaryBuilder(Translator("ru"), context, PROVENANCE).build_clarification(
        request=request, period=request.period, error=error
    )
    assert summary.status == "needs_clarification"
    assert summary.clarification is not None
    assert [c.qid for c in summary.clarification.candidates] == ["Q333", "Q999"]
    assert summary.clarification.query == "astro"
    assert summary.verdict.headline  # the question line, localised
    assert summary.artifacts.charts == []
