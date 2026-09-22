"""CLI commands against the fake world: JSON output and exit codes."""

from __future__ import annotations

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

    def test_schema_violation_names_the_field(self, tmp_path: Path, fakes: Container) -> None:
        bad = {**REQUEST, "projects": []}
        code, payload = _invoke("run", str(_write_request(tmp_path, bad)))
        assert code == 2
        assert "projects" in str(payload["error"])

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
    def test_resolve_lists_bundles(self, tmp_path: Path, fakes: Container) -> None:
        code, payload = _invoke("resolve", str(_write_request(tmp_path, REQUEST)))
        assert code == 0
        topics = payload["topics"]
        assert isinstance(topics, list)
        assert topics[0]["qid"] == "Q333"
        assert {b["project"] for b in topics[0]["bundles"]} == {"uk.wikipedia", "cs.wikipedia"}

    def test_runs_diff_and_render_work_on_saved_runs(
        self, tmp_path: Path, fakes: Container
    ) -> None:
        request = _write_request(tmp_path, REQUEST)
        _, first = _invoke("run", str(request))
        longer = {**REQUEST, "period": {"start": "2025-03", "end": "2026-08"}}
        _, second = _invoke("run", str(_write_request(tmp_path, longer, "second.json")))

        code, listing = _invoke("runs", "astro")
        assert code == 0
        runs = listing["runs"]
        assert isinstance(runs, list)
        assert len(runs) == 2

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
