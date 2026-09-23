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
    def test_headline_names_the_leaders_and_bullets_are_the_findings(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        assert summary.status == "ok"
        headline = summary.verdict.headline
        assert headline == (
            "The attention share of «astronomy»: growing in uk.wikipedia; no clear trend in "
            "cs.wikipedia."
        )
        happening = summary.happening
        assert happening[0].startswith("Attention share (article views per 1 million edition")
        assert "cs.wikipedia 40.0" in happening[0]
        assert happening[1].startswith("Attention share, last 12 months vs the 12 before:")
        # The edition without an article is part of the answer, not only of the findings.
        assert any("No article in pl.wikipedia" in line for line in happening)
        assert summary.verdict.bullets == [f.text for f in summary.findings]
        # The edition without an article comes first, so it is never read as zero interest.
        first = summary.findings[0]
        assert (first.kind, first.project) == ("no_article", "pl.wikipedia")

    def test_assessments_split_a_change_into_article_and_edition(self, tmp_path: Path) -> None:
        summary = _build(tmp_path, question_type="assess", projects=["uk"])
        (uk,) = summary.assessments
        assert (uk.momentum, uk.outcome, uk.relation) == ("growing", "single_growing", "gaining")
        assert uk.edition_line is not None
        assert "article views +21%, edition traffic" in uk.edition_line
        assert uk.article_change == pytest.approx(0.21, abs=0.01)
        assert uk.relation_basis == "yoy"
        assert [e.text for e in uk.evidence][:1] == ["24 months of data"]
        assert uk.robustness_line is not None
        row = next(r for r in summary.comparison if r.project == "uk.wikipedia")
        assert row.views_growth == pytest.approx(uk.article_change, abs=1e-6)
        assert row.edition_growth == pytest.approx(uk.edition_change, abs=1e-6)

    def test_decision_groups_outcomes_and_names_the_next_step(self, tmp_path: Path) -> None:
        decision = _build(tmp_path).decision
        assert decision is not None
        assert (decision.conclusion, decision.candidate) == ("strong", "uk.wikipedia")
        assert decision.summary is not None
        assert decision.summary.startswith("uk.wikipedia combines the highest attention share")
        assert decision.lines[0].startswith("uk.wikipedia: higher attention share, and it is")
        assert decision.next_step.startswith("Next step: confirm the signal for uk.wikipedia")
        assert "Google Trends" in decision.next_step

    def test_share_is_stated_per_million_with_an_index(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        cs = next(r for r in summary.comparison if r.project == "cs.wikipedia")
        assert cs.per_million_avg is not None
        assert cs.index == 100.0
        uk = next(r for r in summary.comparison if r.project == "uk.wikipedia")
        assert uk.index is not None
        assert 0 < uk.index < 100

    def test_related_articles_are_reported_as_context(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        uk = [c for c in summary.context if c.project == "uk.wikipedia"]
        assert [c.title for c in uk] == ["Телескоп"]
        assert uk[0].views_avg is not None
        assert any("one main article" in lim for lim in summary.general_limitations)

    def test_headline_does_not_call_a_decline_growth(self, tmp_path: Path) -> None:
        world = astronomy_world()
        uk = WikiProject("uk")
        world.pageviews.set_article(
            uk, "Астрономія", {m: 6000.0 - 100.0 * i for i, m in enumerate(world.months)}
        )
        world.pageviews.set_article(
            uk, "Телескоп", {m: 900.0 - 10.0 * i for i, m in enumerate(world.months)}
        )
        summary = _build(
            tmp_path,
            projects=["uk"],
            question_type="compare",
            world=world,
            topics=[
                {"query": "astronomy", "id": "astronomy"},
                {"query": "telescope", "id": "telescope", "bundle": "main"},
            ],
        )
        headline = summary.verdict.headline
        assert headline.startswith("The attention share of «astronomy», «telescope» is falling")
        assert "everywhere, fastest in" in headline
        assert summary.decision is not None
        assert summary.decision.summary is not None
        assert "not growing in any edition" in summary.decision.summary

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

    def test_series_and_metrics_cover_each_measured_edition_once(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        assert [s.project for s in summary.series] == ["uk.wikipedia", "cs.wikipedia"]
        assert [m.project for m in summary.metrics] == ["uk.wikipedia", "cs.wikipedia"]
        first = summary.series[0].points[0]
        assert first.period == "2024-09"
        assert first.per_million is not None
        assert first.edition_views is not None

    def test_bundles_state_their_article_counts(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        uk = next(b for b in summary.resolution[0].bundles if b.project == "uk.wikipedia")
        assert uk.article_count == len(uk.articles)
        assert uk.related_count == len(uk.articles) - 1
        pl = next(b for b in summary.resolution[0].bundles if b.project == "pl.wikipedia")
        assert (pl.article_count, pl.related_count) == (0, 0)

    def test_charts_for_compare(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        assert [(c.id, c.kind, c.size) for c in summary.charts] == [
            ("main", "panels", "wide"),
            ("change", "lines", "strip"),
        ]
        main = summary.charts[0]
        assert main.subtitle is not None
        assert [p.title for p in main.panels] == ["uk.wikipedia", "cs.wikipedia"]
        assert main.panels[0].series[0].x[0] == "2024-09"
        change = summary.charts[1]
        assert [s.label for s in change.series] == ["uk.wikipedia", "cs.wikipedia"]
        assert change.reference_y == 0.0

    def test_artifacts_point_into_the_run_dir(self, tmp_path: Path) -> None:
        summary = _build(tmp_path)
        assert summary.artifacts.run_dir == str(tmp_path / "run-1")
        assert summary.artifacts.charts == [
            str(tmp_path / "run-1" / "charts" / f"{c.id}.png") for c in summary.charts
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
        assert summary.verdict.headline.startswith("The number of article views on «astronomy»")
        assert summary.happening[0].startswith("Article views per month, average over the period")
        assert any("without normalising" in lim for lim in summary.limitations)
        assert any("per-million" in step for step in summary.next_steps)
        assert summary.charts[1].title.startswith("Article views")


class TestAssessAndRank:
    def test_assess_headline_states_direction_growth_and_trust(self, tmp_path: Path) -> None:
        summary = _build(tmp_path, question_type="assess", projects=["uk"])
        headline = summary.verdict.headline
        assert headline.startswith("The attention share of «astronomy» in uk.wikipedia is growing")
        assert summary.happening[1] == (
            "Attention share, last 12 months vs the 12 before: uk.wikipedia +21%."
        )
        assert [c.id for c in summary.charts] == ["main", "change"]
        assert [p.title for p in summary.charts[0].panels] == ["uk.wikipedia"]
        assert (summary.charts[0].reference_y, summary.charts[1].reference_y) == (100.0, 0.0)
        assert summary.decision is not None
        assert summary.decision.lines == []  # one audience: the answer says it all

    def test_rank_rows_have_rationales_and_research_suggestions(self, tmp_path: Path) -> None:
        summary = _build(tmp_path, question_type="rank")
        assert [r.rank for r in summary.ranking] == [1, 2, 3]
        assert summary.ranking[0].project == "uk.wikipedia"
        assert "attention share +21%" in summary.ranking[0].rationale
        assert summary.ranking[-1].rationale == "insufficient data for ranking"
        assert any(step.startswith("Research next") for step in summary.next_steps)
        assert summary.charts[-1].id == "change"  # scores are in the ranking table


def test_rank_headline_admits_that_every_edition_declines(tmp_path: Path) -> None:
    world = astronomy_world()
    for project, title, base in (
        (WikiProject("uk"), "Астрономія", 6000.0),
        (WikiProject("cs"), "Astronomie", 4000.0),
    ):
        world.pageviews.set_article(
            project, title, {m: base * (0.97**i) for i, m in enumerate(world.months)}
        )
    summary = _build(tmp_path, question_type="rank", projects=["uk", "cs"], world=world)
    assert summary.verdict.headline.startswith("The attention share is falling in every edition")


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
