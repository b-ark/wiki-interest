"""Matplotlib implementation of :class:`~wiki_interest.ports.renderers.ChartRenderer`.

Charts are drawn head-less on the ``Agg`` backend from a :class:`ChartSpec` and written as a
PNG (for the PDF and chat) and an SVG (for documents). Output is deterministic: no
timestamps in metadata, a fixed ``svg.hashsalt`` and no dependence on the process locale, so
a re-run with the same data yields byte-identical files and golden tests stay green.
"""

from __future__ import annotations

import math
import textwrap
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import matplotlib

matplotlib.use("Agg")  # Must precede any pyplot/figure import: never rely on a display.

import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
from matplotlib.typing import RcKeyType

from wiki_interest.adapters.report_theme import ReportTheme
from wiki_interest.contracts.charts import ChartSeries, ChartSpec, ShareYears
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
"""A wide line chart with more series than this gets its legend under the plot."""
MAX_LEGEND_COLUMNS = 5
"""Entries per row of a legend under the plot."""
FRAME_LEFT_MM = 22.0
FRAME_RIGHT_MM = 3.5
"""Where the plot of every full-width chart starts and ends: charts stacked in the report
line up. The left edge leaves room for the value labels and the axis label."""
FRAME_MIN_MARGIN_MM = 1.0
"""The least room left of the leftmost label before the plot moves right to make more."""
STRIP_X_TICKS = 6
"""A strip labels at most this many months: upright, they leave the plot more of its height."""
MIN_PLOT_MM = 15.0
"""The lowest a plot is drawn: a chart asked to be lower grows back until every row of it
has this much, and the PDF shrinks it instead."""
MAX_REGROWS = 3
PT_TO_MM = 0.3528
HEADER_GAP_MM = 2.0
POINT_ALPHA = 0.35
POINT_SCALE = 0.8
DASHED_WIDTH = 0.9
LOG_TICK_STEPS = (1.0, 2.0, 3.0, 5.0, 7.0)
"""Where a log axis is labelled within each decade: round values, never two crowding."""
SCATTER_MARGIN = 0.12
"""Room around the outermost points of a scatter, so they and their labels are not cut."""
LEGEND_ROW_MM = 7.0
LABEL_OFFSET_PT = 4
SHARE_HEIGHT_SCALE = 1.4
"""The main chart is this many times a wide chart's height: legend and notes under it."""
SHARE_RIGHT_MM = 14.0
"""Room right of the main chart's plot for the audiences' names at the ends of their lines."""
SHARE_HEADROOM = 1.12
"""Room over the highest year or month for the value labels."""
STEP_LINE_WIDTH = 0.6
STEP_LINE_ALPHA = 0.55
STEP_LABEL_BAND = 0.14
"""More room at the top, as a share of the highest value, when a step's label runs there."""
MONTH_LINE_WIDTH = 0.7
SEGMENT_END = 0.9
"""A year's segment ends this far into its last month, so the next year's starts clear of it."""
PARTIAL_DASHES = (0, (3, 2))
"""A partial year is dashed: its months lack part of the season, not every year is comparable."""
CLOSE_SHARE = 0.1
"""Two values closer than this share of the axis would print on top of each other."""
VALUE_UNDER_PT = 11
VALUE_HIGHER_PT = 14
END_LABEL_GAP = 0.07
"""Least distance between two audiences' names at the lines' ends, as a share of the axis."""
NOTE_LINE_HEIGHT = 1.4
NOTE_START = 0.36
"""Where the note under the main chart starts, right of the legend's column (figure share)."""
LEGEND_SPACING = 0.3
LEGEND_HANDLE = 1.8
MARK_SCALE = 1.6
"""A burst's point is this many times the theme's marker, to stand out of the pale line."""


