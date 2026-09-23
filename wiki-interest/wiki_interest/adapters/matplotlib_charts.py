"""Matplotlib implementation of :class:`~wiki_interest.ports.renderers.ChartRenderer`.

Charts are drawn head-less on the ``Agg`` backend from a :class:`ChartSpec` and written as a
PNG (for the PDF and chat) and an SVG (for documents). Output is deterministic: no
timestamps in metadata, a fixed ``svg.hashsalt`` and no dependence on the process locale, so
a re-run with the same data yields byte-identical files and golden tests stay green.
"""

from __future__ import annotations

import math
import textwrap
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # Must precede any pyplot/figure import: never rely on a display.

import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from matplotlib.typing import RcKeyType

from wiki_interest.adapters.report_theme import ReportTheme
from wiki_interest.contracts.charts import ChartPanel, ChartSeries, ChartSpec
from wiki_interest.errors import RenderError

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from numpy.typing import NDArray

__all__ = ["MatplotlibChartRenderer"]

MM_PER_INCH = 25.4
SVG_HASHSALT = "wiki-interest"
"""Fixed salt for SVG element ids; the default is a random UUID per process."""
SVG_METADATA: dict[str, Any] = {"Date": None, "Creator": "wiki-interest"}
"""``Date: None`` removes the creation timestamp matplotlib would otherwise embed."""
PNG_METADATA: dict[str, Any] = {"Software": "wiki-interest"}
"""Replaces the default ``Software`` entry so the PNG does not change with matplotlib upgrades."""
LABEL_ROTATION_THRESHOLD = 6
"""Above this many categories the x labels are rotated to stay legible."""
LABEL_ROTATION_DEG = 45
VALUE_LABEL_OFFSET_PT = 3
ZERO_LINE_WIDTH = 0.8
LARGE_VALUE = 100.0
MEDIUM_VALUE = 10.0
HALF_BAR = 0.5
MAX_MARKED_POINTS = 60
"""Longer series (daily data) are drawn without point markers, which would merge into a band."""
GROUP_WIDTH = 0.8
"""Share of a category slot taken by a group of bars."""
REFERENCE_LINE_WIDTH = 0.9
LEGEND_BAND = 1.45
"""Value-axis stretch that leaves an empty band for the legend of a bar chart."""
VALUE_HEADROOM = 1.12
"""Room above the tallest bar for its value label."""
TITLE_PAD_PT = 8.0
SUBTITLE_LINE_HEIGHT = 1.3
"""Height of a subtitle line in font sizes, the room the title moves up by per line."""
SUBTITLE_WIDTH_SHARE = 0.85
"""Share of the figure width the subtitle may take; the rest is the y-axis label."""
CHAR_MM_PER_PT = 0.2
"""Average width of a DejaVu Sans character per point of font size, in millimetres."""
MAX_INSIDE_LEGEND = 2
"""A wide line chart with more series than this gets its legend outside the plot."""
MAX_PANEL_COLUMNS = 3
EXTRA_ROW_HEIGHT = 0.65
"""Each further row of panels adds this share of a one-row chart's height."""
PT_TO_MM = 0.3528
HEADER_GAP_MM = 2.0
POINT_ALPHA = 0.35
POINT_SCALE = 0.8
DASHED_WIDTH = 0.9
PANEL_ROW_HEIGHT = 1.25
"""A one-row panel chart is this many times a wide chart's height: header, legend, ticks."""
MIN_PANEL_TICKS = 3
LEGEND_ROW_MM = 7.0
RING_SCALE = 2.2
DUMBBELL_LINE_WIDTH = 2.0
LABEL_OFFSET_PT = 4


