"""End-to-end pipeline runs against the fake world: files, exit codes, clarification, render."""

from __future__ import annotations

import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader

from fakes import FakeEntity, FakePage, astronomy_world, fake_container
from fixtures.summaries import example_summary
from wiki_interest.application.pipeline import Pipeline, _with_main_charts
from wiki_interest.application.runs import load_summary
from wiki_interest.application.summary_builder import RunContext
from wiki_interest.contracts.charts import ChartSeries, ChartSpec
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.domain.models import WikiProject
from wiki_interest.i18n import Translator


def _request(**overrides: object) -> AnalysisRequest:
    data: dict[str, object] = {
        "question_type": "compare",
        "topics": [{"query": "astronomy", "query_language": "en", "id": "astronomy"}],
        "projects": ["uk", "cs"],
        "period": {"start": "2024-09", "end": "2026-08"},
        "report": {"language": "uk"},
        "session": "astro",
    }
    data.update(overrides)
    return AnalysisRequest.model_validate(data)


def _context(tmp_path: Path, run_id: str = "run-1") -> RunContext:
    return RunContext(
        run_id=run_id,
        session="astro",
        run_dir=tmp_path / "runs" / "astro" / run_id,
        generated_at=datetime(2026, 9, 22, 12, 0, tzinfo=UTC),
    )


def _pipeline(tmp_path: Path, *, draw_charts: bool = False) -> Pipeline:
    world = astronomy_world()
    container = fake_container(world, tmp_path, draw_charts=draw_charts)
    return container.pipeline()


class TestSuccessfulRun:
    def test_writes_every_artifact_and_returns_exit_zero(self, tmp_path: Path) -> None:
        outcome = _pipeline(tmp_path, draw_charts=True).run(_request(), _context(tmp_path))
        assert outcome.exit_code == 0
        run_dir = tmp_path / "runs" / "astro" / "run-1"
        assert (run_dir / "summary.json").exists()
        assert (run_dir / "summary.md").exists()
        assert (run_dir / "report.pdf").exists()
        pngs = sorted((run_dir / "charts").glob("*.png"))
        assert {p.stem for p in pngs} == {c.id for c in outcome.summary.charts}
        assert "share" in {p.stem for p in pngs}
        assert len(PdfReader(run_dir / "report.pdf").pages) == 1
        payload = outcome.to_dict()
        assert payload["status"] == "ok"
        assert payload["report_pdf"] == str(run_dir / "report.pdf")
        charts = payload["charts"]
        assert isinstance(charts, list)
        assert set(charts) == {str(p) for p in pngs}

    def test_summary_json_is_the_document_the_pipeline_returned(self, tmp_path: Path) -> None:
        outcome = _pipeline(tmp_path).run(_request(), _context(tmp_path))
        saved = load_summary(Path(outcome.summary.artifacts.run_dir))
        assert saved == outcome.summary
        assert saved.provenance.data_through == "2026-08"
        assert {m.project for m in saved.metrics} == {"uk.wikipedia", "cs.wikipedia"}

    def test_a_language_without_a_catalog_asks_the_agent_for_its_labels(
        self, tmp_path: Path
    ) -> None:
        request = _request(report={"language": "de"})
        outcome = _pipeline(tmp_path).run(request, _context(tmp_path))
        text = Path(outcome.summary.artifacts.summary_md).read_text(encoding="utf-8")
        # The template stays English until the agent's narrative brings the translations.
        assert "**Answer:**" in text
        assert "uk.wikipedia" in text
        assert "report.pdf" in text
        facts = json.loads((Path(outcome.summary.artifacts.run_dir) / "facts.json").read_text())
        assert facts["language"] == "de"
        assert "report.happening" in facts["ui"]

    def test_default_period_is_the_last_24_full_months(self, tmp_path: Path) -> None:
        outcome = _pipeline(tmp_path).run(_request(period=None), _context(tmp_path))
        assert outcome.summary.period.model_dump(mode="json") == {
            "start": "2024-09",
            "end": "2026-08",
        }

    def test_assess_and_rank_produce_their_own_charts(self, tmp_path: Path) -> None:
        assess = _pipeline(tmp_path).run(
            _request(question_type="assess", projects=["uk"]), _context(tmp_path, "assess")
        )
        assert [c.kind for c in assess.summary.charts] == ["share_years", "audience_years"]
        rank = _pipeline(tmp_path).run(_request(question_type="rank"), _context(tmp_path, "rank"))
        # Two editions of one topic: the main chart and the views by year hold both, whatever
        # the question.
        assert [c.kind for c in rank.summary.charts] == ["share_years", "audience_years"]
        assert [line.label for line in rank.summary.charts[0].share.lines] == ["uk", "cs"]  # type: ignore[union-attr]
        assert [r.rank for r in rank.summary.ranking] == [1, 2]
        assert rank.summary.ranking[0].project == "uk.wikipedia"


