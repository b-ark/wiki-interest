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
    ("language", "expected"),
    [
        ("uk", ["Інтерес до інтервального голодування", "Що відбувається", "Наскільки стійкий"]),
        ("pl", ["Co się dzieje", "edycja językowa to nie kraj"]),
        ("cs", ["Co se děje", "jazyková edice není země"]),
        ("ru", ["Что происходит", "языковой раздел — не страна"]),
    ],
)
def test_every_language_keeps_its_script_and_labels(
    tmp_path: Path, chart_paths: list[Path], language: str, expected: list[str]
) -> None:
    summary = example_summary(language=language)
    text = _text(_render(summary, chart_paths, tmp_path / f"{language}.pdf"))
    for part in expected:
        assert part in text, part
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
