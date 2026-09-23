"""Markdown report: every section present, localised, deterministic, charts linked relatively."""

from pathlib import Path

import pytest

from fixtures.summaries import example_summary
from wiki_interest.adapters.markdown_report import (
    MarkdownReportRenderer,
    markdown_table,
    relative_chart_path,
)
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator


def _render(summary: AnalysisSummary, tmp_path: Path) -> str:
    charts = [tmp_path / "charts" / f"{spec.id}.png" for spec in summary.charts]
    charts += [tmp_path / "charts" / f"{spec.id}.svg" for spec in summary.charts]
    renderer = MarkdownReportRenderer(Translator(summary.request.report.language))
    path = renderer.render(summary, charts, tmp_path / "report.md")
    return path.read_text(encoding="utf-8")


def test_english_report_contains_every_section(tmp_path: Path) -> None:
    text = _render(example_summary(), tmp_path)
    for heading in (
        "# Intermittent fasting: uk vs cs",
        "**Question:** Compare interest in intermittent fasting across uk.wikipedia, cs.wikipedia",
        "**Context:** Nutrition app choosing the next localisation",
        "**Period:** 2024-09 – 2026-08",
        "## Answer",
        "| Metric | uk.wikipedia | cs.wikipedia |",
        "| Attention share, last 12 months vs the 12 before | +12% | +32% |",
        "| Do the last 3 months confirm the trend? | yes | no, the share is steady |",
        "## Is the topic growing faster or slower than its Wikipedia?",
        "- cs.wikipedia: article views +27%, edition traffic -5% → the attention share rises",
        "## How robust is this conclusion?",
        "- uk.wikipedia: steady growth of the attention share.",
        "Data: 24 months of data; bursts do not drive the result.",
        "## What this means for the decision",
        "- Next step: confirm the signal for cs.wikipedia with an independent source of demand",
        "## Also worth knowing",
        "## Key numbers",
        "## Charts",
        "## Data checks",
        "## Related articles (context, not counted)",
        "## Articles analysed",
        "## Assumptions and limitations",
        "## About the method",
        "## What can be refined",
        "Sources: https://wikimedia.org/api/rest_v1/metrics/pageviews/",
        "Generated: 2026-09-22 12:00 UTC",
        "Skill version: 0.1.0",
    ):
        assert heading in text, heading


def test_key_numbers_table_is_formatted_in_report_locale(tmp_path: Path) -> None:
    text = _render(example_summary(), tmp_path)
    assert (
        "| Topic | Edition | Article views/month | Attention share, per 1M edition views "
        "| Attention share: change | Article views: change | Edition traffic: change "
        "| Attention share trend | Reliability |"
    ) in text
    assert "| Přerušovaný půst | cs.wikipedia |" in text
    assert "| 5,654 | 117.8 per million | +32% | +27% | -5% | rising | medium |" in text
    assert "1 in" not in text
    assert "*Notes:*" in text
    assert "- Přerušovaný půst (cs.wikipedia): 2 months missing" in text


def test_ukrainian_report_is_localised(tmp_path: Path) -> None:
    text = _render(example_summary(language="uk"), tmp_path)
    assert "## Ключові числа" in text
    assert "## Відповідь" in text
    assert "## Наскільки стійкий цей висновок?" in text
    assert "## Перевірки даних" in text
    assert "### Інтервальне голодування — uk.wikipedia: висока" in text
    assert "- пройдено: 24 місяців даних" in text
    assert "**Період:** 2024-09 – 2026-08" in text
    assert "Джерела:" in text
    assert "+32\u202f%" in text
    assert "Key numbers" not in text


def test_charts_are_embedded_as_relative_png_links_only(tmp_path: Path) -> None:
    text = _render(example_summary(), tmp_path)
    assert (
        "![Article views against edition traffic](charts/intermittent-fasting-per-million.png)"
    ) in text
    assert ".svg" not in text


def test_reliability_lists_failures_before_passes(tmp_path: Path) -> None:
    text = _render(example_summary(question_type="rank"), tmp_path)
    section = text.split("### Post przerywany — pl.wikipedia: low")[1].split("###")[0]
    order = [line.split(":")[0] for line in section.splitlines() if line.startswith("- ")]
    assert order[0] == "- fail"
    assert order[-1] == "- pass"