class TestClarification:
    def test_ambiguous_topic_stops_with_exit_three_and_a_question(self, tmp_path: Path) -> None:
        request = _request(topics=[{"query": "astro", "query_language": "en", "id": "astro"}])
        outcome = _pipeline(tmp_path).run(request, _context(tmp_path))
        assert outcome.exit_code == 3
        assert outcome.summary.status == "needs_clarification"
        assert outcome.summary.clarification is not None
        qids = {c.qid for c in outcome.summary.clarification.candidates}
        assert qids == {"Q333", "Q999"}
        run_dir = tmp_path / "runs" / "astro" / "run-1"
        summary_md = (run_dir / "summary.md").read_text(encoding="utf-8")
        assert "Q333" in summary_md
        assert not (run_dir / "report.pdf").exists()
        payload = outcome.to_dict()
        assert payload["exit_code"] == 3
        clarification = payload["clarification"]
        assert isinstance(clarification, dict)
        assert clarification["topic_id"] == "astro"
        assert json.dumps(payload)  # serialisable for stdout

    def test_pinned_qid_resolves_the_ambiguity(self, tmp_path: Path) -> None:
        request = _request(
            topics=[{"query": "astro", "query_language": "en", "id": "astro", "qid": "Q333"}]
        )
        outcome = _pipeline(tmp_path).run(request, _context(tmp_path))
        assert outcome.exit_code == 0


class TestRender:
    def test_render_regenerates_reports_from_summary_json(self, tmp_path: Path) -> None:
        pipeline = _pipeline(tmp_path)
        outcome = pipeline.run(_request(), _context(tmp_path))
        run_dir = Path(outcome.summary.artifacts.run_dir)
        (run_dir / "report.pdf").unlink()
        rendered = pipeline.render(load_summary(run_dir), run_dir)
        assert (run_dir / "report.pdf").exists()
        assert rendered.artifacts == outcome.summary.artifacts


def _world_with_polish_gap(tmp_path: Path) -> Pipeline:
    """The fixture world plus a Polish "Nauka" (science), the item astronomy is a subclass of."""
    world = astronomy_world()
    pl = WikiProject("pl")
    world.wikidata.entities["Q333"].claims["P279"] = ["Q336"]
    world.wikidata.add(FakeEntity("Q336", {"en": "science"}, sitelinks={pl: "Nauka"}))
    world.mediawiki.add_page(pl, FakePage("Nauka", qid="Q336"))
    world.pageviews.set_article(
        pl, "Nauka", {m: 5000.0 - 20.0 * i for i, m in enumerate(world.months)}
    )
    world.pageviews.set_aggregate(pl, dict.fromkeys(world.months, 80000000.0))
    return fake_container(world, tmp_path).pipeline()