class MatplotlibChartRenderer:
    """Renders the charts of :data:`~wiki_interest.contracts.charts.ChartKind` in the report theme.

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
        """The figure of ``spec``; one asked to be low gets taller until its plots are legible."""
        if spec.height_mm is None:
            return self._draw_figure(spec)
        with warnings.catch_warnings():
            # A height too low for the labels is expected here: the figure grows back below.
            warnings.filterwarnings("ignore", message="Tight layout not applied")
            figure = self._draw_figure(spec)
            for _ in range(MAX_REGROWS):
                taller = _taller(figure)
                if taller is None:
                    break
                spec = spec.model_copy(update={"height_mm": taller})
                figure = self._draw_figure(spec)
        return figure

    def _draw_figure(self, spec: ChartSpec) -> Figure:
        chart = self._theme.chart
        if spec.kind == "share_years":
            return self._draw_share_years(spec)
        width, height = {
            "half": (chart.half_width_mm, chart.half_height_mm),
            "strip": (chart.width_mm, chart.strip_height_mm),
        }.get(spec.size, (chart.width_mm, chart.height_mm))
        full_width = spec.size != "half"
        legend_under = _legend_under_plot(spec)
        rows = math.ceil(len(spec.series) / MAX_LEGEND_COLUMNS) if legend_under else 0
        legend_mm = rows * LEGEND_ROW_MM
        height = spec.height_mm or height + legend_mm
        figure = Figure(figsize=(width / MM_PER_INCH, height / MM_PER_INCH), dpi=chart.dpi)
        axes = figure.add_subplot()
        self._style_axes(axes, spec, title=not full_width)
        self._draw_kind(axes, spec, legend=not legend_under)
        if legend_under:
            self._legend_under(figure, axes)
        if spec.reference_y is not None:
            axes.axhline(
                spec.reference_y,
                color=self._theme.muted_color,
                linewidth=REFERENCE_LINE_WIDTH,
                linestyle=":",
            )
        if spec.log_y:
            axes.set_yscale("log")
        if full_width:
            top = self._figure_header(figure, spec, height)
            figure.tight_layout(rect=(0, legend_mm / height, 1, top))
            self._frame(figure, width)
        else:
            figure.tight_layout()
        return figure

    def _draw_kind(self, axes: Axes, spec: ChartSpec, *, legend: bool) -> None:
        """The data of one single-axes chart, by its kind."""
        if spec.kind == "scatter":
            self._draw_scatter(axes, spec)
        elif _is_empty(spec):
            self._draw_empty(axes, spec.series[0].x)
        elif spec.kind == "bars":
            self._draw_bars(axes, spec.series[0], spec.value_suffix)
        elif spec.kind == "grouped_bars":
            self._draw_grouped_bars(axes, spec.series, spec.value_suffix)
        elif spec.kind == "trend":
            self._draw_trend(axes, spec)
        else:
            ticks = STRIP_X_TICKS if spec.size == "strip" else None
            self._draw_lines(axes, spec.series, legend=legend, max_ticks=ticks)

    def _frame(self, figure: Figure, width_mm: float) -> None:
        """Put the plot between the edges every full-width chart shares.

        Value labels wider than the left margin (long category names) push the plot right by
        as much as they would stick out, rather than get cut.
        """
        figure.subplots_adjust(left=FRAME_LEFT_MM / width_mm, right=1 - FRAME_RIGHT_MM / width_mm)
        FigureCanvasAgg(figure)  # a canvas to measure the labels on
        labels = [
            text
            for axes in figure.axes
            if axes.get_visible()
            for text in (*axes.get_yticklabels(), axes.yaxis.label)
            if text.get_text()
        ]
        if not labels:
            return
        start_inches = min(t.get_window_extent().x0 for t in labels) / figure.dpi
        overflow = FRAME_MIN_MARGIN_MM - start_inches * MM_PER_INCH
        if overflow > 0:
            figure.subplots_adjust(left=(FRAME_LEFT_MM + overflow) / width_mm)

    def _legend_under(self, figure: Figure, axes: Axes) -> None:
        """The legend in rows under the plot, as the panels have it."""
        handles, labels = axes.get_legend_handles_labels()
        figure.legend(
            handles,
            labels,
            loc="lower center",
            ncol=min(len(labels), MAX_LEGEND_COLUMNS),
            frameon=False,
            fontsize=self._theme.chart.small_size_pt,
            bbox_to_anchor=(0.5, 0.0),
        )

    def _style_axes(self, axes: Axes, spec: ChartSpec, *, title: bool) -> None:
        """Grid, spines and the value label; with ``title``, the title and subtitle too.

        Full-width charts put the title and subtitle across the figure instead (see
        :meth:`_figure_header`), so they start at the same place in every chart.
        """
        theme = self._theme
        full_width = spec.size != "half"
        if title:
            pad = TITLE_PAD_PT
            if spec.subtitle:
                # The subtitle sits between the title and the plot; the title moves up for it.
                char_mm = theme.chart.small_size_pt * CHAR_MM_PER_PT
                width = int(theme.chart.half_width_mm * SUBTITLE_WIDTH_SHARE / char_mm)
                lines = textwrap.wrap(spec.subtitle, width)
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
            axes.set_title(spec.title, fontsize=theme.chart.font_size_pt, loc="left", pad=pad)
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
        self,
        axes: Axes,
        series: Sequence[ChartSeries],
        *,
        legend: bool = True,
        max_ticks: int | None = None,
    ) -> None:
        """The lines; with ``legend``, their legend in the emptiest corner of the plot."""
        for index, one in enumerate(series):
            self._plot_series(axes, one, index, markers=True)
        self._label_x(axes, _longest_x(series), max_ticks=max_ticks)
        if legend:
            axes.legend(frameon=False, fontsize=self._theme.chart.small_size_pt, loc="best")

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
        return self._localised(text) + suffix

    def _tick_label(self, value: float) -> str:
        """A round axis value as the report writes numbers: ``50``, ``1 000``, ``0,5``."""
        return self._localised(f"{value:,.0f}" if value >= 1 else f"{value:g}")

    def _localised(self, text: str) -> str:
        """``text`` written with ``,`` and ``.`` switched to the report's separators."""
        placeholder = "\0"
        return (
            text.replace(",", placeholder)
            .replace(".", self._decimal_sep)
            .replace(placeholder, self._thousands_sep)
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

    # -- the attention share by calendar year ----------------------------------------------

    def _draw_share_years(self, spec: ChartSpec) -> Figure:
        """Months as a pale line, each calendar year as a segment at its average, per audience.

        The value of each year stands over its segment (the lower of two close ones under
        it), the audience's name at the end of its line, the last months shaded; the steps
        and bursts the text cites are marked. A burst above the other months is drawn at the
        top edge with its value, so it does not flatten everything else.
        """
        share = spec.share
        assert share is not None
        theme = self._theme
        chart = theme.chart
        small = chart.small_size_pt
        # The legend in a column on the left, the note beside it: one band under the plot.
        rows = max(len(spec.legend), spec.note.count("\n") + 1 if spec.note else 0)
        bottom_mm = rows * small * PT_TO_MM * NOTE_LINE_HEIGHT + HEADER_GAP_MM
        height = spec.height_mm or chart.height_mm * SHARE_HEIGHT_SCALE
        figure = Figure(figsize=(chart.width_mm / MM_PER_INCH, height / MM_PER_INCH), dpi=chart.dpi)
        axes = figure.add_subplot()
        axes.set_ylabel(spec.y_label, fontsize=small)
        axes.grid(True, axis="y", color=theme.grid_color, linewidth=0.6)
        axes.set_axisbelow(True)
        for side in ("top", "right"):
            axes.spines[side].set_visible(False)

        spikes = {(m.line, m.x) for m in share.marks if m.kind == "spike"}
        top = 0.0
        for index, line in enumerate(share.lines):
            color = theme.palette[index % len(theme.palette)]
            x = [_month_number(m) for m in line.x]
            axes.plot(
                x, _as_array(line.y), color=color, linewidth=MONTH_LINE_WIDTH, alpha=POINT_ALPHA
            )
            for segment in line.years:
                axes.hlines(
                    segment.value,
                    _month_number(segment.start),
                    _month_number(segment.end) + SEGMENT_END,
                    color=color,
                    linewidth=chart.line_width,
                    linestyles=PARTIAL_DASHES if segment.partial else "solid",
                )
                top = max(top, segment.value)
            usual = [
                v
                for m, v in zip(line.x, line.y, strict=True)
                if v is not None and (index, m) not in spikes
            ]
            top = max(top, *usual) if usual else top
        labelled_step = any(
            m.kind == "step" and label is not None
            for m, label in zip(share.marks, spec.mark_labels, strict=False)
        )
        # A step's label runs along the top edge: a band over the values keeps it clear.
        headroom = SHARE_HEADROOM + (STEP_LABEL_BAND if labelled_step else 0.0)
        ceiling = top * headroom if top > 0 else 1.0
        axes.set_ylim(0, ceiling)

        self._share_values(axes, share, ceiling)
        self._share_marks(axes, spec, ceiling)
        last = max(_month_number(line.x[-1]) for line in share.lines)
        axes.axvspan(
            last - share.recent_months + 1 - HALF_BAR,
            last + HALF_BAR,
            color=theme.highlight_color,
            alpha=theme.highlight_alpha,
            linewidth=0,
        )
        self._share_ends(axes, share, ceiling)
        self._share_years_axis(axes, spec, last)
        axes.yaxis.set_major_formatter(FuncFormatter(lambda v, _: self._tick_label(v)))
        axes.tick_params(axis="y", labelsize=small)

        handles = [
            Line2D([], [], color=theme.muted_color, linewidth=chart.line_width),
            Line2D([], [], color=theme.muted_color, linewidth=MONTH_LINE_WIDTH, alpha=0.6),
            Patch(color=theme.highlight_color, alpha=theme.highlight_alpha, linewidth=0),
        ]
        figure.legend(
            handles,
            spec.legend,
            loc="lower left",
            ncol=1,
            frameon=False,
            fontsize=small,
            labelcolor=theme.muted_color,
            bbox_to_anchor=(0.0, 0.0),
            borderaxespad=0.2,
            labelspacing=LEGEND_SPACING,
            handlelength=LEGEND_HANDLE,
        )
        if spec.note:
            figure.text(
                NOTE_START,
                0.01,
                spec.note,
                fontsize=small,
                ha="left",
                va="bottom",
                linespacing=NOTE_LINE_HEIGHT,
            )
        header = self._figure_header(figure, spec, height)
        figure.tight_layout(rect=(0, bottom_mm / height, 1, header))
        self._frame(figure, chart.width_mm)
        figure.subplots_adjust(right=1 - SHARE_RIGHT_MM / chart.width_mm)
        return figure

    def _share_values(self, axes: Axes, share: ShareYears, ceiling: float) -> None:
        """Each year's value over its segment; of two close values, the lower goes under."""
        small = self._theme.chart.small_size_pt
        close = ceiling * CLOSE_SHARE
        for index, line in enumerate(share.lines):
            color = self._theme.palette[index % len(self._theme.palette)]
            for segment in line.years:
                others = [
                    s.value
                    for j, other in enumerate(share.lines)
                    if j != index
                    for s in other.years
                    if s.year == segment.year
                ]
                above = [o for o in others if 0 < o - segment.value < close]
                below = [o for o in others if 0 <= segment.value - o < close]
                if above and segment.value > ceiling * CLOSE_SHARE:
                    offset = -VALUE_UNDER_PT
                elif below and min(below) <= ceiling * CLOSE_SHARE:
                    offset = VALUE_HIGHER_PT  # the lower one stays over its segment: go higher
                else:
                    offset = VALUE_LABEL_OFFSET_PT
                middle = (_month_number(segment.start) + _month_number(segment.end)) / 2
                axes.annotate(
                    self._share_value(segment.value, absolute=share.absolute),
                    (middle + HALF_BAR, segment.value),
                    xytext=(0, offset),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    color=color,
                    fontsize=small,
                    # A white ground keeps a line crossing the number from cutting it.
                    bbox={"boxstyle": "square,pad=0.1", "facecolor": "white", "linewidth": 0},
                    zorder=3,
                )

    def _share_marks(self, axes: Axes, spec: ChartSpec, ceiling: float) -> None:
        """The steps and bursts the text cites: a dashed line or a point, with its label.

        A burst the text does not cite gets no label, but when it rises over the top edge its
        value stands there, so the line leaving the chart is not left unexplained.
        """
        share = spec.share
        assert share is not None
        small = self._theme.chart.small_size_pt
        for mark, label in zip(share.marks, spec.mark_labels, strict=False):
            color = self._theme.palette[mark.line % len(self._theme.palette)]
            x = _month_number(mark.x)
            if mark.kind == "step":
                if label is None:
                    continue
                # Thin, pale and under the labels: it points to a month, it is not data.
                axes.axvline(
                    x,
                    color=color,
                    linewidth=STEP_LINE_WIDTH,
                    linestyle=(0, (4, 3)),
                    alpha=STEP_LINE_ALPHA,
                    zorder=0,
                )
                axes.annotate(
                    label,
                    (x, ceiling),
                    xytext=(3, -2),
                    textcoords="offset points",
                    color=color,
                    fontsize=small,
                    va="top",
                )
                continue
            if mark.y is None:
                continue
            over = mark.y > ceiling
            if label is None and not over:
                continue
            y = min(mark.y, ceiling)
            axes.plot(
                [x],
                [y],
                marker="^" if over else "o",
                color=color,
                markersize=self._theme.chart.marker_size * MARK_SCALE,
                clip_on=False,
            )
            value = self._share_value(mark.y, absolute=share.absolute)
            text = label or ""
            if over:
                text = f"{text} ({value})" if text else value
            axes.annotate(
                text,
                (x, y),
                xytext=(LABEL_OFFSET_PT + 2, -2),
                textcoords="offset points",
                va="top",
                color=color,
                fontsize=small,
            )

    def _share_ends(self, axes: Axes, share: ShareYears, ceiling: float) -> None:
        """Each audience's name at the end of its line, moved apart when they would touch."""
        ends = sorted(
            (line.years[-1].value, index, line.label) for index, line in enumerate(share.lines)
        )
        placed: list[float] = []
        for value, index, label in ends:
            y = value
            if placed and y - placed[-1] < ceiling * END_LABEL_GAP:
                y = placed[-1] + ceiling * END_LABEL_GAP
            placed.append(y)
            end = _month_number(share.lines[index].years[-1].end) + SEGMENT_END
            axes.annotate(
                label,
                (end, y),
                xytext=(LABEL_OFFSET_PT * 2, 0),
                textcoords="offset points",
                color=self._theme.palette[index % len(self._theme.palette)],
                fontsize=self._theme.chart.font_size_pt,
                fontweight="bold",
                va="center",
                annotation_clip=False,
            )

    def _share_years_axis(self, axes: Axes, spec: ChartSpec, last: float) -> None:
        """One label per calendar year, under its middle."""
        share = spec.share
        assert share is not None
        spans: dict[int, tuple[float, float]] = {}
        for line in share.lines:
            for segment in line.years:
                start, end = _month_number(segment.start), _month_number(segment.end)
                known = spans.get(segment.year, (start, end))
                spans[segment.year] = (min(known[0], start), max(known[1], end))
        years = sorted(spans)
        axes.set_xticks([(spans[y][0] + spans[y][1]) / 2 + HALF_BAR for y in years])
        axes.set_xticklabels(
            spec.year_labels[: len(years)], fontsize=self._theme.chart.small_size_pt
        )
        axes.tick_params(axis="x", length=0)
        axes.set_xlim(spans[years[0]][0] - HALF_BAR, last + 1 + HALF_BAR)

    def _share_value(self, value: float, *, absolute: bool) -> str:
        """``23.6``, ``145``, ``4,300`` in the report's number style."""
        if absolute or value >= LARGE_VALUE:
            return self._localised(f"{value:,.0f}")
        return self._localised(f"{value:,.1f}")

    # -- size and change ------------------------------------------------------------------

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
        axes.margins(x=SCATTER_MARGIN, y=SCATTER_MARGIN * 2)
        if spec.log_x:
            axes.set_xscale("log")
            # Round values in the report's number style ("50", "70", "100"), not "4 x 10^1"
            # or matplotlib's minor labels, which put "90.0" against "100".
            axes.xaxis.set_major_locator(LogLocator(subs=LOG_TICK_STEPS))
            axes.xaxis.set_major_formatter(FuncFormatter(lambda v, _: self._tick_label(v)))
            axes.xaxis.set_minor_formatter(NullFormatter())
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


def _taller(figure: Figure) -> float | None:
    """The height in millimetres at which every row of plots gets ``MIN_PLOT_MM``.

    ``None`` when every row has that already.
    """
    height_mm = figure.get_figheight() * MM_PER_INCH
    visible = [a for a in figure.axes if a.get_visible()]
    rows = len({round(a.get_position().y0, 3) for a in visible})
    plot_mm = min(a.get_position().height for a in visible) * height_mm
    short = MIN_PLOT_MM - plot_mm
    return height_mm + short * rows + 1.0 if short > 0 else None


def _legend_under_plot(spec: ChartSpec) -> bool:
    """Whether the legend goes in a band under the plot rather than inside it.

    A strip is too low for a legend inside, and a wide chart with many lines has no empty
    corner. The band is added to the height, so the plot keeps its size.
    """
    if spec.kind != "lines" or _is_empty(spec):
        return False
    return spec.size == "strip" or (spec.size == "wide" and len(spec.series) > MAX_INSIDE_LEGEND)


def _is_empty(spec: ChartSpec) -> bool:
    return all(value is None for series in spec.series for value in series.y)


def _longest_x(series: Sequence[ChartSeries]) -> Sequence[str]:
    """Period labels of the longest series; series of one chart share the same window."""
    return max((one.x for one in series), key=len)


def _month_number(month: str) -> float:
    """``2026-08`` as a count of months, the horizontal axis of the main chart."""
    year, number = month.split("-")
    return int(year) * 12 + int(number) - 1


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
