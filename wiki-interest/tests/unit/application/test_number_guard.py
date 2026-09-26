"""The report is written only when every number of its text is a field of the result."""

# ruff: noqa: RUF001  -- Ukrainian text in the fixtures is intentional.

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fakes import astronomy_world, fake_container
from wiki_interest.application.narrative_check import check_narrative
from wiki_interest.application.number_guard import check_report_numbers, report_number_problems
from wiki_interest.application.runs import load_summary
from wiki_interest.application.summary_builder import RunContext
from wiki_interest.contracts.narrative import Facts, Narrative, Paragraph
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.errors import RenderError


def _run(tmp_path: Path, language: str = "uk") -> Path:
    request = AnalysisRequest.model_validate(
        {
            "question_type": "compare",
            "topics": [{"query": "astronomy", "query_language": "en", "id": "astronomy"}],
            "projects": ["uk", "cs"],
            "period": {"start": "2024-09", "end": "2026-08"},
            "report": {"language": language},
            "session": "astro",
        }
    )
    run_dir = tmp_path / "runs" / "astro" / "r1"
    context = RunContext("r1", "astro", run_dir, datetime(2026, 9, 22, tzinfo=UTC))
    fake_container(astronomy_world(), tmp_path).pipeline().run(request, context)
    return run_dir


def test_the_code_s_own_report_passes(tmp_path: Path) -> None:
    summary = load_summary(_run(tmp_path))
    assert summary.verdicts
    assert report_number_problems(summary) == []


def test_a_number_nobody_computed_stops_the_render(tmp_path: Path) -> None:
    summary = load_summary(_run(tmp_path))
    broken = summary.model_copy(
        update={"happening": [*summary.happening, "Статтю відкривають 123 456 разів на місяць."]}
    )
    problems = report_number_problems(broken)
    assert len(problems) == 1
    assert "123 456" in problems[0]
    with pytest.raises(RenderError, match="not in the result"):
        check_report_numbers(broken)


def test_rounding_as_written_is_allowed(tmp_path: Path) -> None:
    summary = load_summary(_run(tmp_path))
    ru = next(v for v in summary.verdicts if v.project == "uk.wikipedia")
    assert ru.level_end is not None
    rounded = f"Частка уваги близько {round(ru.level_end)} на мільйон."
    fine = summary.model_copy(update={"happening": [rounded]})
    assert report_number_problems(fine) == []


def test_the_single_term_for_the_share_is_required(tmp_path: Path) -> None:
    run_dir = _run(tmp_path)
    facts = Facts.model_validate_json((run_dir / "facts.json").read_text(encoding="utf-8"))
    text = Narrative(
        language="uk",
        story=[
            Paragraph(
                text="Обсяг уваги до астрономії в українській Вікіпедії зростає.",
                uses=["trend:astronomy/uk"],
            )
        ],
        meaning=Paragraph(text="Обирати українську.", uses=["recommendation:astronomy"]),
        limits="Перегляди показують інтерес, а не готовність платити.",
    )
    messages = [p.message for p in check_narrative(facts, text)]
    assert any("write 'частка уваги'" in m for m in messages)
