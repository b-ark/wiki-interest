"""Matplotlib implementation of :class:`~wiki_interest.ports.renderers.ChartRenderer`.

Charts are drawn head-less on the ``Agg`` backend from a :class:`ChartSpec` and written as a
PNG (for the PDF and chat) and an SVG (for documents). Output is deterministic: no
timestamps in metadata, a fixed ``svg.hashsalt`` and no dependence on the process locale, so
a re-run with the same data yields byte-identical files and golden tests stay green.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # Must precede any pyplot/figure import: never rely on a display.

import numpy as np
from matplotlib.figure import Figure
from matplotlib.typing import RcKeyType

from wiki_interest.adapters.report_theme import ReportTheme
from wiki_interest.contracts.charts import ChartSeries, ChartSpec
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
FOOTNOTE_BAND = 0.08
"""Share of the figure height reserved under the axes for the source/period footnote."""
LABEL_ROTATION_THRESHOLD = 6
"""Above this many categories the x labels are rotated to stay legible."""
LABEL_ROTATION_DEG = 45
VALUE_LABEL_OFFSET_PT = 3
ZERO_LINE_WIDTH = 0.8
LARGE_VALUE = 100.0
MEDIUM_VALUE = 10.0
HALF_BAR = 0.5


class MatplotlibChartRenderer:
    """Renders ``lines``, ``bars`` and ``trend`` charts in the shared report theme.

    Args:
        theme_path: Theme JSON to use; ``None`` selects ``assets/report_theme.json``.
        empty_note: Text drawn on the axes when every value of the spec is missing. Passed in
            (already localised) because the renderer itself knows nothing about languages.
        missing_label: Value label for a single missing bar.
    """

    def __init__(
        self,
        theme_path: Path | None = None,
        *,
        empty_note: str = "No data",
        missing_label: str = "n/a",
    ) -> None:
        self._theme = ReportTheme.load(theme_path)
        self._empty_note = empty_note
        self._missing_label = missing_label

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
        figure = Figure(
            figsize=(chart.width_mm / MM_PER_INCH, chart.height_mm / MM_PER_INCH), dpi=chart.dpi
        )
        axes = figure.add_subplot()
        self._style_axes(axes, spec)
        if _is_empty(spec):
            self._draw_empty(axes, spec.series[0].x)
        elif spec.kind == "bars":
            self._draw_bars(axes, spec.series[0])
        elif spec.kind == "trend":
            self._draw_trend(axes, spec)
        else:
            self._draw_lines(axes, spec.series)
        self._add_footnote(figure, spec.footnote)
        return figure

    def _style_axes(self, axes: Axes, spec: ChartSpec) -> None:
        theme = self._theme
        axes.set_title(spec.title, fontsize=theme.chart.title_size_pt, loc="left", pad=10)
        axes.set_ylabel(spec.y_label)
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

    def _draw_lines(self, axes: Axes, series: Sequence[ChartSeries]) -> None:
        theme = self._theme
        for index, one in enumerate(series):
            axes.plot(
                range(len(one.x)),
                _as_array(one.y),
                color=theme.palette[index % len(theme.palette)],
                linewidth=theme.chart.line_width,
                marker="o",
                markersize=theme.chart.marker_size,
                label=one.label,
            )
        self._label_x(axes, _longest_x(series))
        axes.legend(frameon=False, fontsize=theme.chart.small_size_pt, loc="best")

    def _draw_bars(self, axes: Axes, series: ChartSeries) -> None:
        theme = self._theme
        heights = [0.0 if v is None else v for v in series.y]
        colors = [theme.palette[i % len(theme.palette)] for i in range(len(series.y))]
        axes.bar(range(len(series.y)), heights, color=colors)
        axes.axhline(0, color=theme.text_color, linewidth=ZERO_LINE_WIDTH)
        for index, value in enumerate(series.y):
            self._annotate_bar(axes, index, value)
        self._label_x(axes, series.x)

    def _annotate_bar(self, axes: Axes, index: int, value: float | None) -> None:
        text = self._missing_label if value is None else _compact_number(value)
        below = value is not None and value < 0
        axes.annotate(
            text,
            (index, 0.0 if value is None else value),
            xytext=(0, -VALUE_LABEL_OFFSET_PT if below else VALUE_LABEL_OFFSET_PT),
            textcoords="offset points",
            ha="center",
            va="top" if below else "bottom",
            fontsize=self._theme.chart.small_size_pt,
        )

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
            linewidth=theme.chart.line_width,
            marker="o",
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

    def _label_x(self, axes: Axes, labels: Sequence[str]) -> None:
        """Show at most ``max_x_ticks`` evenly spaced labels; rotate when they would collide."""
        if not labels:
            return
        step = max(1, math.ceil(len(labels) / self._theme.chart.max_x_ticks))
        ticks = list(range(0, len(labels), step))
        rotate = len(labels) > LABEL_ROTATION_THRESHOLD
        axes.set_xticks(ticks)
        axes.set_xticklabels(
            [labels[i] for i in ticks],
            rotation=LABEL_ROTATION_DEG if rotate else 0,
            ha="right" if rotate else "center",
            fontsize=self._theme.chart.small_size_pt,
        )
        axes.set_xlim(-HALF_BAR, len(labels) - HALF_BAR)

    def _add_footnote(self, figure: Figure, footnote: str | None) -> None:
        band = FOOTNOTE_BAND if footnote else 0.0
        figure.tight_layout(rect=(0, band, 1, 1))
        if footnote:
            figure.text(
                0.01,
                0.01,
                footnote,
                fontsize=self._theme.chart.small_size_pt,
                color=self._theme.muted_color,
                ha="left",
                va="bottom",
            )

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
