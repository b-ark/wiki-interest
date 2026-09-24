"""Matplotlib chart renderer: every kind renders, output is deterministic, failures are loud."""

from pathlib import Path

import pytest
from PIL import Image

from fixtures.summaries import example_summary
from wiki_interest.adapters.matplotlib_charts import MatplotlibChartRenderer
from wiki_interest.contracts.charts import ChartNote, ChartPanel, ChartPoint, ChartSeries, ChartSpec
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


def test_svg_contains_title_as_text(renderer: MatplotlibChartRenderer, tmp_path: Path) -> None:
    spec = _spec_of_kind("trend")
    _, svg = renderer.render(spec, tmp_path)
    assert spec.title in svg.read_text(encoding="utf-8")


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


def _panels(count: int) -> ChartSpec:
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    panels = [
        ChartPanel(
            title=f"edition {n}",
            series=[
                ChartSeries(
                    label="months",
                    x=months,
                    y=[100.0 + i for i in range(12)],
                    style="points",
                    color=0,
                ),
                ChartSeries(
                    label="article",
                    x=months,
                    y=[None, None, *[101.0 + i for i in range(10)]],
                    color=0,
                ),
                ChartSeries(label="edition", x=months, y=[100.0] * 12, style="dashed", color=1),
            ],
            notes=[
                ChartNote(x="2025-05", text="2025-05 ×1.9, possibly bots"),
                ChartNote(x="2025-07", text="2025-07 edition ×1.7", series=2),
            ],
        )
        for n in range(count)
    ]
    return ChartSpec(
        id="main",
        kind="panels",
        title="Article views against edition traffic",
        subtitle="Index: mean of the first 12 months = 100. " * 4,
        y_label="index",
        panels=panels,
        reference_y=100.0,
    )


@pytest.mark.parametrize("count", [1, 2, 4, 5])
def test_panels_render_one_per_edition_with_notes(
    renderer: MatplotlibChartRenderer, tmp_path: Path, count: int
) -> None:
    _, svg = renderer.render(_panels(count), tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert f"edition {count - 1}" in text
    assert "possibly bots" in text


def test_dumbbell_and_scatter_render(renderer: MatplotlibChartRenderer, tmp_path: Path) -> None:
    dumbbell = ChartSpec(
        id="before-after",
        kind="dumbbell",
        title="Before and now",
        y_label="",
        x_label="per million",
        series=[
            ChartSeries(label="before", x=["ru", "uk", "pl"], y=[33.7, 28.4, None], style="points"),
            ChartSeries(label="now", x=["ru", "uk", "pl"], y=[27.9, 22.1, 23.1]),
        ],
    )
    _, svg = renderer.render(dumbbell, tmp_path)
    assert "27.9" in svg.read_text(encoding="utf-8")
    scatter = ChartSpec(
        id="size-change",
        kind="scatter",
        title="Size and change",
        y_label="change, %",
        x_label="per million, log scale",
        points=[ChartPoint(label="uk", x=150.0, y=-13.0), ChartPoint(label="hu", x=42.0, y=-23.0)],
        log_x=True,
        reference_y=0.0,
    )
    _, svg = renderer.render(scatter, tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "hu" in text
    assert "10^" not in text


def test_a_chart_without_the_data_its_kind_needs_is_rejected() -> None:
    with pytest.raises(ValueError, match="no data"):
        ChartSpec(id="main", kind="panels", title="t", y_label="y")
    with pytest.raises(ValueError, match="no data"):
        ChartSpec(id="s", kind="scatter", title="t", y_label="y")
    with pytest.raises(ValueError, match="no data"):
        ChartSpec(
            id="d",
            kind="dumbbell",
            title="t",
            y_label="y",
            series=[ChartSeries(label="a", x=["x"], y=[1.0])],
        )


def test_a_strip_is_as_wide_as_a_wide_chart_and_lower(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    series = [ChartSeries(label="uk", x=["2025-01", "2025-02"], y=[-10.0, 5.0])]
    sizes = {}
    for size in ("wide", "strip"):
        spec = ChartSpec(id=size, kind="lines", size=size, title="t", y_label="%", series=series)
        png, _ = renderer.render(spec, tmp_path)
        with Image.open(png) as image:
            sizes[size] = image.size
    assert sizes["strip"][0] == sizes["wide"][0]
    assert sizes["strip"][1] < sizes["wide"][1]


def test_full_width_charts_share_the_edges_of_their_plot(
    renderer: MatplotlibChartRenderer,
) -> None:
    """Charts stacked in the report line up: a legend or long labels never move the plot."""
    months = [f"2025-{m:02d}" for m in range(1, 13)]
    strip = ChartSpec(
        id="change",
        kind="lines",
        size="strip",
        title="Attention share: change against the same months a year earlier",
        y_label="change, %",
        series=[
            ChartSeries(label=f"{code}.wikipedia", x=months, y=[float(i) for i in range(12)])
            for code in ("en", "de", "fr")
        ],
        reference_y=0.0,
    )
    edges = set()
    for spec in (_panels(2), _panels(5), strip):
        figure = renderer._draw(spec)
        visible = [a for a in figure.axes if a.get_visible()]
        left = min(a.get_position().x0 for a in visible)
        right = max(a.get_position().x1 for a in visible)
        edges.add((round(left, 3), round(right, 3)))
    assert len(edges) == 1, edges
