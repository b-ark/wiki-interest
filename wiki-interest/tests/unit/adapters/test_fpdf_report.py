"""PDF report: exactly one A4 page in every language, readable text, graceful overflow."""

from pathlib import Path
from typing import Any

import pytest
from fpdf import FPDF
from pypdf import PdfReader

from fixtures.summaries import example_summary
from wiki_interest.adapters import fpdf_report
from wiki_interest.adapters.fpdf_report import FpdfReportRenderer
from wiki_interest.adapters.matplotlib_charts import MatplotlibChartRenderer
from wiki_interest.adapters.report_theme import ReportTheme
from wiki_interest.contracts.charts import ChartPanel, ChartSeries, ChartSpec
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

A4_WIDTH_PT = 595
A4_WIDTH_MM = 210
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


def _render(
    summary: AnalysisSummary,
    charts: list[Path],
    target: Path,
    ui: dict[str, str] | None = None,
) -> PdfReader:
    translator = Translator(summary.request.report.language)
    translator.override(ui or {})
    return PdfReader(FpdfReportRenderer(translator).render(summary, charts, target))


@pytest.mark.parametrize("language", ["en", "uk", "pl", "cs", "ru"])
def test_fixture_fits_on_exactly_one_page_in_every_language(
    tmp_path: Path, chart_paths: list[Path], language: str
) -> None:
    reader = _render(example_summary(language=language), chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert round(float(box.width)) == A4_WIDTH_PT
    assert round(float(box.height)) == A4_HEIGHT_PT


def _text(reader: PdfReader, page: int = 0) -> str:
    return " ".join(reader.pages[page].extract_text().split())


def test_the_page_reads_as_a_decision_memo_in_order(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    text = _text(_render(example_summary(), chart_paths, tmp_path / "report.pdf"))
    body = [
        "Interest in intermittent fasting is growing faster in Czech",
        "intermittent fasting (Q",  # what was analysed: topic and item
        "Period: 2024-09 – 2026-08",
        "Metric",  # the key numbers
        "117.8",
        "What happened",
        "How robust is this conclusion?",
        "What this means for the decision",
        "Next step: confirm the signal for cs.wikipedia",
    ]
    # The footer is drawn first (its height decides where the content ends).
    footer = [
        "Attention share: article views per 1 million views of the whole edition",
        "a language edition is not a country",
        "method.md",
        "Skill version: 0.1.0",
    ]
    for order in (body, footer):
        positions = [text.index(part) for part in order]
        assert positions == sorted(positions), list(zip(order, positions, strict=True))
    assert "1 in" not in text, "the share is stated per million only"


def test_the_data_line_and_the_robustness_lines(tmp_path: Path, chart_paths: list[Path]) -> None:
    text = _text(_render(example_summary(), chart_paths[:1], tmp_path / "r.pdf"))
    assert "cs.wikipedia: mixed signal." in text
    assert "Data: 24 months of data; bursts do not drive the result." in text


@pytest.mark.parametrize(
    ("language", "ui"),
    [
        ("uk", {"report.happening": "Що відбувається", "report.robustness": "Наскільки стійкий"}),
        (
            "pl",
            {"report.happening": "Co się dzieje", "report.robustness": "Jak pewny jest wniosek"},
        ),
        ("cs", {"report.happening": "Co se děje", "report.robustness": "Jak pevný je závěr"}),
        ("ru", {"report.happening": "Что происходит", "report.robustness": "Насколько устойчив"}),
    ],
)
def test_every_language_keeps_its_script_and_the_agent_labels(
    tmp_path: Path, chart_paths: list[Path], language: str, ui: dict[str, str]
) -> None:
    summary = example_summary(language=language)
    text = _text(_render(summary, chart_paths, tmp_path / f"{language}.pdf", ui))
    for part in ui.values():
        assert part in text, part
    assert summary.verdict.headline.split()[0] in text
    assert "What happened" not in text


def test_many_caveats_are_trimmed_to_keep_one_page(tmp_path: Path, chart_paths: list[Path]) -> None:
    summary = example_summary().model_copy(
        update={"limitations": [f"{i}. {LONG_LIMITATION}" for i in range(40)]}
    )
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    text = _text(reader)
    assert "39. This limitation" not in text
    assert "What this means for the decision" in text


def test_text_is_never_set_below_the_floor(tmp_path: Path, chart_paths: list[Path]) -> None:
    sizes: set[float] = set()

    def visit(_text: str, _cm: object, _tm: object, _font: object, size: float) -> None:
        if _text.strip():
            sizes.add(round(size, 2))

    summary = example_summary().model_copy(
        update={"limitations": [f"{i}. {LONG_LIMITATION}" for i in range(12)]}
    )
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    reader.pages[0].extract_text(visitor_text=visit)
    assert sizes
    assert min(sizes) >= 8.5


def test_renders_without_charts_or_tables(tmp_path: Path) -> None:
    summary = example_summary().model_copy(update={"comparison": [], "ranking": []})
    reader = _render(summary, [], tmp_path / "report.pdf")
    assert len(reader.pages) == 1
    assert "What happened" in _text(reader)


def test_the_appendix_adds_the_method_on_a_second_page(
    tmp_path: Path, chart_paths: list[Path]
) -> None:
    summary = example_summary()
    report = summary.request.report.model_copy(update={"appendix": True})
    summary = summary.model_copy(
        update={"request": summary.request.model_copy(update={"report": report})}
    )
    reader = _render(summary, chart_paths, tmp_path / "report.pdf")
    assert len(reader.pages) >= 2
    method = _text(reader, 1)
    assert method.startswith("Method")
    assert "Trend test (Mann-Kendall" in method


def test_the_key_numbers_follow_the_ranking(tmp_path: Path, chart_paths: list[Path]) -> None:
    summary = example_summary(question_type="rank")
    text = _text(_render(summary, chart_paths, tmp_path / "report.pdf"))
    table = text[text.index("Metric") :]
    assert table.index("cs") < table.index("uk") < table.index("pl")


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


def test_a_long_answer_truncates_without_shrinking(tmp_path: Path, chart_paths: list[Path]) -> None:
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
    assert "What this means for the decision" not in text, "later sections are dropped"


def test_render_error_when_no_layout_fits(
    tmp_path: Path, chart_paths: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(FpdfReportRenderer, "_layouts", lambda _self: iter([fpdf_report._Layout()]))
    summary = example_summary().model_copy(
        update={"limitations": [f"{i}. {LONG_LIMITATION}" for i in range(40)]}
    )
    with pytest.raises(RenderError, match="does not fit"):
        FpdfReportRenderer(Translator("en")).render(summary, chart_paths, tmp_path / "r.pdf")


def _stacked_charts() -> list[ChartSpec]:
    """Panels over a strip, as most reports have them."""
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    line = [ChartSeries(label="article", x=months, y=[100.0 + i for i in range(12)])]
    panels = ChartSpec(
        id="main",
        kind="panels",
        title="Article views against edition traffic",
        subtitle="Index: mean of the first 12 months = 100.",
        y_label="index, first 12 months = 100",
        panels=[ChartPanel(title=f"{code}.wikipedia", series=line) for code in ("uk", "cs")],
        reference_y=100.0,
    )
    strip = ChartSpec(
        id="change",
        kind="lines",
        size="strip",
        title="Attention share: change against the same months a year earlier",
        y_label="change, %",
        series=[
            ChartSeries(label=f"{code}.wikipedia", x=months, y=[float(i) for i in range(12)])
            for code in ("uk", "cs")
        ],
    )
    return [panels, strip]


def test_charts_too_tall_are_drawn_lower_at_the_full_width_and_line_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A crowded page lowers the charts instead of shrinking them: the page width stays."""
    attempts: list[list[tuple[str, float, float]]] = []
    image, draw = FPDF.image, fpdf_report._Page.draw

    def spy_image(pdf: FPDF, name: str, **kwargs: Any) -> object:
        attempts[-1].append((Path(name).stem, round(kwargs["x"], 1), round(kwargs["w"], 1)))
        return image(pdf, name, **kwargs)

    def spy_draw(page: fpdf_report._Page) -> None:
        attempts.append([])
        draw(page)

    monkeypatch.setattr(FPDF, "image", spy_image)
    monkeypatch.setattr(fpdf_report._Page, "draw", spy_draw)
    charts = MatplotlibChartRenderer()
    specs = _stacked_charts()
    paths = [charts.render(spec, tmp_path / "charts")[0] for spec in specs]
    summary = example_summary()
    # The headline always stays: a long one leaves the charts less room on every layout.
    headline = " ".join([summary.verdict.headline] * 4)
    crowded = summary.model_copy(
        update={
            "charts": specs,
            "verdict": summary.verdict.model_copy(update={"headline": headline}),
        }
    )
    renderer = FpdfReportRenderer(Translator("en"), charts=charts)
    renderer.render(crowded, paths, tmp_path / "report.pdf")
    two_charts = [a for a in attempts if len(a) == len(specs)]
    lowered = [a for a in two_charts if all("-h" in name for name, _, _ in a)]
    assert lowered, attempts
    for attempt in lowered:
        assert {(x, w) for _, x, w in attempt} == {(15.0, 180.0)}, attempt


def test_charts_are_drawn_as_wide_as_the_page_places_them() -> None:
    """A chart scaled up in the PDF blurs, and its text grows past the type scale."""
    theme = ReportTheme.load()
    text_width = A4_WIDTH_MM - 2 * theme.pdf.margin_mm
    assert theme.chart.width_mm == text_width
    assert theme.chart.half_width_mm == (text_width - theme.pdf.chart_gap_mm) / 2
