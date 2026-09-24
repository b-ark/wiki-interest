"""CLI commands against the fake world: JSON output and exit codes."""

from __future__ import annotations

import codecs
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fakes import astronomy_world, fake_container
from wiki_interest.cli import app as cli
from wiki_interest.cli.container import Container

REQUEST: dict[str, object] = {
    "question_type": "compare",
    "topics": [{"query": "astronomy", "query_language": "en", "id": "astronomy"}],
    "projects": ["uk", "cs"],
    "period": {"start": "2024-09", "end": "2026-08"},
    "report": {"language": "en"},
    "session": "astro",
}


@pytest.fixture
def fakes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Container:
    container = fake_container(astronomy_world(), tmp_path)
    monkeypatch.setattr(cli, "build_container", lambda: container)
    return container


def _write_request(
    tmp_path: Path, data: dict[str, object] | str, name: str = "request.json"
) -> Path:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def _invoke(*args: str) -> tuple[int, dict[str, object]]:
    result = CliRunner().invoke(cli.app, list(args))
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:  # pragma: no cover - diagnostic aid
        pytest.fail(f"stdout was not JSON (exit {result.exit_code}):\n{result.output}")
    return result.exit_code, payload


class TestRun:
    def test_success_prints_paths_and_exits_zero(self, tmp_path: Path, fakes: Container) -> None:
        code, payload = _invoke("run", str(_write_request(tmp_path, REQUEST)))
        assert code == 0, payload
        assert payload["status"] == "ok"
        assert Path(str(payload["summary_md"])).exists()
        assert Path(str(payload["report_pdf"])).exists()
        assert str(payload["run_dir"]).startswith(str(fakes.settings.runs_dir / "astro"))

    def test_session_override_and_runs_dir_option(self, tmp_path: Path, fakes: Container) -> None:
        out = tmp_path / "elsewhere"
        code, payload = _invoke(
            "run",
            str(_write_request(tmp_path, REQUEST)),
            "--session",
            "other",
            "--runs-dir",
            str(out),
        )
        assert code == 0
        assert str(payload["run_dir"]).startswith(str(out / "other"))

    def test_invalid_json_is_exit_two_with_hint(self, tmp_path: Path, fakes: Container) -> None:
        code, payload = _invoke("run", str(_write_request(tmp_path, "{not json")))
        assert code == 2
        assert "not valid JSON" in str(payload["error"])
        assert "request-schema" in str(payload["hint"])

    def test_request_written_with_a_byte_order_mark_is_accepted(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        path = tmp_path / "bom.json"
        path.write_bytes(codecs.BOM_UTF8 + json.dumps(REQUEST).encode("utf-8"))
        code, payload = _invoke("run", str(path))
        assert code == 0, payload

    def test_schema_violation_names_the_field(self, tmp_path: Path, fakes: Container) -> None:
        bad = {**REQUEST, "projects": []}
        code, payload = _invoke("run", str(_write_request(tmp_path, bad)))
        assert code == 2
        assert "projects" in str(payload["error"])

    def test_topic_field_at_the_top_level_says_where_it_goes(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        misplaced = {**REQUEST, "query_language": "pl"}
        code, payload = _invoke("run", str(_write_request(tmp_path, misplaced)))
        assert code == 2
        assert "topics[].query_language" in str(payload["hint"])

    def test_missing_file_is_exit_two(self, tmp_path: Path, fakes: Container) -> None:
        code, payload = _invoke("run", str(tmp_path / "nope.json"))
        assert code == 2
        assert "not found" in str(payload["error"]).lower()

    def test_ambiguous_topic_is_exit_three_with_candidates(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        ambiguous = {**REQUEST, "topics": [{"query": "astro", "id": "astro"}]}
        code, payload = _invoke("run", str(_write_request(tmp_path, ambiguous)))
        assert code == 3
        clarification = payload["clarification"]
        assert isinstance(clarification, dict)
        assert {c["qid"] for c in clarification["candidates"]} == {"Q333", "Q999"}

    def test_unexpected_exception_is_exit_five(
        self, tmp_path: Path, fakes: Container, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom() -> Container:
            raise RuntimeError("wiring broke")

        monkeypatch.setattr(cli, "build_container", boom)
        code, payload = _invoke("run", str(_write_request(tmp_path, REQUEST)))
        assert code == 5
        assert "wiring broke" in str(payload["error"])


class TestOtherCommands:
    def test_diff_and_render_work_on_saved_runs(self, tmp_path: Path, fakes: Container) -> None:
        request = _write_request(tmp_path, REQUEST)
        _, first = _invoke("run", str(request))
        longer = {**REQUEST, "period": {"start": "2025-03", "end": "2026-08"}}
        _, second = _invoke("run", str(_write_request(tmp_path, longer, "second.json")))

        code, diff = _invoke("diff", str(first["run_dir"]), str(second["run_dir"]))
        assert code == 0
        changes = diff["request_changes"]
        assert isinstance(changes, dict)
        assert "period" in changes

        Path(str(first["report_pdf"])).unlink()
        code, rendered = _invoke("render", str(first["run_dir"]))
        assert code == 0
        assert Path(str(rendered["report_pdf"])).exists()

    def test_diff_with_missing_run_is_exit_two(self, tmp_path: Path, fakes: Container) -> None:
        code, payload = _invoke("diff", str(tmp_path / "a"), str(tmp_path / "b"))
        assert code == 2
        assert "not found" in str(payload["error"]).lower()


class TestRenderNarrative:
    def _run(self, tmp_path: Path) -> dict[str, object]:
        code, payload = _invoke("run", str(_write_request(tmp_path, REQUEST)))
        assert code == 0, payload
        return payload

    @staticmethod
    def _template(payload: dict[str, object]) -> dict[str, object]:
        facts = json.loads(Path(str(payload["facts_json"])).read_text(encoding="utf-8"))
        template: dict[str, object] = facts["template"]
        return template

    def test_run_points_to_the_facts_with_the_template(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        payload = self._run(tmp_path)
        assert self._template(payload)["headline"]

    def test_the_template_is_accepted_and_returns_the_chat_answer(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        payload = self._run(tmp_path)
        path = _write_request(tmp_path, self._template(payload), "narrative.json")
        code, rendered = _invoke("render", str(payload["run_dir"]), "--narrative", str(path))
        assert code == 0, rendered
        assert rendered["status"] == "accepted"
        assert rendered["chat_answer"]
        assert Path(str(rendered["chat_brief"])).is_file()

    def test_a_render_from_inside_the_run_gives_the_full_path_to_the_pdf(
        self, tmp_path: Path, fakes: Container, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        payload = self._run(tmp_path)
        path = _write_request(tmp_path, self._template(payload), "narrative.json")
        monkeypatch.chdir(str(payload["run_dir"]))
        code, rendered = _invoke("render", ".", "--narrative", str(path))
        assert code == 0, rendered
        pdf = Path(str(rendered["report_pdf"]))
        assert pdf.is_absolute()
        assert str(pdf) in str(rendered["chat_answer"])

    def test_a_rejected_text_is_exit_two_with_problems(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        payload = self._run(tmp_path)
        template = self._template(payload)
        path = _write_request(tmp_path, {**template, "headline": "Up 21 %."}, "narrative.json")
        code, rendered = _invoke("render", str(payload["run_dir"]), "--narrative", str(path))
        assert code == 2
        assert rendered["status"] == "rejected"
        assert rendered["problems"]

    def test_a_file_off_the_schema_is_exit_two_with_a_hint(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        payload = self._run(tmp_path)
        path = _write_request(tmp_path, {"headline": "x"}, "narrative.json")
        code, rendered = _invoke("render", str(payload["run_dir"]), "--narrative", str(path))
        assert code == 2
        assert "narrative schema" in str(rendered["error"])
        assert "facts.json's template" in str(rendered["hint"])
