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

With many audiences a second chart sets the size of each share against its change, one point
per audience. A seasonal chart follows when the pattern deserves one. The planner only
decides content; the renderer draws. Methods return ``None`` when the data cannot support the
chart.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from datetime import date
from typing import Literal

from wiki_interest.application.analysis import PairAnalysis
from wiki_interest.application.assessment import headline_growth
from wiki_interest.contracts.charts import (
    ChartPoint,
    ChartSeries,
    ChartSpec,
    ShareChange,
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
    round_count,
    round_share,
    year_levels,
)
from wiki_interest.i18n import Translator

__all__ = ["SHARE_CHART_ID", "ChartPlanner", "share_years_data", "share_years_spec"]

SHARE_CHART_ID = "share"
_YEAR = 12
_RECENT = 3
_MAX_SHARE_LINES = 3
"""More lines on one scale merge; with more audiences the scatter compares them all."""
_MAX_LINES = 6
_MONTHS = 12
_PERCENT = 100.0
_FEW_FOR_ONE_CHART = 3
"""Up to this many audiences the main chart shows them all; more add the scatter."""
_MARKED = ("step", "spike")


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
        observations: What the detectors found: steps and bursts to mark, and which pairs
            got a last-12-months comparison with their edition.
        trend_start: First month the trend reads (a period the user named), or ``None``.
        absolute: Views a month instead of the attention share.
        topic_labels: Topic id -> label, to name lines when there are several topics.
    """
    drawn: list[tuple[PairHistory, ShareLine]] = []
    topics = {h.topic_id for h in histories}
    languages = {h.language for h in histories}
    for history in histories:
        years = year_levels(history, trend_start=trend_start)
        if not years:
            continue
        first = years[0].first
        kept = [k for k, m in enumerate(history.months) if m >= first]
        segments = [
            ShareSegment(
                year=y.year,
                start=_month_label(y.first),
                end=_month_label(y.last),
                value=round_count(y.views) if absolute else round_share(y.share),
                partial=y.partial,
            )
            for y in years
        ]
        line = ShareLine(
            label=_line_label(history, topics, languages, topic_labels),
            x=[_month_label(history.months[k]) for k in kept],
            y=[_value(history, k, absolute=absolute) for k in kept],
            years=segments,
        )
        drawn.append((history, line))
    if not drawn:
        return None
    if len(drawn) > _MAX_SHARE_LINES:
        top = sorted(drawn, key=lambda d: d[1].years[-1].value, reverse=True)
        kept_pairs = {h.pair for h, _ in top[:_MAX_SHARE_LINES]}
        drawn = [d for d in drawn if d[0].pair in kept_pairs]
    months = drawn[0][0].months
    return ShareYears(
        absolute=absolute,
        lines=[line for _, line in drawn],
        marks=_marks(drawn, observations),
        changes=_changes(drawn, observations),
        changes_start=_month_label(months[-_YEAR]) if len(months) >= _YEAR else None,
        changes_end=_month_label(months[-1]),
        recent_months=_RECENT,
    )


def share_years_spec(data: ShareYears, t: Translator, cited: Collection[str]) -> ChartSpec:
    """The main chart in the report's language, marking only what the text cites.

    Args:
        data: What the chart draws (:func:`share_years_data`).
        t: The report-language translator, the agent's labels included.
        cited: Ids of the observations the report text cites.
    """
    by_year: dict[int, ShareSegment] = {}
    for line in data.lines:
        for segment in line.years:
            by_year.setdefault(segment.year, segment)
    year_labels = [
        t.t(
            "chart.share.partial_year",
            year=year,
            first=_short_month(segment.start, t),
            last=_short_month(segment.end, t),
        )
        if segment.partial
        else str(year)
        for year, segment in sorted(by_year.items())
    ]
    # Every mark's label is composed, cited or not: the labels the agent must translate are
    # the ones composed, and a text written later may cite any of them.
    labels = [t.t(f"chart.share.{mark.kind}", month=_month_name(mark.x, t)) for mark in data.marks]
    mark_labels = [
        label if mark.observation in cited else None
        for mark, label in zip(data.marks, labels, strict=True)
    ]
    note = None
    if data.changes and data.changes_start and data.changes_end:
        lines = [
            t.t(
                "chart.share.changes",
                start=_month_name(data.changes_start, t),
                end=_month_name(data.changes_end, t),
            ),
            *(
                t.t(
                    "chart.share.change",
                    label=c.label,
                    article=t.percent(c.article / _PERCENT, signed=True),
                    edition=t.percent(c.edition / _PERCENT, signed=True),
                )
                for c in data.changes
            ),
        ]
        note = "\n".join(lines)
    kind = "absolute" if data.absolute else "share"
    return ChartSpec(
        id=SHARE_CHART_ID,
        kind="share_years",
        size="wide",
        title=t.t(f"chart.{kind}.title"),
        subtitle=t.t(f"chart.{kind}.subtitle"),
        y_label=t.t(f"chart.{kind}.axis"),
        share=data,
        year_labels=year_labels,
        mark_labels=mark_labels,
        legend=[
            t.t("chart.share.legend_year"),
            t.t("chart.share.legend_month"),
            t.t("chart.share.legend_recent", months=data.recent_months),
        ],
        note=note,
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
    """``uk`` for one topic; the topic for one edition; both otherwise."""
    topic = topic_labels.get(history.topic_id, history.topic_id)
    if len(topics) == 1:
        return history.language
    if len(languages) == 1:
        return topic
    return f"{topic} · {history.language}"


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


def _changes(
    drawn: Sequence[tuple[PairHistory, ShareLine]], observations: Sequence[Observation]
) -> list[ShareChange]:
    """The last 12 months against the 12 before, as ``vs_edition`` computes them.

    Only for the audiences that got that observation: the chart repeats what the text may
    cite, never a comparison the detectors held too short to make.
    """
    compared = {o.pair for o in observations if o.kind == "vs_edition"}
    out: list[ShareChange] = []
    for history, line in drawn:
        if history.pair not in compared or len(history.months) < 2 * _YEAR:
            continue
        article = _change(history.views)
        edition = _change(history.edition)
        if article is None or edition is None:
            continue
        out.append(ShareChange(label=line.label, article=round(article), edition=round(edition)))
    return out


def _change(values: Sequence[float | None]) -> float | None:
    last = sum(v for v in values[-_YEAR:] if v is not None)
    before = sum(v for v in values[-2 * _YEAR : -_YEAR] if v is not None)
    return (last / before - 1) * _PERCENT if last and before else None


def _short_month(month: str, t: Translator) -> str:
    return t.t(f"month.short.{int(month.split('-')[1])}")


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
