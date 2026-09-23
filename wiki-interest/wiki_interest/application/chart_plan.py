"""Which charts a report shows, as declarative :class:`ChartSpec` objects.

Every chart answers one question a reader has about the numbers.

The main chart answers "is the topic gaining or losing ground in its Wikipedia": one panel
per edition, the article's views and the whole edition's traffic as indexes on one scale
(the mean of the first year is 100). When the article's line falls below the edition's, the
topic loses its share of attention; months that stand out are labelled where they happen.

The second chart depends on how many audiences are compared:

* one topic in one or two editions: the share's change against the same months a year
  earlier, month by month, which shows whether a decline is slowing or a rise is fading;
* up to four audiences: the share before and after, one "dumbbell" per audience;
* five or more: size of the share against its change, one point per audience.

A seasonal chart follows when the pattern deserves one. The planner only decides content;
the renderer draws. Methods return ``None`` when the data cannot support the chart.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from statistics import fmean

from wiki_interest.application.analysis import MonthFinding, PairAnalysis
from wiki_interest.application.assessment import headline_growth
from wiki_interest.contracts.charts import (
    ChartNote,
    ChartPanel,
    ChartPoint,
    ChartSeries,
    ChartSpec,
)
from wiki_interest.domain.findings import SeasonalProfile
from wiki_interest.domain.models import Series, WikiProject
from wiki_interest.i18n import Translator

__all__ = ["ChartPlanner"]

_INDEX_BASE_MONTHS = 12
"""The index starts at the mean of the first year (100), which is steadier than one month."""
_SMOOTH_MONTHS = 3
_YEAR = 12
_MAX_PANELS = 6
_MAX_NOTES = 3
_MAX_LINES = 6
_MONTHS = 12
_PERCENT = 100.0
_FEW_FOR_LINES = 2
_FEW_FOR_DUMBBELLS = 4
_EDITION_SERIES = 2
"""Position of the edition's line among a panel's series (points, article, edition)."""


class ChartPlanner:
    """Builds chart specifications in the report language.

    Args:
        translator: Titles and axis labels.
        pair_label: Display label of a (topic, edition) pair, substitutes included.
        footnote: Source and period line for a full-width chart.
        short_label: Compact label for category axes (``uk`` for ``uk.wikipedia``); the
            full label is used when not given.
        show_season: Whether an edition's seasonal pattern deserves a chart; the rule lives
            with the findings (:func:`~wiki_interest.application.insights.season_visibility`)
            so a chart never shows a pattern the text calls too weak. All are shown when
            not given.
    """

    def __init__(
        self,
        translator: Translator,
        pair_label: Callable[[str, WikiProject], str],
        footnote: str,
        short_label: Callable[[str, WikiProject], str] | None = None,
        *,
        show_season: Callable[[PairAnalysis], bool] | None = None,
    ) -> None:
        self._t = translator
        self._label = pair_label
        self._short = short_label or pair_label
        self._footnote = footnote
        self._show_season = show_season

    def _seasonal(self, pair: PairAnalysis) -> bool:
        if _profile(pair) is None:
            return False
        return self._show_season is None or self._show_season(pair)

    def widen(self, spec: ChartSpec) -> ChartSpec:
        """The same chart at full width, with the source and period under it."""
        return spec.model_copy(update={"size": "wide", "footnote": self._footnote})

    def _pair(self, pair: PairAnalysis) -> str:
        return self._label(pair.topic_id, pair.project)

    def _id(self, prefix: str, pair: PairAnalysis) -> str:
        return f"{prefix}-{pair.topic_id}-{pair.project.language}".lower()

    def plan(
        self, pairs: Sequence[PairAnalysis], *, normalised: bool, single_topic: bool
    ) -> list[ChartSpec]:
        """The main chart, the second chart for this many audiences, and the seasons."""
        measured = [p for p in pairs if p.views is not None]
        if not measured:
            return []
        if single_topic and len(measured) <= _FEW_FOR_LINES:
            second = self.change_over_time(measured, normalised=normalised)
        elif len(measured) <= _FEW_FOR_DUMBBELLS:
            second = self.before_after(measured, normalised=normalised)
        else:
            second = self.size_and_change(measured, normalised=normalised)
        season = (
            self.season_bars(measured[0]) if len(measured) == 1 else self.season_lines(measured)
        )
        return [c for c in (self.main(measured), second, season) if c is not None]

    # -- the main chart ---------------------------------------------------------------------

    def main(self, pairs: Sequence[PairAnalysis]) -> ChartSpec | None:
        """Article views against edition traffic, one panel per edition, as indexes."""
        panels = [panel for p in pairs[:_MAX_PANELS] if (panel := self._panel(p)) is not None]
        if not panels:
            return None
        return ChartSpec(
            id="main",
            kind="panels",
            size="wide",
            title=self._t.t("chart.index_title"),
            subtitle=self._t.t("chart.index_subtitle"),
            y_label=self._t.t("chart.axis_index"),
            panels=panels,
            reference_y=_PERCENT,
            footnote=self._footnote,
        )

    def _panel(self, pair: PairAnalysis) -> ChartPanel | None:
        views = pair.views
        if views is None:
            return None
        article = _index(views)
        edition = _index(pair.edition_total)
        if article is None or edition is None:
            return None
        months = _months(views)
        return ChartPanel(
            title=self._pair(pair),
            series=[
                ChartSeries(
                    label=self._t.t("chart.series_article_months"),
                    x=months,
                    y=article,
                    style="points",
                    color=0,
                ),
                ChartSeries(
                    label=self._t.t("chart.series_article_smooth"),
                    x=months,
                    y=_rolling(article),
                    color=0,
                ),
                ChartSeries(
                    label=self._t.t("chart.series_edition_short"),
                    x=months,
                    y=_rolling(edition),
                    style="dashed",
                    color=1,
                ),
            ],
            notes=[self._note(m) for m in pair.findings.months[:_MAX_NOTES]],
        )

    def _note(self, month: MonthFinding) -> ChartNote:
        """``2024-05 ×1.9 possibly bots``: the largest multiple among the series."""
        multiple = max((m for _, m in month.multiples), key=lambda m: abs(m - 1))
        text = self._t.t(
            f"chart.note.{month.nature}",
            month=_month_label(month.month),
            multiple=self._t.number(multiple, 1),
        )
        # A month in which only the edition moved is ringed on the edition's line.
        on = _EDITION_SERIES if month.nature == "edition" else 0
        return ChartNote(x=_month_label(month.month), text=text, series=on)

    # -- the second chart -------------------------------------------------------------------

    def change_over_time(
        self, pairs: Sequence[PairAnalysis], *, normalised: bool
    ) -> ChartSpec | None:
        """Each month's last three months against the same three months a year earlier."""
        series: list[ChartSeries] = []
        for pair in pairs:
            source = pair.per_million if normalised else pair.views
            if source is None:
                continue
            x, y = _rolling_yoy(source)
            if any(v is not None for v in y):
                series.append(ChartSeries(label=self._pair(pair), x=x, y=y))
        if not series:
            return None
        return ChartSpec(
            id="change",
            kind="lines",
            size="wide",
            title=self._t.t("chart.yoy_title", metric=self._metric(normalised)),
            subtitle=self._t.t("chart.yoy_subtitle"),
            y_label=self._t.t("chart.axis_growth"),
            series=series,
            reference_y=0.0,
            value_suffix="%",
        )

    def before_after(self, pairs: Sequence[PairAnalysis], *, normalised: bool) -> ChartSpec | None:
        """Mean share of the year before and of the last year, per audience."""
        rows: list[tuple[str, float, float]] = []
        bases: set[str] = set()
        for pair in pairs:
            source = pair.per_million if normalised else pair.views
            if source is None:
                continue
            compared = _before_after(source)
            if compared is None:
                continue
            before, after, basis = compared
            rows.append((self._short(pair.topic_id, pair.project), before, after))
            bases.add(basis)
        if not rows:
            return None
        basis = bases.pop() if len(bases) == 1 else "mixed"
        labels = [label for label, _, _ in rows]
        unit = "chart.axis_per_million" if normalised else "chart.axis_views"
        return ChartSpec(
            id="before-after",
            kind="dumbbell",
            size="wide",
            title=self._t.t("chart.dumbbell_title", metric=self._metric(normalised)),
            subtitle=self._t.t(f"chart.dumbbell_basis.{basis}"),
            y_label="",
            x_label=self._t.t(unit),
            series=[
                ChartSeries(
                    label=self._t.t(f"chart.series_before.{basis}"),
                    x=labels,
                    y=[round(b, 2) for _, b, _ in rows],
                    style="points",
                    color=1,
                ),
                ChartSeries(
                    label=self._t.t(f"chart.series_after.{basis}"),
                    x=labels,
                    y=[round(a, 2) for _, _, a in rows],
                    color=0,
                ),
            ],
        )

    def size_and_change(
        self, pairs: Sequence[PairAnalysis], *, normalised: bool
    ) -> ChartSpec | None:
        """Size of the share (log axis) against its change, one point per audience."""
        points: list[ChartPoint] = []
        for pair in pairs:
            metrics = pair.metrics
            if metrics is None or not pair.measures_topic:
                continue
            size = metrics.per_million_avg if normalised else metrics.views_avg
            change, _ = headline_growth(metrics)
            if size is None or size <= 0 or change is None:
                continue
            label = self._short(pair.topic_id, pair.project)
            points.append(ChartPoint(label=label, x=size, y=round(change * _PERCENT, 1)))
        if not points:
            return None
        unit = "chart.axis_per_million" if normalised else "chart.axis_views"
        return ChartSpec(
            id="size-change",
            kind="scatter",
            size="wide",
            title=self._t.t("chart.scatter_title", metric=self._metric(normalised)),
            subtitle=self._t.t("chart.scatter_subtitle"),
            y_label=self._t.t("chart.axis_growth"),
            x_label=self._t.t("chart.axis_log", unit=self._t.t(unit)),
            points=points,
            log_x=True,
            reference_y=0.0,
            value_suffix="%",
        )

    def _metric(self, normalised: bool) -> str:
        return self._t.t("metric.attention_share" if normalised else "metric.article_views")

    # -- seasons ----------------------------------------------------------------------------

    def season_bars(self, pair: PairAnalysis) -> ChartSpec | None:
        """Each calendar month against the usual level, in percent."""
        profile = _profile(pair)
        if profile is None or not self._seasonal(pair):
            return None
        return ChartSpec(
            id=self._id("season", pair),
            kind="bars",
            size="half",
            title=self._t.t("chart.season_title"),
            subtitle=self._season_period(pair),
            y_label=self._t.t("chart.axis_season"),
            series=[
                ChartSeries(
                    label=self._t.t("chart.season_title"),
                    x=[self._t.t(f"month.short.{m}") for m in range(1, _MONTHS + 1)],
                    y=[None if e is None else round(e * _PERCENT, 1) for e in profile.effects],
                )
            ],
            reference_y=0.0,
            value_suffix="%",
        )

    def season_lines(self, pairs: Sequence[PairAnalysis]) -> ChartSpec | None:
        """Seasonal profiles of the editions that have one, on one chart."""
        profiled = [(p, _profile(p)) for p in pairs[:_MAX_LINES] if self._seasonal(p)]
        if not profiled:
            return None
        months = [self._t.t(f"month.short.{m}") for m in range(1, _MONTHS + 1)]
        return ChartSpec(
            id="season",
            kind="lines",
            size="half",
            title=self._t.t("chart.season_title"),
            subtitle=self._season_period(profiled[0][0]),
            y_label=self._t.t("chart.axis_season"),
            series=[
                ChartSeries(
                    label=self._pair(p),
                    x=months,
                    y=[None if e is None else round(e * _PERCENT, 1) for e in profile.effects],
                )
                for p, profile in profiled
                if profile is not None
            ],
            reference_y=0.0,
        )

    def _season_period(self, pair: PairAnalysis) -> str | None:
        season = pair.findings.season
        if season is None or season.start is None or season.end is None:
            return None
        return self._t.t(
            "chart.season_period",
            start=_month_label(season.start),
            end=_month_label(season.end),
        )


