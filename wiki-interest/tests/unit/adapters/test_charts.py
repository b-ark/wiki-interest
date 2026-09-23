"""Matplotlib chart renderer: every kind renders, output is deterministic, failures are loud."""

from pathlib import Path

import pytest

from fixtures.summaries import example_summary
from wiki_interest.adapters.matplotlib_charts import MatplotlibChartRenderer
from wiki_interest.contracts.charts import ChartSeries, ChartSpec
from wiki_interest.errors import RenderError

PNG_MAGIC = b"\x89PNG"


@pytest.fixture(scope="module")
def renderer() -> MatplotlibChartRenderer:
    return MatplotlibChartRenderer()


def _spec_of_kind(kind: str) -> ChartSpec:
    return next(c for c in example_summary().charts if c.kind == kind)


def _bars() -> ChartSpec:
    return ChartSpec(
        id="season",
        kind="bars",
        size="half",
        title="Months",
        y_label="%",
        series=[ChartSeries(label="m", x=["Jan", "Feb", "Mar"], y=[12.0, -4.5, 30.25])],
        reference_y=0.0,
        value_suffix="%",
    )


@pytest.mark.parametrize("kind", ["lines", "grouped_bars", "trend"])
def test_each_kind_writes_png_and_svg(
    renderer: MatplotlibChartRenderer, tmp_path: Path, kind: str
) -> None:
    spec = _spec_of_kind(kind)
    paths = renderer.render(spec, tmp_path / "charts")
    assert [p.name for p in paths] == [f"{spec.id}.png", f"{spec.id}.svg"]
    assert paths[0].read_bytes().startswith(PNG_MAGIC)
    assert paths[1].stat().st_size > 0
    assert "<svg" in paths[1].read_text(encoding="utf-8")


def test_bars_render_with_percent_labels(renderer: MatplotlibChartRenderer, tmp_path: Path) -> None:
    _, svg = renderer.render(_bars(), tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "30%" in text
    assert "-4%" in text or "-5%" in text


def test_value_labels_use_the_report_separators(tmp_path: Path) -> None:
    renderer = MatplotlibChartRenderer(decimal_sep=",", thousands_sep=" ")
    spec = ChartSpec(
        id="score",
        kind="bars",
        title="Score",
        y_label="score",
        series=[ChartSeries(label="s", x=["uk", "pl"], y=[0.98, 1234.0])],
    )
    _, svg = renderer.render(spec, tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "0,98" in text
    assert "1 234" in text


def test_log_axis_and_reference_line_render(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    spec = _spec_of_kind("lines").model_copy(update={"log_y": True, "reference_y": 50.0})
    assert len(renderer.render(spec, tmp_path)) == 2


def test_grouped_bars_with_mixed_signs_render(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    spec = ChartSpec(
        id="mixed",
        kind="grouped_bars",
        title="Mixed",
        y_label="%",
        series=[
            ChartSeries(label="a", x=["uk", "cs"], y=[10.0, -5.0]),
            ChartSeries(label="b", x=["uk", "cs"], y=[None, 3.0]),
        ],
    )
    assert len(renderer.render(spec, tmp_path)) == 2


def test_svg_contains_title_and_footnote_as_text(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    spec = _spec_of_kind("trend")
    _, svg = renderer.render(spec, tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert spec.title in text
    assert spec.footnote is not None
    assert "Wikimedia Pageviews API" in text


def test_svg_is_byte_identical_across_runs(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    spec = _spec_of_kind("trend")
    first = renderer.render(spec, tmp_path / "a")[1].read_bytes()
    second = renderer.render(spec, tmp_path / "b")[1].read_bytes()
    assert first == second
    assert b"<dc:date>" not in first


def test_png_is_byte_identical_across_runs(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    spec = _bars()
    first = renderer.render(spec, tmp_path / "a")[0].read_bytes()
    second = renderer.render(spec, tmp_path / "b")[0].read_bytes()
    assert first == second


def test_none_only_series_renders_empty_axes_with_note(tmp_path: Path) -> None:
    renderer = MatplotlibChartRenderer(empty_note="Немає даних")
    spec = ChartSpec(
        id="empty",
        kind="lines",
        title="Empty",
        y_label="y",
        series=[ChartSeries(label="uk", x=["2024-01", "2024-02"], y=[None, None])],
    )
    png, svg = renderer.render(spec, tmp_path)
    assert png.stat().st_size > 0
    assert "Немає даних" in svg.read_text(encoding="utf-8")


def test_bars_with_missing_and_negative_values_render(tmp_path: Path) -> None:
    renderer = MatplotlibChartRenderer(missing_label="н/д")
    spec = ChartSpec(
        id="growth",
        kind="bars",
        title="Growth",
        y_label="%",
        series=[ChartSeries(label="g", x=["a", "b", "c"], y=[12.5, None, -3.0])],
    )
    _, svg = renderer.render(spec, tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "н/д" in text
    assert "-3.00" in text


def test_trend_without_trend_line_or_highlights_renders(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    spec = ChartSpec(
        id="bare-trend",
        kind="trend",
        title="Trend",
        y_label="y",
        series=[ChartSeries(label="s", x=["2024-01", "2024-02", "2024-03"], y=[1.0, None, 3.0])],
        highlight_x=["2099-01"],
    )
    paths = renderer.render(spec, tmp_path)
    assert len(paths) == 2


def test_spec_without_footnote_renders(renderer: MatplotlibChartRenderer, tmp_path: Path) -> None:
    spec = _spec_of_kind("lines").model_copy(update={"footnote": None})
    assert len(renderer.render(spec, tmp_path)) == 2


def test_output_dir_that_is_a_file_raises_render_error(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    blocker = tmp_path / "charts"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(RenderError) as info:
        renderer.render(_spec_of_kind("lines"), blocker)
    assert info.value.exit_code == 5
    assert info.value.hint


def test_missing_theme_file_raises_render_error(tmp_path: Path) -> None:
    with pytest.raises(RenderError):
        MatplotlibChartRenderer(theme_path=tmp_path / "missing.json")


def test_invalid_theme_file_raises_render_error(tmp_path: Path) -> None:
    broken = tmp_path / "theme.json"
    broken.write_text('{"palette": []}', encoding="utf-8")
    with pytest.raises(RenderError):
        MatplotlibChartRenderer(theme_path=broken)
