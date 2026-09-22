"""Agent summary: short, structured, localised, with a clarification branch."""

from pathlib import Path

import pytest

from fixtures.summaries import example_summary
from wiki_interest.adapters.agent_summary import AgentSummaryRenderer
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

MAX_LINES_FOR_TWO_PROJECT_COMPARE = 60


def _build(summary: AnalysisSummary) -> str:
    return AgentSummaryRenderer(Translator(summary.request.report.language)).build(summary)


def test_english_summary_has_the_six_sections_in_order(compare_summary: AnalysisSummary) -> None:
    text = _build(compare_summary)
    positions = [
        text.index(marker)
        for marker in (
            "**Answer:** Interest in intermittent fasting is growing faster",
            "## Key numbers",
            "## How much to trust this",
            "## Caveats",
            "## What can be refined",
            "## Articles analysed",
            "## Files",
        )
    ]
    assert positions == sorted(positions)


def test_summary_is_short_for_two_project_compare(compare_summary: AnalysisSummary) -> None:
    assert len(_build(compare_summary).splitlines()) <= MAX_LINES_FOR_TWO_PROJECT_COMPARE


def test_trust_lines_show_level_and_top_reasons(compare_summary: AnalysisSummary) -> None:
    text = _build(compare_summary)
    line = next(ln for ln in text.splitlines() if "cs.wikipedia: medium" in ln)
    assert line.startswith("- **Přerušovaný půst — cs.wikipedia: medium.**")
    assert "2 months without data (8% of the period)" in line
    assert line.count(";") == 2, "three reasons separated by semicolons"


def test_artifacts_are_listed_with_absolute_paths(compare_summary: AnalysisSummary) -> None:
    text = _build(compare_summary)
    assert "- report.pdf: `/runs/fasting-uk-cs/20260922-120000-abcd/report.pdf`" in text
    assert "- intermittent-fasting-uk-trend.png: `/runs/fasting-uk-cs/" in text


def test_bundles_are_compact(compare_summary: AnalysisSummary) -> None:
    text = _build(compare_summary)
    assert (
        "- **uk.wikipedia**: found, articles: 2 (related: 1) — "
        "Інтервальне голодування (main, 1.00); "
        "Голодування (related, 0.50)" in text
    )


def test_ukrainian_summary_is_localised() -> None:
    text = _build(example_summary(language="uk"))
    assert "**Відповідь:**" in text
    assert "## Наскільки можна довіряти" in text
    assert "## Застереження" in text
    assert "## Що можна уточнити" in text
    assert "## Файли" in text
    assert "висока.**" in text
    assert "Answer" not in text


def test_rank_summary_includes_ranking_table() -> None:
    text = _build(example_summary(question_type="rank"))
    assert "| # | Topic | Edition | Score | Profile | Reliability | Why |" in text
    assert "| 3 | Post przerywany | pl.wikipedia | 0.22 | insufficient data | low |" in text
    assert (
        "- **pl.wikipedia**: found via search, articles: 1 (related: 0) — "
        "Post przerywany (main, 1.00)" in text
    )


def test_clarification_branch_shows_question_and_candidates_only() -> None:
    text = _build(example_summary(with_clarification=True))
    assert "## Clarification needed" in text
    assert '**Which entity do you mean by "intermittent fasting"?**' in text
    assert "1. **intermittent fasting** (Q1666254) — diet" in text
    assert "3. **Intermittent Fasting (film)** (Q99999999)" in text
    assert "_Ask the user which entity they mean" in text
    assert "## Key numbers" not in text
    assert "## Files" not in text


def test_clarification_without_details_falls_back_to_headline() -> None:
    summary = example_summary(with_clarification=True).model_copy(update={"clarification": None})
    text = _build(summary)
    assert "## Clarification needed" in text
    assert summary.verdict.headline in text


def test_empty_optional_sections_are_skipped() -> None:
    summary = example_summary().model_copy(
        update={"limitations": [], "next_steps": [], "resolution": [], "reliability": []}
    )
    text = _build(summary)
    for heading in ("## Caveats", "## What can be refined", "## Articles analysed", "## How much"):
        assert heading not in text


def test_render_writes_file_and_is_deterministic(
    compare_summary: AnalysisSummary, tmp_path: Path
) -> None:
    renderer = AgentSummaryRenderer(Translator("en"))
    first = renderer.render(compare_summary, [], tmp_path / "a" / "summary.md")
    second = renderer.render(compare_summary, [], tmp_path / "b" / "summary.md")
    assert first.read_bytes() == second.read_bytes()
    assert b"\r\n" not in first.read_bytes()


def test_unwritable_output_raises_render_error(
    compare_summary: AnalysisSummary, tmp_path: Path
) -> None:
    blocker = tmp_path / "summary.md"
    blocker.mkdir()
    with pytest.raises(RenderError):
        AgentSummaryRenderer(Translator("en")).render(compare_summary, [], blocker)


def test_not_found_bundle_is_reported_honestly() -> None:
    summary = example_summary(question_type="rank")
    topic = summary.resolution[0]
    bundles = [
        b.model_copy(update={"status": "not_found", "articles": []})
        if b.project == "pl.wikipedia"
        else b
        for b in topic.bundles
    ]
    summary = summary.model_copy(
        update={"resolution": [topic.model_copy(update={"bundles": bundles})]}
    )
    text = _build(summary)
    assert "- **pl.wikipedia**: not found" in text