class MatplotlibChartRenderer:
    """Renders ``lines``, ``bars``, ``grouped_bars`` and ``trend`` charts in the report theme.

    Args:
        theme_path: Theme JSON to use; ``None`` selects ``assets/report_theme.json``.
        empty_note: Text drawn on the axes when every value of the spec is missing. Passed in
            (already localised) because the renderer itself knows nothing about languages.
        missing_label: Value label for a single missing bar.
        decimal_sep: Decimal separator of the report language for value labels.
        thousands_sep: Thousands separator of the report language for value labels.
    """

    def __init__(
        self,
        theme_path: Path | None = None,
        *,
        empty_note: str = "No data",
        missing_label: str = "n/a",
        decimal_sep: str = ".",
        thousands_sep: str = ",",
    ) -> None:
        self._theme = ReportTheme.load(theme_path)
        self._empty_note = empty_note
        self._missing_label = missing_label
        self._decimal_sep = decimal_sep
        self._thousands_sep = thousands_sep

    def render(self, spec: ChartSpec, output_dir: Path) -> Sequence[Path]:
        """Draw ``spec`` and write ``<id>.png`` and ``<id>.svg`` into ``output_dir``.

        Raises:
            RenderError: If the directory cannot be created or matplotlib fails to draw/save.
        """
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            with matplotlib.rc_context(self._rc_params()):
                figure = self._draw(spec)
                return self._save(figure, spec.id, output_dir)
        except (OSError, ValueError, RuntimeError) as exc:
            msg = f"Cannot render chart {spec.id!r} into {output_dir}: {exc}"
            raise RenderError(msg, hint="Check that the output directory is writable") from exc

    # -- figure assembly ---------------------------------------------------------------------

    def _rc_params(self) -> dict[RcKeyType, Any]:
        theme = self._theme
        return {
            "font.family": theme.font_family,
            "font.size": theme.chart.font_size_pt,
            "text.color": theme.text_color,
            "axes.labelcolor": theme.text_color,
            "xtick.color": theme.text_color,
            "ytick.color": theme.text_color,
            "axes.edgecolor": theme.grid_color,
            "svg.hashsalt": SVG_HASHSALT,
            "svg.fonttype": "none",
            "path.simplify": False,
        }

    def _draw(self, spec: ChartSpec) -> Figure:
        chart = self._theme.chart
        if spec.kind == "panels":
            return self._draw_panels(spec)
        width, height = {
            "half": (chart.half_width_mm, chart.half_height_mm),
            "strip": (chart.width_mm, chart.strip_height_mm),
        }.get(spec.size, (chart.width_mm, chart.height_mm))
        figure = Figure(figsize=(width / MM_PER_INCH, height / MM_PER_INCH), dpi=chart.dpi)
        axes = figure.add_subplot()
        self._style_axes(axes, spec)
        if spec.kind == "scatter":
            self._draw_scatter(axes, spec)
        elif spec.kind == "dumbbell":
            self._draw_dumbbell(axes, spec)
        elif _is_empty(spec):
            self._draw_empty(axes, spec.series[0].x)
        elif spec.kind == "bars":
            self._draw_bars(axes, spec.series[0], spec.value_suffix)
        elif spec.kind == "grouped_bars":
            self._draw_grouped_bars(axes, spec.series, spec.value_suffix)
        elif spec.kind == "trend":
            self._draw_trend(axes, spec)
        else:
            # A strip is too low for a legend inside; a wide chart with many lines too.
            outside = spec.size == "strip" or (
                spec.size == "wide" and len(spec.series) > MAX_INSIDE_LEGEND
            )
            self._draw_lines(axes, spec.series, legend_outside=outside)
        if spec.reference_y is not None:
            axes.axhline(
                spec.reference_y,
                color=self._theme.muted_color,
                linewidth=REFERENCE_LINE_WIDTH,
                linestyle=":",
            )
        if spec.log_y:
            axes.set_yscale("log")
        figure.tight_layout()
        return figure

    def _style_axes(self, axes: Axes, spec: ChartSpec) -> None:
        theme = self._theme
        full_width = spec.size != "half"
        title_size = theme.chart.title_size_pt if full_width else theme.chart.font_size_pt
        pad = TITLE_PAD_PT
        if spec.subtitle:
            # The subtitle sits between the title and the plot; the title moves up to make room.
            width = theme.chart.width_mm if full_width else theme.chart.half_width_mm
            char_mm = theme.chart.small_size_pt * CHAR_MM_PER_PT
            lines = textwrap.wrap(spec.subtitle, int(width * SUBTITLE_WIDTH_SHARE / char_mm))
            axes.annotate(
                "\n".join(lines),
                xy=(0, 1),
                xycoords="axes fraction",
                xytext=(0, TITLE_PAD_PT / 2),
                textcoords="offset points",
                fontsize=theme.chart.small_size_pt,
                color=theme.muted_color,
                ha="left",
                va="bottom",
            )
            pad += len(lines) * theme.chart.small_size_pt * SUBTITLE_LINE_HEIGHT
        axes.set_title(spec.title, fontsize=title_size, loc="left", pad=pad)
        # A half-height chart has no room for a long axis label at the body size.
        label_size = theme.chart.font_size_pt if full_width else theme.chart.small_size_pt
        axes.set_ylabel(spec.y_label, fontsize=label_size)
        axes.grid(True, axis="y", color=theme.grid_color, linewidth=0.6)
        axes.set_axisbelow(True)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)

    def _draw_empty(self, axes: Axes, labels: Sequence[str]) -> None:
        self._label_x(axes, labels)
        axes.text(
            0.5,
            0.5,
            self._empty_note,
            transform=axes.transAxes,
            ha="center",
            va="center",
            color=self._theme.muted_color,
        )

    def _plot_series(self, axes: Axes, one: ChartSeries, index: int, *, markers: bool) -> None:
        """One series in its style: a line, a dashed reference, or pale monthly points."""
        theme = self._theme
        color = theme.palette[(one.color if one.color is not None else index) % len(theme.palette)]
        x = range(len(one.x))
        y = _as_array(one.y)
        if one.style == "points":
            axes.plot(
                x,
                y,
                linestyle="none",
                marker="o",
                markersize=theme.chart.marker_size * POINT_SCALE,
                color=color,
                alpha=POINT_ALPHA,
                label=one.label,
            )
            return
        dashed = one.style == "dashed"
        axes.plot(
            x,
            y,
            color=color,
            linewidth=theme.chart.line_width * (DASHED_WIDTH if dashed else 1.0),
            linestyle="--" if dashed else "-",
            marker="o" if markers and not dashed and len(one.x) <= MAX_MARKED_POINTS else "",
            markersize=theme.chart.marker_size,
            label=one.label,
        )

    def _draw_lines(
        self, axes: Axes, series: Sequence[ChartSeries], *, legend_outside: bool = False
    ) -> None:
        theme = self._theme
        for index, one in enumerate(series):
            self._plot_series(axes, one, index, markers=True)
        self._label_x(axes, _longest_x(series))
        if legend_outside:
            # Many lines leave no empty corner; the legend goes right of the plot instead.
            axes.legend(
                frameon=False,
                fontsize=theme.chart.small_size_pt,
                loc="upper left",
                bbox_to_anchor=(1.0, 1.0),
            )
        else:
            axes.legend(frameon=False, fontsize=theme.chart.small_size_pt, loc="best")

    def _draw_bars(self, axes: Axes, series: ChartSeries, suffix: str) -> None:
        theme = self._theme
        heights = [0.0 if v is None else v for v in series.y]
        colors = [theme.palette[i % len(theme.palette)] for i in range(len(series.y))]
        if len(series.y) > LABEL_ROTATION_THRESHOLD:
            # Many bars (twelve months) read better in one colour, with no value labels.
            colors = [theme.palette[0]] * len(series.y)
        axes.bar(range(len(series.y)), heights, color=colors)
        axes.axhline(0, color=theme.text_color, linewidth=ZERO_LINE_WIDTH)
        if len(series.y) <= LABEL_ROTATION_THRESHOLD:
            for index, value in enumerate(series.y):
                self._annotate_bar(axes, float(index), value, suffix)
            observed = [v for v in series.y if v is not None]
            if observed and min(observed) >= 0 < max(observed):
                axes.set_ylim(top=max(observed) * VALUE_HEADROOM)
        self._label_x(axes, series.x)

    def _draw_grouped_bars(self, axes: Axes, series: Sequence[ChartSeries], suffix: str) -> None:
        theme = self._theme
        count = len(series)
        width = GROUP_WIDTH / count
        for number, one in enumerate(series):
            offset = (number - (count - 1) / 2) * width
            positions = [index + offset for index in range(len(one.y))]
            heights = [0.0 if v is None else v for v in one.y]
            axes.bar(
                positions,
                heights,
                width=width,
                color=theme.palette[number % len(theme.palette)],
                label=one.label,
            )
            for position, value in zip(positions, one.y, strict=True):
                self._annotate_bar(axes, position, value, suffix)
        axes.axhline(0, color=theme.text_color, linewidth=ZERO_LINE_WIDTH)
        self._label_x(axes, _longest_x(series))
        self._legend_clear_of_bars(axes, [v for one in series for v in one.y if v is not None])

    def _legend_clear_of_bars(self, axes: Axes, values: Sequence[float]) -> None:
        """Put the legend in an empty band so it never covers a bar or its label.

        When every bar points the same way, the value axis is stretched on that side and the
        legend sits in the band this frees; mixed signs fall back to matplotlib's choice.
        """
        size = self._theme.chart.small_size_pt
        if values and all(v <= 0 for v in values):
            axes.set_ylim(bottom=min(values) * LEGEND_BAND, top=0)
            axes.legend(fontsize=size, loc="lower center", ncol=2, frameon=False)
        elif values and all(v >= 0 for v in values):
            axes.set_ylim(bottom=0, top=max(values) * LEGEND_BAND)
            axes.legend(fontsize=size, loc="upper center", ncol=2, frameon=False)
        else:
            axes.legend(fontsize=size, loc="best", framealpha=0.85)

    def _annotate_bar(
        self, axes: Axes, position: float, value: float | None, suffix: str = ""
    ) -> None:
        text = self._missing_label if value is None else self._value_label(value, suffix)
        below = value is not None and value < 0
        axes.annotate(
            text,
            (position, 0.0 if value is None else value),
            xytext=(0, -VALUE_LABEL_OFFSET_PT if below else VALUE_LABEL_OFFSET_PT),
            textcoords="offset points",
            ha="center",
            va="top" if below else "bottom",
            fontsize=self._theme.chart.small_size_pt,
        )

    def _value_label(self, value: float, suffix: str) -> str:
        """``-36 %``-style label: whole percents, else precision by magnitude, local separators."""
        text = f"{value:,.0f}" if suffix == "%" else _compact_number(value)
        placeholder = "\0"
        text = (
            text.replace(",", placeholder)
            .replace(".", self._decimal_sep)
            .replace(placeholder, self._thousands_sep)
        )
        return text + suffix

    def _draw_trend(self, axes: Axes, spec: ChartSpec) -> None:
        theme = self._theme
        series = spec.series[0]
        for label in spec.highlight_x:
            if label in series.x:
                index = series.x.index(label)
                axes.axvspan(
                    index - HALF_BAR,
                    index + HALF_BAR,
                    color=theme.highlight_color,
                    alpha=theme.highlight_alpha,
                    linewidth=0,
                )
        axes.plot(
            range(len(series.x)),
            _as_array(series.y),
            color=theme.palette[0],
            linewidth=theme.chart.line_width if len(series.x) <= MAX_MARKED_POINTS else 0.8,
            marker="o" if len(series.x) <= MAX_MARKED_POINTS else "",
            markersize=theme.chart.marker_size,
            label=series.label,
        )
        if spec.trend_y is not None:
            axes.plot(
                range(len(spec.trend_y)),
                _as_array(spec.trend_y),
                color=theme.trend_color,
                linewidth=theme.chart.line_width,
                linestyle="--",
            )
        self._label_x(axes, series.x)

    # -- small multiples ----------------------------------------------------------------------

    def _draw_panels(self, spec: ChartSpec) -> Figure:
        """One panel per edition on a shared value axis, the title and subtitle above all."""
        theme = self._theme
        chart = theme.chart
        count = len(spec.panels)
        columns = 2 if count == 4 else min(MAX_PANEL_COLUMNS, count)  # noqa: PLR2004 -- 2x2
        rows = math.ceil(count / columns)
        height = chart.height_mm * (PANEL_ROW_HEIGHT + EXTRA_ROW_HEIGHT * (rows - 1))
        figure = Figure(figsize=(chart.width_mm / MM_PER_INCH, height / MM_PER_INCH), dpi=chart.dpi)
        grid = figure.subplots(rows, columns, sharey=True, squeeze=False)
        cells = [axes for row in grid for axes in row]
        ticks = max(MIN_PANEL_TICKS, chart.max_x_ticks // (2 * columns))
        for axes, panel in zip(cells, spec.panels, strict=False):
            self._draw_panel(axes, panel, spec, ticks)
        for axes in cells[count:]:
            axes.set_visible(False)
        # One axis label and one legend for all panels, the legend under them.
        figure.supylabel(spec.y_label, fontsize=chart.small_size_pt, x=0.005)
        handles, labels = cells[0].get_legend_handles_labels()
        legend_band = LEGEND_ROW_MM / height
        figure.legend(
            handles,
            labels,
            loc="lower center",
            ncol=len(labels),
            frameon=False,
            fontsize=chart.small_size_pt,
            bbox_to_anchor=(0.5, 0.0),
        )
        top = self._figure_header(figure, spec, height)
        figure.tight_layout(rect=(0.02, legend_band, 1, top))
        return figure

    def _draw_panel(self, axes: Axes, panel: ChartPanel, spec: ChartSpec, ticks: int) -> None:
        """One edition; months that stand out are ringed and listed under the panel title."""
        theme = self._theme
        small = theme.chart.small_size_pt
        pad = TITLE_PAD_PT
        if panel.notes:
            axes.annotate(
                " · ".join(note.text for note in panel.notes),
                xy=(0, 1),
                xycoords="axes fraction",
                xytext=(0, TITLE_PAD_PT / 2),
                textcoords="offset points",
                fontsize=small,
                color=theme.muted_color,
                ha="left",
                va="bottom",
            )
            pad += small * SUBTITLE_LINE_HEIGHT
        axes.set_title(panel.title, fontsize=theme.chart.font_size_pt, loc="left", pad=pad)
        axes.grid(True, axis="y", color=theme.grid_color, linewidth=0.6)
        axes.set_axisbelow(True)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)
        for index, one in enumerate(panel.series):
            self._plot_series(axes, one, index, markers=False)
        if spec.reference_y is not None:
            axes.axhline(
                spec.reference_y,
                color=theme.muted_color,
                linewidth=REFERENCE_LINE_WIDTH,
                linestyle=":",
            )
        labels = _longest_x(panel.series)
        for note in panel.notes:
            if note.x not in labels:
                continue
            position = labels.index(note.x)
            target = panel.series[min(note.series, len(panel.series) - 1)]
            value = target.y[position] if position < len(target.y) else None
            if value is None:
                continue
            axes.plot(
                [position],
                [value],
                marker="o",
                markersize=theme.chart.marker_size * RING_SCALE,
                markerfacecolor="none",
                markeredgecolor=theme.text_color,
                markeredgewidth=0.8,
                linestyle="none",
            )
        self._label_x(axes, labels, max_ticks=ticks)

    def _figure_header(self, figure: Figure, spec: ChartSpec, height_mm: float) -> float:
        """Title and subtitle across the whole figure; returns the top of the plotting area."""
        theme = self._theme
        chart = theme.chart
        figure.text(0.01, 0.99, spec.title, fontsize=chart.title_size_pt, ha="left", va="top")
        used_mm = chart.title_size_pt * PT_TO_MM * SUBTITLE_LINE_HEIGHT + HEADER_GAP_MM
        if spec.subtitle:
            char_mm = chart.small_size_pt * CHAR_MM_PER_PT
            lines = textwrap.wrap(
                spec.subtitle, int(chart.width_mm * SUBTITLE_WIDTH_SHARE / char_mm)
            )
            figure.text(
                0.01,
                1 - used_mm / height_mm,
                "\n".join(lines),
                fontsize=chart.small_size_pt,
                color=theme.muted_color,
                ha="left",
                va="top",
            )
            used_mm += len(lines) * chart.small_size_pt * PT_TO_MM * SUBTITLE_LINE_HEIGHT
        return 1 - (used_mm + HEADER_GAP_MM) / height_mm

    # -- before and after, size and change ---------------------------------------------------

    def _draw_dumbbell(self, axes: Axes, spec: ChartSpec) -> None:
        """Per category, the earlier value and the later one joined by a line, top to bottom."""
        theme = self._theme
        before, after = spec.series
        count = len(before.x)
        positions = [count - 1 - i for i in range(count)]
        for position, start, end in zip(positions, before.y, after.y, strict=True):
            if start is None or end is None:
                continue
            axes.plot(
                [start, end],
                [position, position],
                color=theme.grid_color,
                linewidth=DUMBBELL_LINE_WIDTH,
                zorder=1,
            )
        for index, one in enumerate((before, after)):
            color = theme.palette[
                (one.color if one.color is not None else index) % len(theme.palette)
            ]
            xs = [v for v in one.y if v is not None]
            ys = [p for p, v in zip(positions, one.y, strict=True) if v is not None]
            axes.scatter(xs, ys, color=color, zorder=2, label=one.label, s=28)
        for position, end in zip(positions, after.y, strict=True):
            if end is not None:
                axes.annotate(
                    self._value_label(end, spec.value_suffix),
                    (end, position),
                    xytext=(LABEL_OFFSET_PT, LABEL_OFFSET_PT),
                    textcoords="offset points",
                    fontsize=theme.chart.small_size_pt,
                )
        axes.set_yticks(positions)
        axes.set_yticklabels(before.x, fontsize=theme.chart.small_size_pt)
        axes.set_ylim(-0.7, count - 0.3)
        axes.grid(True, axis="x", color=theme.grid_color, linewidth=0.6)
        axes.grid(False, axis="y")
        if spec.x_label:
            axes.set_xlabel(spec.x_label, fontsize=theme.chart.small_size_pt)
        axes.legend(frameon=False, fontsize=theme.chart.small_size_pt, loc="best")

    def _draw_scatter(self, axes: Axes, spec: ChartSpec) -> None:
        """Labelled points: size of the share (often on a log axis) against its change."""
        theme = self._theme
        axes.scatter(
            [p.x for p in spec.points],
            [p.y for p in spec.points],
            color=theme.palette[0],
            s=28,
            zorder=2,
        )
        for point in spec.points:
            axes.annotate(
                point.label,
                (point.x, point.y),
                xytext=(LABEL_OFFSET_PT, LABEL_OFFSET_PT),
                textcoords="offset points",
                fontsize=theme.chart.small_size_pt,
            )
        if spec.log_x:
            axes.set_xscale("log")
            # Plain numbers ("40", "100") instead of "4 x 10^1".
            axes.xaxis.set_major_formatter(FuncFormatter(lambda v, _: _compact_number(v)))
            axes.xaxis.set_minor_formatter(FuncFormatter(lambda v, _: _compact_number(v)))
            axes.tick_params(axis="x", which="both", labelsize=theme.chart.small_size_pt)
        if spec.x_label:
            axes.set_xlabel(spec.x_label, fontsize=theme.chart.small_size_pt)
        axes.grid(True, axis="x", color=theme.grid_color, linewidth=0.6)

    def _label_x(self, axes: Axes, labels: Sequence[str], *, max_ticks: int | None = None) -> None:
        """Show at most ``max_x_ticks`` evenly spaced labels; rotate when they would collide."""
        if not labels:
            return
        step = max(1, math.ceil(len(labels) / (max_ticks or self._theme.chart.max_x_ticks)))
        ticks = list(range(0, len(labels), step))
        rotate = len(ticks) > LABEL_ROTATION_THRESHOLD
        axes.set_xticks(ticks)
        axes.set_xticklabels(
            [labels[i] for i in ticks],
            rotation=LABEL_ROTATION_DEG if rotate else 0,
            ha="right" if rotate else "center",
            fontsize=self._theme.chart.small_size_pt,
        )
        axes.set_xlim(-HALF_BAR, len(labels) - HALF_BAR)

    def _save(self, figure: Figure, chart_id: str, output_dir: Path) -> list[Path]:
        png = output_dir / f"{chart_id}.png"
        svg = output_dir / f"{chart_id}.svg"
        figure.savefig(png, format="png", dpi=self._theme.chart.dpi, metadata=PNG_METADATA)
        figure.savefig(svg, format="svg", metadata=SVG_METADATA)
        return [png, svg]


def _is_empty(spec: ChartSpec) -> bool:
    return all(value is None for series in spec.series for value in series.y)


def _longest_x(series: Sequence[ChartSeries]) -> Sequence[str]:
    """Period labels of the longest series; series of one chart share the same window."""
    return max((one.x for one in series), key=len)


def _as_array(values: Sequence[float | None]) -> NDArray[np.float64]:
    """Convert gaps to NaN so matplotlib breaks the line instead of interpolating across."""
    return np.array([np.nan if v is None else v for v in values], dtype=np.float64)


def _compact_number(value: float) -> str:
    """Value label with precision that suits its magnitude (``1,234``, ``12.3``, ``0.45``)."""
    magnitude = abs(value)
    if magnitude >= LARGE_VALUE:
        return f"{value:,.0f}"
    if magnitude >= MEDIUM_VALUE:
        return f"{value:.1f}"
    return f"{value:.2f}"