def test_articles_analysed_show_roles_sources_and_redirects(tmp_path: Path) -> None:
    text = _render(example_summary(question_type="rank"), tmp_path)
    assert "### intermittent fasting (Q1666254)" in text
    assert "**uk.wikipedia** — found" in text
    assert "| Article | Role | Source |" in text
    assert "| Інтервальне голодування (← Інтервальний піст) | main | Wikidata sitelink |" in text
    assert "| Голодування | related | Wikidata relation |" in text
    assert "**pl.wikipedia** — found via search" in text
    assert "| Post przerywany | main | search fallback |" in text


def test_ranking_table_present_only_for_rank(tmp_path: Path) -> None:
    assert "## Ranking" not in _render(example_summary(), tmp_path)
    text = _render(example_summary(question_type="rank"), tmp_path)
    assert "## Ranking" in text
    assert (
        "| 1 | Přerušovaný půst | cs.wikipedia | 0.81 "
        "| large audience, attention share growing | medium |"
    ) in text


def test_empty_sections_are_skipped(tmp_path: Path) -> None:
    summary = example_summary().model_copy(
        update={
            "limitations": [],
            "general_limitations": [],
            "next_steps": [],
            "ranking": [],
            "resolution": [],
            "decision": None,
            "assessments": [],
            "context": [],
        }
    )
    text = _render(summary, tmp_path)
    assert "## Assumptions and limitations" not in text
    assert "## About the method" not in text
    assert "## What can be refined" not in text
    assert "## Articles analysed" not in text
    assert "## What this means" not in text
    assert "## Is the topic growing" not in text
    assert "## Related articles" not in text


def test_no_charts_skips_chart_section(tmp_path: Path) -> None:
    renderer = MarkdownReportRenderer(Translator("en"))
    text = renderer.build(example_summary(), [], tmp_path)
    assert "## Chart" not in text


def test_output_is_deterministic(tmp_path: Path) -> None:
    assert _render(example_summary(), tmp_path / "a") == _render(example_summary(), tmp_path / "b")


def test_unwritable_output_raises_render_error(tmp_path: Path) -> None:
    blocker = tmp_path / "report.md"
    blocker.mkdir()
    with pytest.raises(RenderError):
        MarkdownReportRenderer(Translator("en")).render(example_summary(), [], blocker)


def test_markdown_table_escapes_pipes() -> None:
    lines = markdown_table(["a"], [["x|y"]])
    assert lines == ["| a |", "| --- |", "| x\\|y |"]


def test_relative_chart_path_falls_back_to_absolute_across_drives() -> None:
    chart = Path("Z:/runs/x/charts/c.png") if Path("C:/").exists() else Path("/runs/x/c.png")
    base = Path("C:/other") if Path("C:/").exists() else Path("/srv/other")
    result = relative_chart_path(chart, base)
    assert result.endswith("c.png")
    assert relative_chart_path(Path("/runs/x/charts/c.png"), Path("/runs/x")) == "charts/c.png"


@pytest.mark.parametrize("language", ["ru", "pl", "cs"])
def test_other_languages_render_without_missing_keys(tmp_path: Path, language: str) -> None:
    text = _render(example_summary(language=language), tmp_path)
    assert "{" not in text


def test_not_found_bundle_has_status_line_without_table(tmp_path: Path) -> None:
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
    text = _render(summary, tmp_path)
    assert "**pl.wikipedia** — not found" in text
    assert "| Post przerywany | main |" not in text, "no article table for a not_found bundle"


def test_svg_only_chart_list_is_still_embedded(tmp_path: Path) -> None:
    summary = example_summary()
    renderer = MarkdownReportRenderer(Translator("en"))
    text = renderer.build(summary, [tmp_path / "charts" / "x.svg"], tmp_path)
    assert "## Chart" + chr(10) in text
    assert "![x](charts/x.svg)" in text


def test_title_carries_a_short_description_of_the_topic(tmp_path: Path) -> None:
    summary = example_summary()
    topic = summary.resolution[0].model_copy(update={"description": "diet of timed fasting"})
    request = summary.request.model_copy(
        update={"report": summary.request.report.model_copy(update={"title": None})}
    )
    text = _render(summary.model_copy(update={"resolution": [topic], "request": request}), tmp_path)
    assert text.startswith("# Intermittent fasting — diet of timed fasting: interest on Wikipedia")
    long_topic = topic.model_copy(update={"description": "x" * 80})
    text = _render(
        summary.model_copy(update={"resolution": [long_topic], "request": request}), tmp_path
    )
    assert text.startswith("# Intermittent fasting: interest on Wikipedia")