class TestMissingArticle:
    def test_stops_before_loading_series_and_lists_the_options(self, tmp_path: Path) -> None:
        pipeline = _world_with_polish_gap(tmp_path)
        outcome = pipeline.run(_request(projects=["uk", "pl"]), _context(tmp_path))
        assert outcome.exit_code == 3
        clarification = outcome.summary.clarification
        assert clarification is not None
        assert clarification.kind == "missing_article"
        (gap,) = clarification.gaps
        assert gap.project == "pl.wikipedia"
        assert gap.qid == "Q333"
        assert [(o.kind, o.title) for o in gap.options] == [("broader", "Nauka"), ("skip", None)]
        assert outcome.summary.artifacts.report_pdf is None
        assert outcome.summary.series == []
        payload = outcome.to_dict()
        details = payload["clarification"]
        assert isinstance(details, dict)
        assert details["gaps"][0]["options"][0]["choose"] == {
            "pl.wikipedia": {"title": "Nauka", "kind": "broader"}
        }
        assert json.dumps(payload)
        run_dir = Path(outcome.summary.artifacts.run_dir)
        text = (run_dir / "summary.md").read_text(encoding="utf-8")
        # The user sees the broader article with a link to open it before choosing.
        assert "Тему охоплюють ширші статті цього розділу:" in text  # written, not translated
        assert "[Nauka](https://pl.wikipedia.org/wiki/Nauka)" in text
        assert gap.options[0].url == "https://pl.wikipedia.org/wiki/Nauka"
        assert gap.options[1].url is None
        assert not (run_dir / "report.pdf").exists()

    def test_the_question_to_the_user_is_composed_by_the_code(self, tmp_path: Path) -> None:
        """In English it is ready at once: the agent sends it word for word."""
        pipeline = _world_with_polish_gap(tmp_path)
        request = _request(projects=["uk", "pl"], report={"language": "en"})
        outcome = pipeline.run(request, _context(tmp_path))
        clarification = outcome.summary.clarification
        assert clarification is not None
        assert clarification.ui == {}
        assert clarification.ask_user is not None
        assert 'pl.wikipedia has no article on "astronomy".' in clarification.ask_user
        assert "1. [Nauka](https://pl.wikipedia.org/wiki/Nauka), the wider subject" in (
            clarification.ask_user
        )
        assert clarification.ask_user.endswith(
            "Which option should I use for pl.wikipedia? Reply with its number."
        )
        details = outcome.to_dict()["clarification"]
        assert isinstance(details, dict)
        assert details["ask_user"] == clarification.ask_user

    def test_another_language_gets_the_question_after_its_labels(self, tmp_path: Path) -> None:
        """The labels are asked for first; with them the question reads in the user's language."""
        pipeline = _world_with_polish_gap(tmp_path)
        request = _request(projects=["uk", "pl"], report={"language": "de"})
        outcome = pipeline.run(request, _context(tmp_path))
        clarification = outcome.summary.clarification
        assert clarification is not None
        assert clarification.ask_user is None
        assert "gap.question" in clarification.ui
        assert "translated into de" in clarification.question
        run_dir = Path(outcome.summary.artifacts.run_dir)
        labels = {key: f"DE {text}" for key, text in clarification.ui.items()}
        asked = pipeline.ask(run_dir, labels)
        assert asked.status == "accepted"
        question = load_summary(run_dir).clarification
        assert question is not None
        assert question.ask_user is not None
        assert question.ask_user.startswith("DE Topic:")
        assert "DE Which option should I use" in question.ask_user
        assert asked.to_dict()["ask_user"] == question.ask_user

    def test_labels_that_lost_a_placeholder_are_sent_back(self, tmp_path: Path) -> None:
        pipeline = _world_with_polish_gap(tmp_path)
        request = _request(projects=["uk", "pl"], report={"language": "de"})
        outcome = pipeline.run(request, _context(tmp_path))
        clarification = outcome.summary.clarification
        assert clarification is not None
        labels = dict(clarification.ui)
        labels["gap.question"] = "Kein Artikel."
        del labels["ask.which"]
        asked = pipeline.ask(Path(outcome.summary.artifacts.run_dir), labels)
        assert asked.status == "rejected"
        assert asked.exit_code == 2
        assert any("ui.ask.which: missing" in p for p in asked.problems)
        assert any("{project}, {topic}" in p for p in asked.problems)

    def test_the_session_remembers_the_labels(self, tmp_path: Path) -> None:
        """A second question in the same conversation needs no translation round."""
        pipeline = _world_with_polish_gap(tmp_path)
        request = _request(projects=["uk", "pl"], report={"language": "de"})
        first = pipeline.run(request, _context(tmp_path)).summary.clarification
        assert first is not None
        run_dir = tmp_path / "runs" / "astro" / "run-1"
        pipeline.ask(run_dir, {key: f"DE {text}" for key, text in first.ui.items()})
        second = pipeline.run(request, _context(tmp_path, "run-2")).summary.clarification
        assert second is not None
        assert second.ui == {}
        assert second.ask_user is not None

    def test_the_chosen_substitute_is_measured_and_named_but_never_leads(
        self, tmp_path: Path
    ) -> None:
        pipeline = _world_with_polish_gap(tmp_path)
        request = _request(
            projects=["cs", "pl"],
            topics=[
                {
                    "query": "astronomy",
                    "query_language": "en",
                    "id": "astronomy",
                    "substitutes": {"pl": {"title": "Nauka", "kind": "broader"}},
                }
            ],
            report={"language": "en"},
        )
        outcome = pipeline.run(request, _context(tmp_path))
        assert outcome.exit_code == 0
        summary = outcome.summary
        pl_reliability = next(r for r in summary.reliability if r.project == "pl.wikipedia")
        assert pl_reliability.level == "low"
        # "Nauka" has far more views per million than Czech astronomy, yet the headline is
        # about the topic, so it names cs; the substitute is not compared with it.
        assert "Czech Wikipedia" in summary.verdict.headline
        assert "Polish" not in summary.verdict.headline
        assert not any(o.kind == "sections" for o in summary.observations)
        text = Path(summary.artifacts.summary_md).read_text(encoding="utf-8")
        assert "pl.wikipedia (Nauka)" in text
        assert 'the broader article "Nauka"' in text

    def test_skip_runs_without_the_edition(self, tmp_path: Path) -> None:
        pipeline = _world_with_polish_gap(tmp_path)
        request = _request(
            projects=["uk", "pl"],
            topics=[
                {
                    "query": "astronomy",
                    "query_language": "en",
                    "id": "astronomy",
                    "substitutes": {"pl": "skip"},
                }
            ],
        )
        outcome = pipeline.run(request, _context(tmp_path))
        assert outcome.exit_code == 0
        pl_row = next(r for r in outcome.summary.comparison if r.project == "pl.wikipedia")
        assert pl_row.views_avg is None


