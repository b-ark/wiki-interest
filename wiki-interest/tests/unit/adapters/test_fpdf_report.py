"""PDF report: exactly one A4 page in every language, readable text, graceful overflow."""

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
    assert "cs: 117.8 per million" in text, "size of interest card"
    assert "10,349" in text, "views per month under the size card"
    assert "cs: +32% ↑" in text, "change card"
    assert "1 in" not in text, "the share is stated per million only"
    assert "Answer" in text
    assert "Is the topic growing faster or slower than its Wikipedia?" in text
    assert "What this means for the decision" in text
    assert "Next step: confirm the signal for cs.wikipedia" in " ".join(text.split())
    assert "How robust is this conclusion?" in text
    assert "Do recent months confirm the trend?" in text
    assert "Assumptions and limitations" in text
    assert "About the method" in text
    assert "Wikimedia Pageviews API, Wikidata, MediaWiki API" in text, "sources by name"
    assert "Skill version: 0.1.0" in text
    assert "2026-09-22 12:00 UTC" in text, "generated-at footer (label may wrap)"


def test_robustness_lines_and_the_data_line(tmp_path: Path, chart_paths: list[Path]) -> None:
    text = _render(example_summary(), chart_paths, tmp_path / "r.pdf").pages[0].extract_text()
    joined = " ".join(text.split())
    assert "cs.wikipedia: mixed signal." in joined
    assert "Data: 24 months of data; bursts do not drive the result." in joined
    assert "statistically significant (p" not in joined


def test_ukrainian_text_contains_cyrillic_and_czech_diacritics(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    reader = _render(example_summary(language="uk"), chart_paths, tmp_path / "report.pdf")
    text = reader.pages[0].extract_text()
    assert "Інтерес до інтервального голодування" in text
    assert "Відповідь" in text
    assert "Наскільки стійкий цей висновок?" in text
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
    assessments = [
        item.model_copy(
            update={
                "evidence": [
                    e.model_copy(update={"text": f"{e.text}. {LONG_LIMITATION}"})
                    for e in item.evidence
                ]
            }
        )
        for item in summary.assessments
    ]
    summary = summary.model_copy(update={"assessments": assessments})
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1


def test_renders_without_charts_or_tables(tmp_path: Path) -> None:
    summary = example_summary().model_copy(update={"comparison": [], "ranking": []})
    reader = _render(summary, [], tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    assert "Answer" in reader.pages[0].extract_text()


def test_rank_cards_follow_the_ranking(tmp_path: Path, chart_paths: list[Path]) -> None:
    summary = example_summary(question_type="rank")
    text = _render(summary, chart_paths, tmp_path / "report.pdf").pages[0].extract_text()
    assert (
        text.index("cs: 117.8 per million")
        < text.index("uk: 98.6 per million")
        < text.index("pl: ")
    )


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


def test_further_findings_are_capped_on_the_page(tmp_path: Path, chart_paths: list[Path]) -> None:
    summary = example_summary().model_copy(
        update={
            "verdict": example_summary().verdict.model_copy(
                update={"bullets": [f"Finding {i}." for i in range(30)]}
            )
        }
    )
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    text = reader.pages[0].extract_text()
    assert "Finding 0." in text
    assert "Finding 2." not in text, "report.md lists the rest"


def test_a_long_answer_shrinks_font_then_truncates(tmp_path: Path, chart_paths: list[Path]) -> None:
    summary = example_summary().model_copy(
        update={
            "verdict": example_summary().verdict.model_copy(
                update={"headline": " ".join(LONG_LIMITATION for _ in range(25))}
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
    items = [
        summary.assessments[0].model_copy(update={"label": "intermittent fasting · uk.wikipedia"}),
        summary.assessments[1].model_copy(
            update={"topic_id": "fasting", "label": "fasting · cs.wikipedia"}
        ),
    ]
    text = _render(
        summary.model_copy(update={"assessments": items}), chart_paths, tmp_path / "r.pdf"
    )
    extracted = text.pages[0].extract_text()
    assert "uk intermittent…: 98.6 per million" in extracted
    assert "cs fasting: 117.8 per million" in extracted


def test_render_error_when_no_layout_fits(
    tmp_path: Path, chart_paths: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(FpdfReportRenderer, "_layouts", lambda _self: iter([fpdf_report._Layout()]))
    summary = example_summary().model_copy(
        update={"limitations": [f"{i}. {LONG_LIMITATION}" for i in range(40)]}
    )
    with pytest.raises(RenderError, match="does not fit"):
        FpdfReportRenderer(Translator("en")).render(summary, chart_paths, tmp_path / "r.pdf")
