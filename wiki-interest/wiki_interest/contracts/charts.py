"""Declarative chart specifications.

The application decides *what* to plot and expresses it here; a
:class:`~wiki_interest.ports.renderers.ChartRenderer` decides *how*. Keeping the spec as data
makes chart content testable without matplotlib and lets the report cite exactly what was drawn.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

__all__ = [
    "ChartKind",
    "ChartNote",
    "ChartPanel",
    "ChartPoint",
    "ChartSeries",
    "ChartSize",
    "ChartSpec",
    "SeriesStyle",
]

ChartKind = Literal["lines", "bars", "grouped_bars", "trend", "panels", "dumbbell", "scatter"]
"""``lines``: several series over time; ``bars``: one value per category; ``grouped_bars``:
several series side by side per category; ``trend``: one series with its fitted trend line
and highlighted periods; ``panels``: small multiples, one panel of lines per edition on a
shared scale; ``dumbbell``: two values per category joined by a line (before and after);
``scatter``: labelled points on two numeric axes."""

ChartSize = Literal["wide", "strip", "half"]
"""``wide`` spans the page; ``strip`` spans it at half the height (a second chart under the
main one); ``half`` is drawn for a two-column grid."""

SeriesStyle = Literal["line", "dashed", "points"]
"""``line``: the series that matters; ``dashed``: a reference to compare against;
``points``: pale monthly observations behind a smoothed line of the same colour."""


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ChartSeries(_Model):
    """One plotted series: ``x`` holds category or period labels, ``y`` the values, gaps as None.

    ``color`` groups series that belong together (the monthly points and the smoothed line of
    the same article); series without one take the next colour of the palette.
    """

    label: str
    x: list[str]
    y: list[float | None]
    style: SeriesStyle = "line"
    color: int | None = None


class ChartNote(_Model):
    """A label attached to one period of a panel: ``2024-05 ×1.9 possibly bots``.

    ``series`` is the index of the panel series whose point is ringed at ``x``.
    """

    x: str
    text: str
    series: int = 0


class ChartPanel(_Model):
    """One panel of a ``panels`` chart."""

    title: str
    series: list[ChartSeries] = Field(min_length=1)
    notes: list[ChartNote] = Field(default_factory=list)


class ChartPoint(_Model):
    """One labelled point of a ``scatter`` chart."""

    label: str
    x: float
    y: float


class ChartSpec(_Model):
    """A chart to render.

    Attributes:
        id: File-name-safe identifier, unique within a run.
        kind: Chart type.
        title: Chart title, already localised.
        subtitle: One line under the title saying what the measure is and how to read it.
        y_label: Value axis label, already localised, with its unit.
        x_label: Horizontal axis label for ``scatter`` and ``dumbbell`` charts.
        series: Data to plot; ``bars`` and ``trend`` use exactly one series, ``dumbbell``
            two (before, after) over the same categories.
        panels: The panels of a ``panels`` chart.
        points: The points of a ``scatter`` chart.
        trend_y: Fitted trend values aligned with ``series[0].x`` (``trend`` charts only).
        highlight_x: Labels of periods to shade as spikes (``trend`` charts only).
        size: Width class; the renderer maps it to physical dimensions.
        log_y: Logarithmic value axis, for series that differ by orders of magnitude.
        log_x: Logarithmic horizontal axis (``scatter``).
        reference_y: Value of a horizontal reference line (100 for an index, 0 for change).
        value_suffix: Appended to value labels (``%``).
    """

    id: str = Field(pattern=r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$")
    kind: ChartKind
    title: str
    subtitle: str | None = None
    y_label: str
    x_label: str | None = None
    series: list[ChartSeries] = Field(default_factory=list)
    panels: list[ChartPanel] = Field(default_factory=list)
    points: list[ChartPoint] = Field(default_factory=list)
    trend_y: list[float | None] | None = None
    highlight_x: list[str] = Field(default_factory=list)
    size: ChartSize = "wide"
    log_y: bool = False
    log_x: bool = False
    reference_y: float | None = None
    value_suffix: str = ""

    @model_validator(mode="after")
    def _has_data(self) -> Self:
        """Each kind carries its data where the renderer looks for it."""
        if self.kind == "panels":
            ok = bool(self.panels)
        elif self.kind == "scatter":
            ok = bool(self.points)
        elif self.kind == "dumbbell":
            ok = len(self.series) == 2  # noqa: PLR2004 -- before and after
        else:
            ok = bool(self.series)
        if not ok:
            msg = f"A {self.kind!r} chart has no data where its kind needs it"
            raise ValueError(msg)
        return self
