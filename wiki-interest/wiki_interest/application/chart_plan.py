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

from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
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
    ShareYears,
)
from wiki_interest.domain.findings import SeasonalProfile
from wiki_interest.domain.models import WikiProject
from wiki_interest.domain.observations import (
    Observation,
    PairHistory,
    YearLevel,
    round_count,
    round_share,
    share_move,
    year_levels,
)
from wiki_interest.i18n import Translator

__all__ = [
    "AUDIENCE_CHART_ID",
    "SHARE_CHART_ID",
    "ChartPlanner",
    "audience_years_data",
    "audience_years_spec",
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
    """An audience the charts draw: its series, its calendar years and its name on them."""

    history: PairHistory
    years: list[YearLevel]
    label: str


def _drawn(
    histories: Sequence[PairHistory],
    *,
    trend_start: date | None,
    absolute: bool,
    topic_labels: Mapping[str, str],
) -> list[_Drawn]:
    """The audiences both charts draw, in the order of the request.

    With more than the lines one scale holds, the largest by their last year; the two charts
    always show the same audiences under the same names.
    """
    topics = {h.topic_id for h in histories}
    languages = {h.language for h in histories}
    drawn = [
        _Drawn(history, years, _line_label(history, topics, languages, topic_labels))
        for history in histories
        if (years := year_levels(history, trend_start=trend_start))
    ]
    if len(drawn) > _MAX_SHARE_LINES:

        def size(d: _Drawn) -> float:
            return d.years[-1].views if absolute else d.years[-1].share

        largest = sorted(drawn, key=size, reverse=True)[:_MAX_SHARE_LINES]
        kept = {d.history.pair for d in largest}
        drawn = [d for d in drawn if d.history.pair in kept]
    return drawn


def share_years_data(
    histories: Sequence[PairHistory],
    observations: Sequence[Observation],
    *,
    trend_start: date | None,
    absolute: bool,
    topic_labels: Mapping[str, str],
) -> ShareYears | None:
    """What the main chart draws, from the series and windows the observations read.

    Args:
        histories: The pairs' long series.
        observations: What the detectors found: the steps and bursts to mark.
        trend_start: First month the trend reads (a period the user named), or ``None``.
        absolute: Views a month instead of the attention share.
        topic_labels: Topic id -> label, to name lines when there are several topics.
    """
    drawn: list[tuple[PairHistory, ShareLine]] = []
    for d in _drawn(
        histories, trend_start=trend_start, absolute=absolute, topic_labels=topic_labels
    ):
        history = d.history
        kept = [k for k, m in enumerate(history.months) if m >= d.years[0].first]
        segments = [
            ShareSegment(
                year=y.year,
                start=_month_label(y.first),
                end=_month_label(y.last),
                value=round_count(y.views) if absolute else round_share(y.share),
                partial=y.partial,
            )
            for y in d.years
        ]
        line = ShareLine(
            label=d.label,
            x=[_month_label(history.months[k]) for k in kept],
            y=[_value(history, k, absolute=absolute) for k in kept],
            years=segments,
        )
        drawn.append((history, line))
    if not drawn:
        return None
    return ShareYears(
        absolute=absolute,
        lines=[line for _, line in drawn],
        marks=_marks(drawn, observations),
        recent_months=_RECENT,
    )


def audience_years_data(
    histories: Sequence[PairHistory],
    *,
    trend_start: date | None,
    topic_labels: Mapping[str, str],
) -> AudienceYears | None:
    """What the chart of views by year draws: the main chart's audiences and calendar years.

    Each year's change is the one ``vs_edition`` states for "now": the views against the
    same months a year earlier, a partial year against the same months only; whether the
    share gained, held or lost uses the observations' threshold (:func:`share_move`).
    """
    lines = [
        AudienceLine(
            label=d.label,
            years=[
                AudienceYear(
                    year=y.year,
                    start=_month_label(y.first),
                    end=_month_label(y.last),
                    views=round_count(y.views),
                    change=None if y.change is None else round(y.change.article),
                    move=None if y.change is None else share_move(y.change.share),
                    partial=y.partial,
                )
                for y in d.years
            ],
        )
        for d in _drawn(
            histories, trend_start=trend_start, absolute=False, topic_labels=topic_labels
        )
    ]
    return AudienceYears(lines=lines) if lines else None


def audience_years_spec(data: AudienceYears, t: Translator) -> ChartSpec:
    """The chart of views by year in the report's language.

    A partial year gets a quiet line saying what it is compared with, so its change is not
    read against the whole year before.
    """
    years = [(y.year, y.start, y.end, y.partial) for line in data.lines for y in line.years]
    partial = next(
        (y for line in data.lines for y in line.years if y.partial and y.change is not None),
        None,
    )
    note = None
    if partial is not None:
        note = t.t(
            "chart.audience.partial",
            year=partial.year,
            first=_full_month(partial.start, t),
            last=_full_month(partial.end, t),
            previous=partial.year - 1,
        )
    return ChartSpec(
        id=AUDIENCE_CHART_ID,
        kind="audience_years",
        size="wide",
        title=t.t("chart.audience.title"),
        subtitle=t.t("chart.audience.subtitle"),
        y_label=t.t("chart.absolute.axis"),
        audience=data,
        year_labels=_year_labels(years, t),
        note=note,
    )


def _year_labels(years: Iterable[tuple[int, str, str, bool]], t: Translator) -> list[str]:
    """One label per calendar year, in order: ``2025``, ``2026 (Jan – Aug)``.

    Args:
        years: ``(year, first month, last month, partial)`` of every drawn year.
        t: The report-language translator.
    """
    by_year: dict[int, tuple[str, str, bool]] = {}
    for year, start, end, partial in years:
        by_year.setdefault(year, (start, end, partial))
    return [
        t.t(
            "chart.share.partial_year",
            year=year,
            first=_short_month(start, t),
            last=_short_month(end, t),
        )
        if partial
        else str(year)
        for year, (start, end, partial) in sorted(by_year.items())
    ]


def share_years_spec(data: ShareYears, t: Translator, cited: Collection[str]) -> ChartSpec:
    """The main chart in the report's language, marking only what the text cites.

    Args:
        data: What the chart draws (:func:`share_years_data`).
        t: The report-language translator, the agent's labels included.
        cited: Ids of the observations the report text cites.
    """
    year_labels = _year_labels(
        ((s.year, s.start, s.end, s.partial) for line in data.lines for s in line.years), t
    )
    # A mark says its month only: the text that cites it says what happened, and a longer
    # label in a longer language would run into the next one.
    labels = [_month_name(mark.x, t) for mark in data.marks]
    mark_labels = [
        label if mark.observation in cited else None
        for mark, label in zip(data.marks, labels, strict=True)
    ]
    # The last months are shaded only when the text speaks of them: a band it never explains
    # is one more layer to read.
    recent = any(oid.startswith(_RECENT_OBSERVATION) for oid in cited)
    legend = [t.t("chart.share.legend_year"), t.t("chart.share.legend_month")]
    # Composed whether shown or not: the labels the agent translates are the ones composed,
    # and its text may cite the last months after the translations were asked for.
    recent_label = t.t("chart.share.legend_recent", months=data.recent_months)
    if recent:
        legend.append(recent_label)
    kind = "absolute" if data.absolute else "share"
    return ChartSpec(
        id=SHARE_CHART_ID,
        kind="share_years",
        size="wide",
        title=t.t(f"chart.{kind}.title"),
        subtitle=t.t(f"chart.{kind}.subtitle"),
        y_label=t.t(f"chart.{kind}.axis"),
        share=data if recent else data.model_copy(update={"recent_months": 0}),
        year_labels=year_labels,
        mark_labels=mark_labels,
        legend=legend,
    )


def _value(history: PairHistory, k: int, *, absolute: bool) -> float | None:
    views, edition = history.views[k], history.edition[k]
    if absolute:
        return views
    return None if views is None or not edition else round(views / edition * 1e6, 3)


def _line_label(
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
    drawn: Sequence[tuple[PairHistory, ShareLine]], observations: Sequence[Observation]
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
            out.append(ShareMark(kind=kind, line=index, x=month, y=value, observation=o.id))
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
    """

    def __init__(
        self,
        translator: Translator,
        pair_label: Callable[[str, WikiProject], str],
        short_label: Callable[[str, WikiProject], str] | None = None,
        *,
        show_season: Callable[[PairAnalysis], bool] | None = None,
    ) -> None:
        self._t = translator
        self._label = pair_label
        self._short = short_label or pair_label
        self._show_season = show_season

    def _seasonal(self, pair: PairAnalysis) -> bool:
        if _profile(pair) is None:
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


def _month_label(day: date) -> str:
    return day.strftime("%Y-%m")


def _profile(pair: PairAnalysis) -> SeasonalProfile | None:
    """The seasonal profile of the pair's whole history, if one could be computed."""
    season = pair.findings.season
    return season.profile if season is not None else None
