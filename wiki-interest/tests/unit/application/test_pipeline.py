"""End-to-end pipeline runs against the fake world: files, exit codes, clarification, render."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader

from fakes import astronomy_world, fake_container
from wiki_interest.application.pipeline import Pipeline
from wiki_interest.application.runs import load_summary
from wiki_interest.application.summary_builder import RunContext
from wiki_interest.contracts.request import AnalysisRequest


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


def _pipeline(tmp_path: Path) -> Pipeline:
    world = astronomy_world()
    container = fake_container(world, tmp_path)
    return container.pipeline()


class TestSuccessfulRun:
    def test_writes_every_artifact_and_returns_exit_zero(self, tmp_path: Path) -> None:
        outcome = _pipeline(tmp_path).run(_request(), _context(tmp_path))
        assert outcome.exit_code == 0
        run_dir = tmp_path / "runs" / "astro" / "run-1"
        assert (run_dir / "summary.json").exists()
        assert (run_dir / "summary.md").exists()
        assert (run_dir / "report.md").exists()
        assert (run_dir / "report.pdf").exists()
        pngs = sorted((run_dir / "charts").glob("*.png"))
        assert [p.name for p in pngs] == ["growth.png", "interest-over-time.png"]
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

    def test_summary_md_is_in_the_report_language_with_numbers(self, tmp_path: Path) -> None:
        outcome = _pipeline(tmp_path).run(_request(), _context(tmp_path))
        text = Path(outcome.summary.artifacts.summary_md).read_text(encoding="utf-8")
        assert "Відповідь" in text or "відповідь" in text.lower()
        assert "uk.wikipedia" in text
        assert "report.pdf" in text

    def test_default_period_is_the_last_24_full_months(self, tmp_path: Path) -> None:
        outcome = _pipeline(tmp_path).run(_request(period=None), _context(tmp_path))
        assert outcome.summary.period.model_dump(mode="json") == {
            "start": "2024-09",
            "end": "2026-08",
        }

    def test_formats_restrict_which_reports_are_written(self, tmp_path: Path) -> None:
        request = _request(report={"language": "en", "formats": ["md"]})
        outcome = _pipeline(tmp_path).run(request, _context(tmp_path))
        run_dir = Path(outcome.summary.artifacts.run_dir)
        assert not (run_dir / "report.pdf").exists()
        assert (run_dir / "report.md").exists()
        assert outcome.summary.artifacts.report_pdf is None

    def test_assess_and_rank_produce_their_own_charts(self, tmp_path: Path) -> None:
        assess = _pipeline(tmp_path).run(
            _request(question_type="assess", projects=["uk"]), _context(tmp_path, "assess")
        )
        assert [c.kind for c in assess.summary.charts] == ["trend", "bars"]
        rank = _pipeline(tmp_path).run(_request(question_type="rank"), _context(tmp_path, "rank"))
        assert [c.kind for c in rank.summary.charts] == ["lines", "bars", "bars"]
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