class TestTopicQuestions:
    def test_unknown_topic_stops_with_a_request_for_a_link(self, tmp_path: Path) -> None:
        request = _request(topics=[{"query": "zzz", "query_language": "en", "id": "z"}])
        outcome = _pipeline(tmp_path).run(request, _context(tmp_path))
        assert outcome.exit_code == 3
        assert outcome.summary.clarification is not None
        assert outcome.summary.clarification.kind == "topic_not_found"
        payload = outcome.to_dict()
        assert payload["clarification"] == {
            "kind": "topic_not_found",
            "topic_id": "z",
            "query": "zzz",
            "question": outcome.summary.clarification.question,
        }

    def test_articles_found_only_by_search_are_offered_with_a_way_out(self, tmp_path: Path) -> None:
        world = astronomy_world()
        world.mediawiki.add_search(WikiProject("uk"), "зоряне небо", ["Телескоп"])
        pipeline = fake_container(world, tmp_path).pipeline()
        topic = {"query": "зоряне небо", "query_language": "uk", "id": "sky"}
        outcome = pipeline.run(_request(topics=[topic]), _context(tmp_path))
        assert outcome.exit_code == 3
        clarification = outcome.to_dict()["clarification"]
        assert isinstance(clarification, dict)
        assert clarification["kind"] == "ambiguous_topic"
        assert clarification["from_search"] is True
        assert [c["qid"] for c in clarification["candidates"]] == ["Q4213"]
        # The agent reads the question in the output: it says what to do when none fits.
        assert "article_url" in clarification["question"]
        assert "any language" in clarification["question"]
        text = Path(outcome.summary.artifacts.summary_md).read_text(encoding="utf-8")
        assert "guesses of a text search" in text
        assert not (tmp_path / "runs" / "astro" / "run-1" / "report.pdf").exists()

    def test_successful_run_names_the_analysed_entity(self, tmp_path: Path) -> None:
        outcome = _pipeline(tmp_path).run(_request(), _context(tmp_path))
        topics = outcome.to_dict()["topics"]
        assert isinstance(topics, list)
        assert topics[0]["qid"] == "Q333"
        assert topics[0]["description"] == "natural science of celestial objects"
        text = Path(outcome.summary.artifacts.summary_md).read_text(encoding="utf-8")
        assert "(Q333)" in text


class TestTopicStageOnly:
    def test_stop_after_resolve_writes_the_topic_and_measures_nothing(self, tmp_path: Path) -> None:
        world = astronomy_world()
        container = fake_container(world, tmp_path)
        settings = container.settings.model_copy(update={"stop_after": "resolve"})
        pipeline = dataclasses.replace(container, settings=settings).pipeline()
        outcome = pipeline.run(_request(), _context(tmp_path))
        assert outcome.exit_code == 0
        assert outcome.summary.status == "topic_resolved"
        assert outcome.summary.resolution[0].qid == "Q333"
        assert outcome.summary.series == []
        assert not [c for c in world.pageviews.calls if c[0] == "aggregate"]
        run_dir = Path(outcome.summary.artifacts.run_dir)
        text = (run_dir / "summary.md").read_text(encoding="utf-8")
        assert "(Q333)" in text
        assert not (run_dir / "report.pdf").exists()


class TestSeasonChart:
    """A season takes its chart only when the user asked about timing or the text cites it."""

    @staticmethod
    def _summary(*, cited: list[str], seasonality: str = "auto") -> AnalysisSummary:
        summary = example_summary()
        season = ChartSpec(
            id="season",
            kind="lines",
            size="half",
            title="Months against the usual level",
            y_label="%",
            series=[ChartSeries(label="uk", x=["Jan", "Feb"], y=[10.0, -5.0])],
        )
        report = summary.request.report.model_copy(update={"seasonality": seasonality})
        request = summary.request.model_copy(update={"report": report})
        return summary.model_copy(update={"charts": [season], "cited": cited, "request": request})

    def test_a_season_the_text_does_not_cite_is_not_drawn(self) -> None:
        charts = _with_main_charts(self._summary(cited=[]), Translator("en")).charts
        assert "season" not in [c.id for c in charts]

    def test_a_cited_season_or_a_question_about_timing_is_drawn(self) -> None:
        cited = self._summary(cited=["decision:timing:astronomy/uk"])
        asked = self._summary(cited=[], seasonality="show")
        for summary in (cited, asked):
            assert "season" in [c.id for c in _with_main_charts(summary, Translator("en")).charts]
