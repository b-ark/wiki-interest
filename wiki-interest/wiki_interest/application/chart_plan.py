"""Which charts a report shows, as declarative :class:`ChartSpec` objects.

Every chart answers one question a reader has about the numbers.

The main chart answers "how big is the interest, and where is it going": the attention share
(views per million views of the whole edition) month by month, with the average of each
calendar year on top, one line per audience on one scale. The share already sets the topic
against its Wikipedia: when the article falls faster than the edition, the line falls. It
reads the same calendar years as the observations, so the report text's numbers are the
chart's; its data are kept without text (:func:`share_years_data`) and its spec is built when
the report is rendered (:func:`share_years_spec`), in the report's language, with the steps
and bursts the text cites.

Under it, the chart of views by year answers "how many readers are there, and how did they
move": each calendar year's mean monthly views, the audiences side by side on one scale, the
change against a year earlier over each pair of bars and, under the years, whether the
article gained, held or lost its share of its Wikipedia's views. A share can fall while the
views grow, when the whole Wikipedia grows faster; the two charts together show both. Its
data too are kept without text (:func:`audience_years_data`) and its spec built when the
report is rendered (:func:`audience_years_spec`).

With many audiences a further chart sets the size of each share against its change, one
point per audience. A seasonal chart follows when the pattern deserves one. The planner only
decides content; the renderer draws. Methods return ``None`` when the data cannot support the
chart.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from statistics import mean
from typing import Literal

from wiki_interest.application.analysis import PairAnalysis
from wiki_interest.application.assessment import headline_growth
from wiki_interest.contracts.charts import (
    AudienceLine,
    AudienceYear,
    AudienceYears,
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ShareLine,
    ShareMark,
    ShareSegment,
    ShareTrend,
    ShareYears,
)
from wiki_interest.contracts.request import Period
from wiki_interest.domain.models import WikiProject
from wiki_interest.domain.observations import (
    Observation,
    PairHistory,
    SeasonProfile,
    YearLevel,
    round_count,
    round_share,
    year_levels,
)
from wiki_interest.domain.trust import BreakpointVerdict, TrendVerdict, Trust, WindowTrend
from wiki_interest.i18n import Translator

__all__ = [
    "AUDIENCE_CHART_ID",
    "SHARE_CHART_ID",
    "ChartPlanner",
    "audience_years_data",
    "audience_years_spec",
    "line_label",
    "round_significant",
    "share_years_data",
    "share_years_spec",
]

SHARE_CHART_ID = "share"
AUDIENCE_CHART_ID = "audience"
_RECENT = 3
_RECENT_OBSERVATION = "recent:"
_MAX_SHARE_LINES = 3
"""More lines on one scale merge; with more audiences the scatter compares them all."""
_MAX_LINES = 6
_MONTHS = 12
_PERCENT = 100.0
_FEW_FOR_ONE_CHART = 3
"""Up to this many audiences the main chart shows them all; more add the scatter."""
_MARKED = ("step", "spike")


@dataclass(frozen=True, slots=True)
class _Drawn:
    """An audience the charts draw: its series, its context years, its verdict, its name."""

    history: PairHistory
    years: list[YearLevel]
    trend: WindowTrend | None
    label: str


def _drawn(
    histories: Sequence[PairHistory],
    *,
    trends: Mapping[str, WindowTrend],
    absolute: bool,
    topic_labels: Mapping[str, str],
) -> list[_Drawn]:
    """The audiences both charts draw, in the order of the request.

    With more than the lines one scale holds, the largest by their window (views or the
    trend line's last level); the two charts always show the same audiences under the same
    names.
    """
    topics = {h.topic_id for h in histories}
    languages = {h.language for h in histories}
    drawn = [
        _Drawn(
            history,
            year_levels(history),
            trends.get(history.pair),
            line_label(history, topics, languages, topic_labels),
        )
        for history in histories
        if any(v is not None for v in history.views)
    ]
    if len(drawn) > _MAX_SHARE_LINES:

        def size(d: _Drawn) -> float:
            t = d.trend
            if t is None:
                return 0.0
            if absolute:
                return t.views_avg or 0.0
            return t.level_end or 0.0

        largest = sorted(drawn, key=size, reverse=True)[:_MAX_SHARE_LINES]
        kept = {d.history.pair for d in largest}
        drawn = [d for d in drawn if d.history.pair in kept]
    return drawn


def share_years_data(  # noqa: PLR0913 -- the series, what was found, and the two ranges
    histories: Sequence[PairHistory],
    observations: Sequence[Observation],
    *,
    window: Period,
    context: Period,
    trends: Mapping[str, WindowTrend],
    absolute: bool,
    topic_labels: Mapping[str, str],
    trust: Mapping[str, Trust] | None = None,
) -> ShareYears | None:
    """What the main chart draws: the history as context, the analysis window and its trend.

    Args:
        histories: The pairs' long series.
        observations: What the detectors found: the steps and bursts to mark.
        window: The analysis window, shaded.
        context: The months the chart shows.
        trends: The window's verdict of each pair: its trend line is drawn in the window.
        absolute: Views a month instead of the attention share (no trend line then: the
            verdict reads the share).
        topic_labels: Topic id -> label, to name lines when there are several topics.
        trust: The trust in each verdict: a step it finds technical is drawn as such.
    """
    drawn: list[tuple[PairHistory, ShareLine]] = []
    for d in _drawn(histories, trends=trends, absolute=absolute, topic_labels=topic_labels):
        history = d.history
        kept = [k for k, m in enumerate(history.months) if context.start <= m <= context.end]
        if not kept:
            continue
        segments = [
            ShareSegment(
                year=y.year,
                start=_month_label(y.first),
                end=_month_label(y.last),
                value=round_count(y.views) if absolute else round_share(y.share),
            )
            for y in d.years
            if not y.partial and y.first >= context.start and y.last < window.start
        ]
        trend = d.trend
        drawn_trend = None
        if (
            not absolute
            and trend is not None
            and trend.level_start is not None
            and trend.level_end is not None
        ):
            drawn_trend = ShareTrend(
                start=_month_label(trend.segment_start),
                end=_month_label(trend.window_end),
                value_start=round_share(trend.level_start),
                value_end=round_share(trend.level_end),
                verdict=trend.verdict.value,
            )
        line = ShareLine(
            label=d.label,
            x=[_month_label(history.months[k]) for k in kept],
            y=[_value(history, k, absolute=absolute) for k in kept],
            years=segments,
            trend=drawn_trend,
        )
        drawn.append((history, line))
    if not drawn:
        return None
    return ShareYears(
        absolute=absolute,
        lines=[line for _, line in drawn],
        marks=_marks(drawn, observations, trust or {}),
        recent_months=0,
        window_start=_month_label(window.start) if window.start > context.start else None,
        window_end=_month_label(window.end),
    )


def audience_years_data(
    histories: Sequence[PairHistory],
    *,
    trends: Mapping[str, WindowTrend],
    topic_labels: Mapping[str, str],
) -> AudienceYears | None:
    """What the chart of views draws: the twelve months before the last twelve, and the last.

    The views are shown to three significant digits and the change is computed from the
    shown values, so "10,500 → 6,720" never stands next to a percentage the reader cannot
    get from them. Under the last span, the window's verdict on the share.
    """
    lines: list[AudienceLine] = []
    for d in _drawn(histories, trends=trends, absolute=False, topic_labels=topic_labels):
        history = d.history
        n = len(history.months)
        spans = [(n - 2 * _MONTHS, n - _MONTHS), (n - _MONTHS, n)]
        years: list[AudienceYear] = []
        previous: float | None = None
        for index, (first, stop) in enumerate(spans):
            values = [v for v in history.views[max(first, 0) : stop] if v is not None]
            if first < 0 or len(values) < _MONTHS:
                continue
            shown = round_significant(mean(values))
            change = None
            if previous:
                change = round((shown / previous - 1) * _PERCENT)
            last = index == len(spans) - 1
            years.append(
                AudienceYear(
                    year=index,
                    start=_month_label(history.months[first]),
                    end=_month_label(history.months[stop - 1]),
                    views=shown,
                    change=change,
                    move=_MOVES.get(d.trend.verdict) if last and d.trend else None,
                )
            )
            previous = shown
        if years:
            lines.append(AudienceLine(label=d.label, years=years))
    return AudienceYears(lines=lines) if lines else None


_MOVES: Mapping[TrendVerdict, Literal["gained", "held", "lost"]] = {
    TrendVerdict.GROWING: "gained",
    TrendVerdict.STABLE: "held",
    TrendVerdict.DECLINING: "lost",
}
"""The window's verdict as the symbol row under the views reads it (▲ ≈ ▼)."""


_MARK_VERDICTS: Mapping[BreakpointVerdict, Literal["real", "artifact", "unknown"]] = {
    BreakpointVerdict.REAL: "real",
    BreakpointVerdict.ARTIFACT: "artifact",
    BreakpointVerdict.UNKNOWN: "unknown",
}


def round_significant(value: float, digits: int = 3) -> float:
    """``value`` to ``digits`` significant digits: 10,473 → 10,500; 6,718 → 6,720; 552 → 552."""
    if value <= 0:
        return 0.0
    places = digits - 1 - math.floor(math.log10(value))
    return float(round(value, places))


def audience_years_spec(data: AudienceYears, t: Translator) -> ChartSpec:
    """The chart of views in the report's language: one label per span."""
    spans: dict[int, tuple[str, str]] = {}
    for line in data.lines:
        for y in line.years:
            spans.setdefault(y.year, (y.start, y.end))
    labels = [
        t.t("chart.audience.span", first=_month_name(start, t), last=_month_name(end, t))
        for _, (start, end) in sorted(spans.items())
    ]
    return ChartSpec(
        id=AUDIENCE_CHART_ID,
        kind="audience_years",
        size="wide",
        title=t.t("chart.audience.title"),
        subtitle=t.t("chart.audience.subtitle"),
        y_label=t.t("chart.absolute.axis"),
        audience=data,
        year_labels=labels,
    )


def _calendar_labels(data: ShareYears, t: Translator) -> list[str]:
    """One label per calendar year the chart's months cover: ``2025``, ``2026 (Jan – Aug)``."""
    by_year: dict[int, list[str]] = {}
    for line in data.lines:
        for month in line.x:
            by_year.setdefault(int(month[:4]), []).append(month)
    labels = []
    for year, months in sorted(by_year.items()):
        first, last = min(months), max(months)
        if len(set(months)) < _MONTHS:
            labels.append(
                t.t(
                    "chart.share.partial_year",
                    year=year,
                    first=_short_month(first, t),
                    last=_short_month(last, t),
                )
            )
        else:
            labels.append(str(year))
    return labels


def share_years_spec(data: ShareYears, t: Translator, cited: Collection[str]) -> ChartSpec:
    """The main chart in the report's language.

    Steps are marked always (their verdict decides how: a probable technical change is grey
    and dashed); a one-off burst only when the report text cites it.

    Args:
        data: What the chart draws (:func:`share_years_data`).
        t: The report-language translator, the agent's labels included.
        cited: Ids of the observations the report text cites.
    """
    labels = [
        t.t("chart.share.artifact", month=_month_name(mark.x, t))
        if mark.verdict == "artifact"
        else _month_name(mark.x, t)
        for mark in data.marks
    ]
    mark_labels = [
        label if mark.kind == "step" or mark.observation in cited else None
        for mark, label in zip(data.marks, labels, strict=True)
    ]
    legend = [t.t("chart.share.legend_month")]
    if any(line.years for line in data.lines):
        legend.insert(0, t.t("chart.share.legend_year"))
    if any(line.trend for line in data.lines):
        legend.append(t.t("chart.share.legend_trend"))
    if data.window_start is not None:
        legend.append(t.t("chart.share.legend_window"))
    kind = "absolute" if data.absolute else "share"
    return ChartSpec(
        id=SHARE_CHART_ID,
        kind="share_years",
        size="wide",
        title=t.t(f"chart.{kind}.title"),
        subtitle=t.t(f"chart.{kind}.subtitle"),
        y_label=t.t(f"chart.{kind}.axis"),
        share=data,
        year_labels=_calendar_labels(data, t),
        mark_labels=mark_labels,
        legend=legend,
    )


def _value(history: PairHistory, k: int, *, absolute: bool) -> float | None:
    views, edition = history.views[k], history.edition[k]
    if absolute:
        return views
    return None if views is None or not edition else round(views / edition * 1e6, 3)


def line_label(
    history: PairHistory,
    topics: Collection[str],
    languages: Collection[str],
    topic_labels: Mapping[str, str],
) -> str:
    """``uk`` for one topic; the topic for one edition; both otherwise.

    An edition measured through another article names it: ``pl (Post)``, so its line is not
    read as the topic's.
    """
    topic = topic_labels.get(history.topic_id, history.topic_id)
    if len(topics) == 1:
        label = history.language
    elif len(languages) == 1:
        label = topic
    else:
        label = f"{topic} · {history.language}"
    return f"{label} ({history.substitute})" if history.substitute else label


def _marks(
    drawn: Sequence[tuple[PairHistory, ShareLine]],
    observations: Sequence[Observation],
    trust: Mapping[str, Trust],
) -> list[ShareMark]:
    out: list[ShareMark] = []
    for index, (history, line) in enumerate(drawn):
        for o in observations:
            if o.kind not in _MARKED or o.pair != history.pair or o.month is None:
                continue
            month = _month_label(o.month)
            if month not in line.x:
                continue
            kind: Literal["step", "spike"] = "step" if o.kind == "step" else "spike"
            value = line.y[line.x.index(month)]
            checked = trust.get(history.pair)
            verdict = (
                next(
                    (_MARK_VERDICTS[b.verdict] for b in checked.breakpoints if b.month == o.month),
                    None,
                )
                if checked and kind == "step"
                else None
            )
            out.append(
                ShareMark(
                    kind=kind, line=index, x=month, y=value, observation=o.id, verdict=verdict
                )
            )
    return out


def _short_month(month: str, t: Translator) -> str:
    return t.t(f"month.short.{int(month.split('-')[1])}")


def _full_month(month: str, t: Translator) -> str:
    return t.month_name(int(month.split("-")[1]))


def _month_name(month: str, t: Translator) -> str:
    """``Aug 2023`` in the report's language."""
    return t.t(
        "chart.share.month", month=_short_month(month, t), year=month.split("-", maxsplit=1)[0]
    )


class ChartPlanner:
    """Builds the charts other than the main one, in the report language.

    Args:
        translator: Titles and axis labels.
        pair_label: Display label of a (topic, edition) pair, substitutes included.
        short_label: Compact label for category axes (``uk`` for ``uk.wikipedia``); the
            full label is used when not given.
        show_season: Whether an edition's seasonal pattern deserves a chart; the rule lives
            with the findings (:func:`~wiki_interest.application.insights.season_visibility`)
            so a chart never shows a pattern the text calls too weak. All are shown when
            not given.
        seasons: The season of each ``(topic_id, edition domain)``, as the text reads it
            (:func:`~wiki_interest.domain.observations.season_profile`); an edition without
            one gets no season chart.
    """

    def __init__(
        self,
        translator: Translator,
        pair_label: Callable[[str, WikiProject], str],
        short_label: Callable[[str, WikiProject], str] | None = None,
        *,
        show_season: Callable[[PairAnalysis], bool] | None = None,
        seasons: Mapping[tuple[str, str], SeasonProfile] | None = None,
    ) -> None:
        self._t = translator
        self._label = pair_label
        self._short = short_label or pair_label
        self._show_season = show_season
        self._seasons = seasons or {}

    def _season(self, pair: PairAnalysis) -> SeasonProfile | None:
        return self._seasons.get((pair.topic_id, pair.project.domain))

    def _seasonal(self, pair: PairAnalysis) -> bool:
        if self._season(pair) is None:
            return False
        return self._show_season is None or self._show_season(pair)

    def _pair(self, pair: PairAnalysis) -> str:
        return self._label(pair.topic_id, pair.project)

    def _id(self, prefix: str, pair: PairAnalysis) -> str:
        return f"{prefix}-{pair.topic_id}-{pair.project.language}".lower()

    def plan(self, pairs: Sequence[PairAnalysis], *, normalised: bool) -> list[ChartSpec]:
        """The scatter for many audiences and the seasons; the main chart comes separately."""
        measured = [p for p in pairs if p.views is not None]
        if not measured:
            return []
        second = (
            self.size_and_change(measured, normalised=normalised)
            if len(measured) > _FEW_FOR_ONE_CHART
            else None
        )
        season = (
            self.season_bars(measured[0]) if len(measured) == 1 else self.season_lines(measured)
        )
        return [c for c in (second, season) if c is not None]

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
            size="strip",
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
        profile = self._season(pair)
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
                    y=list(profile.percents),
                )
            ],
            reference_y=0.0,
            value_suffix="%",
        )

    def season_lines(self, pairs: Sequence[PairAnalysis]) -> ChartSpec | None:
        """Seasonal profiles of the editions that have one, on one chart."""
        profiled = [(p, self._season(p)) for p in pairs[:_MAX_LINES] if self._seasonal(p)]
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
                    y=list(profile.percents),
                )
                for p, profile in profiled
                if profile is not None
            ],
            reference_y=0.0,
        )

    def _season_period(self, pair: PairAnalysis) -> str | None:
        season = self._season(pair)
        if season is None:
            return None
        return self._t.t(
            "chart.season_period",
            start=_month_label(season.first),
            end=_month_label(season.last),
        )


def _month_label(day: date) -> str:
    return day.strftime("%Y-%m")
