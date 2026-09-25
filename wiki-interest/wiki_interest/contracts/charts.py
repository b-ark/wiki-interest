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
    "ChartPoint",
    "ChartSeries",
    "ChartSize",
    "ChartSpec",
    "SeriesStyle",
    "ShareChange",
    "ShareLine",
    "ShareMark",
    "ShareSegment",
    "ShareYears",
]

ChartKind = Literal["lines", "bars", "grouped_bars", "trend", "scatter", "share_years"]
"""``lines``: several series over time; ``bars``: one value per category; ``grouped_bars``:
several series side by side per category; ``trend``: one series with its fitted trend line
and highlighted periods; ``scatter``: labelled points on two numeric axes; ``share_years``:
the attention share month by month with the average of each calendar year (:class:`ShareYears`)."""

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


class ChartPoint(_Model):
    """One labelled point of a ``scatter`` chart."""

    label: str
    x: float
    y: float


class ShareSegment(_Model):
    """One calendar year of a :class:`ShareLine`: its months and their average.

    ``start`` and ``end`` are months (``2026-01``); a ``partial`` year (the last of the data)
    is averaged over the months it has.
    """

    year: int
    start: str
    end: str
    value: float
    partial: bool = False


class ShareLine(_Model):
    """One audience of a ``share_years`` chart: its months and its calendar years.

    ``label`` names the line at its end (``uk``); ``x`` holds months (``2021-01``) and ``y``
    their values, gaps as ``None``.
    """

    label: str
    x: list[str]
    y: list[float | None]
    years: list[ShareSegment] = Field(min_length=1)


class ShareMark(_Model):
    """A month an observation singles out on a line: a lasting step or a one-off burst.

    The chart shows it only when the report text cites ``observation``: a mark the text does
    not explain would leave the reader guessing.
    """

    kind: Literal["step", "spike"]
    line: int
    x: str
    y: float | None = None
    observation: str


class ShareChange(_Model):
    """The last 12 months of one audience: the article's views and its edition's, in %."""

    label: str
    article: float
    edition: float


class ShareYears(_Model):
    """What a ``share_years`` chart draws, without any text: the text is the report's language.

    Attributes:
        absolute: Views a month instead of the attention share (the user asked for raw views).
        lines: One per audience, in the order of the request.
        marks: Steps and bursts the observations found.
        changes: The last 12 months of each audience, for the line under the chart.
        changes_start: First month of those 12 (``2025-09``).
        changes_end: Their last month.
        recent_months: How many last months the chart shades.
    """

    absolute: bool = False
    lines: list[ShareLine] = Field(min_length=1)
    marks: list[ShareMark] = Field(default_factory=list)
    changes: list[ShareChange] = Field(default_factory=list)
    changes_start: str | None = None
    changes_end: str | None = None
    recent_months: int = 3


class ChartSpec(_Model):
    """A chart to render.

    Attributes:
        id: File-name-safe identifier, unique within a run.
        kind: Chart type.
        title: Chart title, already localised.
        subtitle: One line under the title saying what the measure is and how to read it.
        y_label: Value axis label, already localised, with its unit.
        x_label: Horizontal axis label for ``scatter`` charts.
        series: Data to plot; ``bars`` and ``trend`` use exactly one series.
        points: The points of a ``scatter`` chart.
        share: The data of a ``share_years`` chart.
        year_labels: Axis labels of a ``share_years`` chart, one per year of its lines
            (``2026 (Jan – Aug)`` for a partial one), in the order of the years.
        mark_labels: Labels of the marks it shows (``level changed, Aug 2023``), aligned
            with ``share.marks``; a mark without a label is not shown.
        legend: Legend entries of a ``share_years`` chart: the yearly average, each month,
            the shaded last months.
        note: Lines under a ``share_years`` chart (the last 12 months of each audience).
        trend_y: Fitted trend values aligned with ``series[0].x`` (``trend`` charts only).
        highlight_x: Labels of periods to shade as spikes (``trend`` charts only).
        size: Width class; the renderer maps it to physical dimensions.
        height_mm: Figure height in millimetres instead of the one ``size`` gives: the PDF
            redraws a chart lower rather than shrink it, so it keeps the full page width.
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
    points: list[ChartPoint] = Field(default_factory=list)
    share: ShareYears | None = None
    year_labels: list[str] = Field(default_factory=list)
    mark_labels: list[str | None] = Field(default_factory=list)
    legend: list[str] = Field(default_factory=list)
    note: str | None = None
    trend_y: list[float | None] | None = None
    highlight_x: list[str] = Field(default_factory=list)
    size: ChartSize = "wide"
    height_mm: float | None = Field(default=None, gt=0)
    log_y: bool = False
    log_x: bool = False
    reference_y: float | None = None
    value_suffix: str = ""

    @model_validator(mode="after")
    def _has_data(self) -> Self:
        """Each kind carries its data where the renderer looks for it."""
        if self.kind == "scatter":
            ok = bool(self.points)
        elif self.kind == "share_years":
            ok = self.share is not None
        else:
            ok = bool(self.series)
        if not ok:
            msg = f"A {self.kind!r} chart has no data where its kind needs it"
            raise ValueError(msg)
        return self
