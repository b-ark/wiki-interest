"""Matplotlib chart renderer: every kind renders, output is deterministic, failures are loud."""

from pathlib import Path

import pytest
from PIL import Image

from fixtures.summaries import audience_years_data, example_summary, share_years_data
from wiki_interest.adapters.matplotlib_charts import MatplotlibChartRenderer, _step_rows
from wiki_interest.application.chart_plan import audience_years_spec, share_years_spec
from wiki_interest.contracts.charts import ChartPoint, ChartSeries, ChartSpec, ShareMark
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

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


def _share(lines: int = 2, cited: frozenset[str] = frozenset({"step:x/uk"})) -> ChartSpec:
    return share_years_spec(share_years_data(lines), Translator("en"), cited)


@pytest.mark.parametrize("lines", [1, 2, 3])
def test_the_main_chart_names_each_audience_and_writes_each_year(
    renderer: MatplotlibChartRenderer, tmp_path: Path, lines: int
) -> None:
    _, svg = renderer.render(_share(lines), tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert all(code in text for code in ("uk", "cs", "pl")[:lines])
    assert "24.0" in text  # the first audience's trend line after its step
    assert "(Jan – Aug)" in text  # the partial year says which months it has
    assert "average over a calendar year (context)" in text
    assert "analysis period" in text
    assert "Attention share over time" in text


def test_a_long_name_at_a_line_end_stays_inside_the_chart(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    data = share_years_data(2)
    long = data.lines[1].model_copy(update={"label": "pl (Obserwatorium astronomiczne)"})
    spec = share_years_spec(
        data.model_copy(update={"lines": [data.lines[0], long]}), Translator("en"), set()
    )
    png, _ = renderer.render(spec, tmp_path)
    with Image.open(png) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        edge = {rgb.getpixel((x, y)) for x in range(width - 4, width) for y in range(height)}
    assert edge == {rgb.getpixel((0, 0))}  # the background alone: no letter cut at the edge


def test_the_main_chart_marks_steps_always_and_bursts_the_text_cites(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    # A mark says its month only: the text that cites it says what happened.
    _, svg = renderer.render(_share(cited=frozenset()), tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "Aug 2023" in text
    # An uncited burst over the top edge keeps its value, not a label.
    assert "Aug 2022" not in text
    assert "80.0" in text
    _, svg = renderer.render(_share(cited=frozenset({"spike:x/uk"})), tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "Aug 2022 (80.0)" in text


def test_close_steps_put_their_labels_on_two_rows() -> None:
    data = share_years_data(1)
    marks = [
        ShareMark(kind="step", line=0, x="2025-04", observation="step:a"),
        ShareMark(kind="step", line=0, x="2025-08", observation="step:b"),
        ShareMark(kind="step", line=0, x="2022-01", observation="step:c"),
    ]
    spec = share_years_spec(
        data.model_copy(update={"marks": marks}), Translator("en"), {"step:a", "step:b", "step:c"}
    )
    assert _step_rows(spec) == {2: 0, 0: 0, 1: 1}


def test_the_main_chart_of_raw_views_writes_whole_numbers(
    renderer: MatplotlibChartRenderer, tmp_path: Path
) -> None:
    data = share_years_data(1).model_copy(update={"absolute": True})
    spec = share_years_spec(data, Translator("en"), set())
    _, svg = renderer.render(spec, tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "Views by year" in text
    assert ">24<" in text or "24</" in text or " 24" in text


@pytest.mark.parametrize("lines", [1, 2, 3])
def test_the_views_by_year_write_each_change_and_whether_the_share_moved(
    renderer: MatplotlibChartRenderer, tmp_path: Path, lines: int
) -> None:
    spec = audience_years_spec(audience_years_data(lines), Translator("en"))
    _, svg = renderer.render(spec, tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert all(code in text for code in ("uk", "cs", "pl")[:lines])
    assert "84,000" in text  # views as shown, three significant digits
    assert "\u221220%" in text  # the change against a year earlier, over the bar
    # Symbols, not words: they fit under a year in any language.
    assert "▲" in text
    assert "≈" in text
    assert "▼" in text
    assert "gained share" not in text
    assert "Sep 2025 – Aug 2026" in text


def test_the_views_by_year_write_numbers_in_the_report_style(tmp_path: Path) -> None:
    renderer = MatplotlibChartRenderer(decimal_sep=",", thousands_sep="\u202f")
    spec = audience_years_spec(audience_years_data(1), Translator("uk"))
    _, svg = renderer.render(spec, tmp_path)
    text = svg.read_text(encoding="utf-8")
    assert "84\u202f000" in text
    assert "\u221220\u202f%" in text


def test_scatter_renders(renderer: MatplotlibChartRenderer, tmp_path: Path) -> None:
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
        ChartSpec(id="share", kind="share_years", title="t", y_label="y")
    with pytest.raises(ValueError, match="no data"):
        ChartSpec(id="s", kind="scatter", title="t", y_label="y")
    with pytest.raises(ValueError, match="no data"):
        ChartSpec(id="audience", kind="audience_years", title="t", y_label="y")


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


def test_full_width_charts_share_the_left_edge_of_their_plot(
    renderer: MatplotlibChartRenderer,
) -> None:
    """Charts stacked in the report line up: a legend or long labels never move the plot.

    The main chart ends earlier on the right: the audiences' names stand at its lines' ends.
    """
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
    lefts, rights = [], []
    for spec in (_share(1), _share(3), strip):
        figure = renderer._draw(spec)
        visible = [a for a in figure.axes if a.get_visible()]
        lefts.append(round(min(a.get_position().x0 for a in visible), 3))
        rights.append(round(max(a.get_position().x1 for a in visible), 3))
    assert len(set(lefts)) == 1, lefts
    assert rights[0] == rights[1] < rights[2]
