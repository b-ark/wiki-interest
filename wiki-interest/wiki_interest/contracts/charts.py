"""Declarative chart specifications.

The application decides *what* to plot and expresses it here; a
:class:`~wiki_interest.ports.renderers.ChartRenderer` decides *how*. Keeping the spec as data
makes chart content testable without matplotlib and lets the report cite exactly what was drawn.
"""

from __future__ import annotations

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wiki_interest.domain.observations import ShareMove

__all__ = [
    "AudienceLine",
    "AudienceYear",
    "AudienceYears",
    "ChartKind",
    "ChartPoint",
    "ChartSeries",
    "ChartSize",
    "ChartSpec",
    "SeriesStyle",
    "ShareLine",
    "ShareMark",
    "ShareSegment",
    "ShareYears",
]

ChartKind = Literal[
    "lines", "bars", "grouped_bars", "trend", "scatter", "share_years", "audience_years"
]
"""``lines``: several series over time; ``bars``: one value per category; ``grouped_bars``:
several series side by side per category; ``trend``: one series with its fitted trend line
and highlighted periods; ``scatter``: labelled points on two numeric axes; ``share_years``:
the attention share month by month with the average of each calendar year (:class:`ShareYears`);
``audience_years``: each calendar year's views, the audiences side by side
(:class:`AudienceYears`)."""

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


class ShareYears(_Model):
    """What a ``share_years`` chart draws, without any text: the text is the report's language.

    Attributes:
        absolute: Views a month instead of the attention share (the user asked for raw views).
        lines: One per audience, in the order of the request.
        marks: Steps and bursts the observations found.
        recent_months: How many last months the chart shades; 0 shades none.
    """

    absolute: bool = False
    lines: list[ShareLine] = Field(min_length=1)
    marks: list[ShareMark] = Field(default_factory=list)
    recent_months: int = Field(default=3, ge=0)


class AudienceYear(_Model):
    """One calendar year of an audience: its mean monthly views and the change a year on.

    Attributes:
        year: The calendar year.
        start: Its first month (``2026-01``).
        end: Its last month (``2026-08`` for a partial year).
        views: Mean monthly views, rounded as the text rounds them.
        change: The views against the same months a year earlier, in whole %; ``None``
            without a year of data before.
        move: Whether the article's share of its Wikipedia's views gained, held or lost
            over the same comparison.
        partial: Fewer than 12 months (the last year of the data).
    """

    year: int
    start: str
    end: str
    views: float
    change: float | None = None
    move: ShareMove | None = None
    partial: bool = False


class AudienceLine(_Model):
    """One audience of an ``audience_years`` chart, named as on the main chart (``uk``)."""

    label: str
    years: list[AudienceYear] = Field(min_length=1)


class AudienceYears(_Model):
    """What an ``audience_years`` chart draws, without any text.

    The audiences of the main chart, in its order: their size in views a month on one scale,
    how the views changed a year on, and whether that beat the whole Wikipedia.
    """

    lines: list[AudienceLine] = Field(min_length=1)


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
        audience: The data of an ``audience_years`` chart.
        year_labels: Axis labels of a ``share_years`` or ``audience_years`` chart, one per
            year of its lines (``2026 (Jan – Aug)`` for a partial one), in the order of the
            years.
        mark_labels: Labels of the marks it shows (``level changed, Aug 2023``), aligned
            with ``share.marks``; a mark without a label is not shown.
        move_labels: What an ``audience_years`` chart writes under a year for each
            :data:`~wiki_interest.domain.observations.ShareMove` (``▲ gained share``).
        legend: Legend entries of a ``share_years`` chart: the yearly average, each month,
            the shaded last months.
        note: A quiet line under the header of an ``audience_years`` chart: what its partial
            year is compared with.
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
    audience: AudienceYears | None = None
    year_labels: list[str] = Field(default_factory=list)
    mark_labels: list[str | None] = Field(default_factory=list)
    move_labels: dict[ShareMove, str] = Field(default_factory=dict)
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
        elif self.kind == "audience_years":
            ok = self.audience is not None
        else:
            ok = bool(self.series)
        if not ok:
            msg = f"A {self.kind!r} chart has no data where its kind needs it"
            raise ValueError(msg)
        return self