def _months(series: Series) -> list[str]:
    return [_month_label(p.period) for p in series.points]


def _month_label(day: date) -> str:
    return day.strftime("%Y-%m")


def _index(series: Series) -> list[float | None] | None:
    """The series as an index: the mean of its first year (or first half) is 100."""
    values = series.values
    span = min(_INDEX_BASE_MONTHS, max(1, len(values) // 2))
    base_values = [v for v in values[:span] if v is not None]
    if not base_values or fmean(base_values) <= 0:
        return None
    base = fmean(base_values)
    return [None if v is None else round(v / base * _PERCENT, 1) for v in values]


def _rolling(values: Sequence[float | None]) -> list[float | None]:
    """Trailing mean of three months; ``None`` until three observed months are available."""
    out: list[float | None] = []
    for i in range(len(values)):
        window = [v for v in values[max(0, i - _SMOOTH_MONTHS + 1) : i + 1] if v is not None]
        out.append(round(fmean(window), 1) if len(window) == _SMOOTH_MONTHS else None)
    return out


def _rolling_yoy(series: Series) -> tuple[list[str], list[float | None]]:
    """Each month's last three months over the same three a year earlier, in percent.

    Summing three months steadies the line; comparing with the same months cancels seasons.
    """
    values = series.values
    x: list[str] = []
    y: list[float | None] = []
    for i in range(_YEAR + _SMOOTH_MONTHS - 1, len(values)):
        now = values[i - _SMOOTH_MONTHS + 1 : i + 1]
        then = values[i - _YEAR - _SMOOTH_MONTHS + 1 : i - _YEAR + 1]
        x.append(_month_label(series.points[i].period))
        if any(v is None for v in (*now, *then)):
            y.append(None)
            continue
        base = sum(v for v in then if v is not None)
        current = sum(v for v in now if v is not None)
        y.append(round((current / base - 1) * _PERCENT, 1) if base > 0 else None)
    return x, y


def _before_after(series: Series) -> tuple[float, float, str] | None:
    """Mean of the 12 months before the last 12 and of the last 12; halves when shorter."""
    values = series.values
    if len(values) >= 2 * _YEAR:
        before, after, basis = values[-2 * _YEAR : -_YEAR], values[-_YEAR:], "yoy"
    else:
        half = len(values) // 2
        before, after, basis = values[:half], values[len(values) - half :], "halves"
    seen_before = [v for v in before if v is not None]
    seen_after = [v for v in after if v is not None]
    if not seen_before or not seen_after:
        return None
    return fmean(seen_before), fmean(seen_after), basis


def _profile(pair: PairAnalysis) -> SeasonalProfile | None:
    """The seasonal profile of the pair's whole history, if one could be computed."""
    season = pair.findings.season
    return season.profile if season is not None else None
