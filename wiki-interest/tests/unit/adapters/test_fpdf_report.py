"""PDF report: exactly one A4 page in every language, readable text, graceful overflow."""

# ruff: noqa: RUF001  -- expected strings contain Cyrillic titles.

from pathlib import Path

import pytest
from pypdf import PdfReader

from fixtures.summaries import example_summary
from wiki_interest.adapters import fpdf_report
from wiki_interest.adapters.fpdf_report import FpdfReportRenderer
from wiki_interest.adapters.matplotlib_charts import MatplotlibChartRenderer
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

A4_WIDTH_PT = 595
A4_HEIGHT_PT = 842
LONG_LIMITATION = (
    "This limitation is deliberately verbose so that a long list of them cannot possibly fit "
    "on a single A4 page without the renderer shrinking and finally truncating the section"
)


@pytest.fixture(scope="module")
def chart_paths(tmp_path_factory: pytest.TempPathFactory) -> list[Path]:
    out = tmp_path_factory.mktemp("charts")
    renderer = MatplotlibChartRenderer()
    return [renderer.render(spec, out)[0] for spec in example_summary().charts]


def _render(summary: AnalysisSummary, charts: list[Path], target: Path) -> PdfReader:
    renderer = FpdfReportRenderer(Translator(summary.request.report.language))
    return PdfReader(renderer.render(summary, charts, target))


@pytest.mark.parametrize("language", ["en", "uk", "pl", "cs", "ru"])
def test_fixture_fits_on_exactly_one_page_in_every_language(
    tmp_path: Path, chart_paths: list[Path], language: str
) -> None:
    reader = _render(example_summary(language=language), chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert round(float(box.width)) == A4_WIDTH_PT
    assert round(float(box.height)) == A4_HEIGHT_PT


def test_english_text_contains_headline_key_number_and_sections(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    reader = _render(example_summary(), chart_paths, tmp_path / "report.pdf")
    text = reader.pages[0].extract_text()
    assert "Intermittent fasting: uk vs cs" in text
    assert "Interest in intermittent fasting is growing faster in Czech" in text
    assert "10,349" in text, "views/month tile value"
    assert "+32%" in text, "growth tile value"
    assert "Verdict" in text
    assert "How much to trust this" in text
    assert "Assumptions and limitations" in text
    assert "Skill version: 0.1.0" in text
    assert "2026-09-22 12:00 UTC" in text, "generated-at footer (label may wrap)"


def test_ukrainian_text_contains_cyrillic_and_czech_diacritics(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    reader = _render(example_summary(language="uk"), chart_paths, tmp_path / "report.pdf")
    text = reader.pages[0].extract_text()
    assert "Інтерес до інтервального голодування" in text
    assert "Přerušovaný půst" in text
    assert "Наскільки можна довіряти" in text
    assert "Verdict" not in text


def test_polish_and_czech_diacritics_survive_extraction(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    text = _render(example_summary(language="pl"), chart_paths, tmp_path / "pl.pdf").pages[0]
    assert "Założenia i ograniczenia" in text.extract_text()
    text = _render(example_summary(language="cs"), chart_paths, tmp_path / "cs.pdf").pages[0]
    assert "Předpoklady a omezení" in text.extract_text()


def test_overflowing_limitations_still_yield_one_page_with_pointer(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    summary = example_summary().model_copy(
        update={"limitations": [f"{i}. {LONG_LIMITATION}" for i in range(40)]}
    )
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    assert "summary.md" in reader.pages[0].extract_text()


def test_overflowing_reliability_reasons_are_reduced_before_truncation(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    summary = example_summary(question_type="rank")
    reliability = [
        item.model_copy(
            update={
                "checks": [
                    c.model_copy(update={"message": f"{c.message}. {LONG_LIMITATION}"})
                    for c in item.checks
                ]
            }
        )
        for item in summary.reliability
    ]
    summary = summary.model_copy(update={"reliability": reliability})
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1


def test_renders_without_charts_or_tables(tmp_path: Path) -> None:
    summary = example_summary().model_copy(update={"comparison": [], "ranking": []})
    reader = _render(summary, [], tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    assert "Verdict" in reader.pages[0].extract_text()


def test_rank_summary_uses_ranking_tiles(tmp_path: Path, chart_paths: list[Path]) -> None:
    summary = example_summary(question_type="rank").model_copy(update={"comparison": []})
    text = _render(summary, chart_paths, tmp_path / "report.pdf").pages[0].extract_text()
    assert "1. cs: 0.81" in text
    assert "growth market" in text


def test_output_is_byte_identical_across_runs(tmp_path: Path, chart_paths: list[Path]) -> None:
    renderer = FpdfReportRenderer(Translator("en"))
    first = renderer.render(example_summary(), chart_paths, tmp_path / "a.pdf").read_bytes()
    second = renderer.render(example_summary(), chart_paths, tmp_path / "b.pdf").read_bytes()
    assert first == second
    assert b"/CreationDate (D:20000101" in first


def test_metadata_is_fixed(tmp_path: Path, chart_paths: list[Path]) -> None:
    reader = _render(example_summary(), chart_paths, tmp_path / "report.pdf")
    assert reader.metadata is not None
    assert reader.metadata.title == "Intermittent fasting: uk vs cs"
    assert reader.metadata.producer == "wiki-interest"


def test_missing_chart_file_raises_render_error(tmp_path: Path) -> None:
    renderer = FpdfReportRenderer(Translator("en"))
    with pytest.raises(RenderError):
        renderer.render(example_summary(), [tmp_path / "missing.png"], tmp_path / "report.pdf")


def test_unwritable_output_raises_render_error(tmp_path: Path) -> None:
    blocker = tmp_path / "report.pdf"
    blocker.mkdir()
    with pytest.raises(RenderError):
        FpdfReportRenderer(Translator("en")).render(example_summary(), [], blocker)


def test_missing_font_dir_raises_render_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(fpdf_report, "FONT_DIR", tmp_path)
    with pytest.raises(RenderError):
        FpdfReportRenderer(Translator("en"))


def test_many_verdict_bullets_shrink_font_then_truncate(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    summary = example_summary().model_copy(
        update={
            "verdict": example_summary().verdict.model_copy(
                update={"bullets": [f"{i}. {LONG_LIMITATION}" for i in range(30)]}
            )
        }
    )
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "summary.md" in text
    assert "Assumptions and limitations" not in text, "later sections are dropped, not spilled"


def test_multi_topic_tiles_carry_shortened_labels(tmp_path: Path, chart_paths: list[Path]) -> None:
    summary = example_summary()
    rows = [
        summary.comparison[0],
        summary.comparison[1].model_copy(update={"topic_id": "fasting", "label": "Půst"}),
    ]
    text = _render(summary.model_copy(update={"comparison": rows}), chart_paths, tmp_path / "r.pdf")
    extracted = text.pages[0].extract_text()
    assert "uk Інтервальне г…: 10,349" in extracted
    assert "cs Půst: 5,654" in extracted


def test_render_error_when_no_layout_fits(
    tmp_path: Path, chart_paths: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(FpdfReportRenderer, "_layouts", lambda _self: iter([fpdf_report._Layout()]))
    summary = example_summary().model_copy(
        update={"limitations": [f"{i}. {LONG_LIMITATION}" for i in range(40)]}
    )
    with pytest.raises(RenderError, match="does not fit"):
        FpdfReportRenderer(Translator("en")).render(summary, chart_paths, tmp_path / "r.pdf")
