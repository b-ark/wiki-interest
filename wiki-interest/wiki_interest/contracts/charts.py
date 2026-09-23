"""Declarative chart specifications.

The application decides *what* to plot and expresses it here; a
:class:`~wiki_interest.ports.renderers.ChartRenderer` decides *how*. Keeping the spec as data
makes chart content testable without matplotlib and lets the report cite exactly what was drawn.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["ChartKind", "ChartSeries", "ChartSize", "ChartSpec"]

ChartKind = Literal["lines", "bars", "grouped_bars", "trend"]
"""``lines``: several series over time; ``bars``: one value per category; ``grouped_bars``:
several series side by side per category; ``trend``: one series with its fitted trend line
and highlighted periods."""

ChartSize = Literal["wide", "half"]
"""``wide`` spans the page; ``half`` is drawn for a two-column grid."""


class ChartSeries(BaseModel):
    """One plotted series: ``x`` holds category or period labels, ``y`` the values, gaps as None."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str
    x: list[str]
    y: list[float | None]


class ChartSpec(BaseModel):
    """A chart to render.

    Attributes:
        id: File-name-safe identifier, unique within a run.
        kind: Chart type.
        title: Chart title, already localised.
        subtitle: One line under the title saying what the measure is and why, or ``None``.
        y_label: Axis label, already localised.
        series: Data to plot; ``bars`` and ``trend`` use exactly one series.
        trend_y: Fitted trend values aligned with ``series[0].x`` (``trend`` charts only).
        highlight_x: Labels of periods to shade as spikes (``trend`` charts only).
        footnote: Source and period line under the chart.
        size: Width class; the renderer maps it to physical dimensions.
        log_y: Logarithmic value axis, for series that differ by orders of magnitude.
        reference_y: Value of a horizontal reference line (100 for an index, 0 for change).
        value_suffix: Appended to bar value labels (``%``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    kind: ChartKind
    title: str
    subtitle: str | None = None
    y_label: str
    series: list[ChartSeries] = Field(min_length=1)
    trend_y: list[float | None] | None = None
    highlight_x: list[str] = Field(default_factory=list)
    footnote: str | None = None
    size: ChartSize = "wide"
    log_y: bool = False
    reference_y: float | None = None
    value_suffix: str = ""
