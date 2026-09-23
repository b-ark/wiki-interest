"""Which charts a report shows, as declarative :class:`ChartSpec` objects.

Every chart answers one question a reader has about the numbers. The main chart, full
width, answers "how large is the interest and where is it heading": the topic's share of its
edition's attention, month by month, which is comparable across Wikipedias of any size (or
the views, when the user asked for raw numbers). The smaller charts under it answer:

* does the topic grow faster or slower than its whole edition (a falling share can be the
  edition growing, not the topic shrinking);
* which months of the year are strong and weak, when that pattern is worth showing;
* on which days the bursts were, for a single audience;
* how the audiences rank, for a ranking.

The planner only decides content; the renderer draws. Methods return ``None`` when the data
cannot support the chart, and the caller drops it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import date
from statistics import fmean

from wiki_interest.application.analysis import AnalysisResult, PairAnalysis
from wiki_interest.contracts.charts import ChartSeries, ChartSpec
from wiki_interest.domain.models import Series, WikiProject
from wiki_interest.domain.trend_tests import detrend
from wiki_interest.i18n import Translator

__all__ = ["ChartPlanner"]

_INDEX_BASE_MONTHS = 12
"""The index starts at the mean of the first year (100), which is steadier than one month."""
_LOG_SCALE_RATIO = 20.0
"""Absolute views of editions this far apart are drawn on a log axis, or the small one is flat."""
_MAX_LINES = 6
_MONTHS = 12
_PERCENT = 100.0


class ChartPlanner:
    """Builds chart specifications in the report language.

    The main chart is full width; the others are planned half-width, for a two-column grid,
    and without a footnote: the page footer names the source and the subtitle the period.
    :meth:`widen` turns a half chart that ends up alone into a full-width one.

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
        if pair.findings.seasonality is None:
            return False
        return self._show_season is None or self._show_season(pair)

    def widen(self, spec: ChartSpec) -> ChartSpec:
        """The same chart at full width, with the source and period under it."""
        return spec.model_copy(update={"size": "wide", "footnote": self._footnote})

    def _pair(self, pair: PairAnalysis) -> str:
        return self._label(pair.topic_id, pair.project)

    def _id(self, prefix: str, pair: PairAnalysis) -> str:
        return f"{prefix}-{pair.topic_id}-{pair.project.language}".lower()

    # -- the main chart ---------------------------------------------------------------------

    def main(self, pairs: Sequence[PairAnalysis], normalised: bool) -> ChartSpec | None:
        """The full-width chart the report leads with: share of attention over time.

        One audience gets its monthly series with a fitted trend and the burst months shaded;
        several get one line each. Without normalisation the views are drawn instead.
        """
        if len(pairs) == 1:
            return self._trend(pairs[0], normalised)
        return self._lines(pairs, normalised)

    def _trend(self, pair: PairAnalysis, normalised: bool) -> ChartSpec | None:
        """Monthly share (or views) with a fitted trend line; months with a burst are shaded."""
        series = pair.per_million if normalised else pair.views
        if series is None:
            return None
        values = list(series.values)
        residuals = detrend(values)
        trend = [
            None if v is None or r is None else v - r
            for v, r in zip(values, residuals, strict=True)
        ]
        burst_months = {
            _month_label(day)
            for burst in pair.findings.anomalies
            for day in (burst.start, burst.end)
        }
        if normalised:
            title = self._t.t("chart.share_single_title", label=self._pair(pair))
            subtitle: str | None = self._t.t("chart.share_subtitle")
            axis = "chart.axis_per_million"
        else:
            title = self._t.t("chart.views_title", label=self._pair(pair))
            subtitle = None
            axis = "chart.axis_views"
        return ChartSpec(
            id=self._id("share" if normalised else "views", pair),
            kind="trend",
            size="wide",
            title=title,
            subtitle=subtitle,
            y_label=self._t.t(axis),
            series=[ChartSeries(label=self._pair(pair), x=_months(series), y=values)],
            trend_y=trend,
            highlight_x=sorted(burst_months),
        )

    def _lines(self, pairs: Sequence[PairAnalysis], normalised: bool) -> ChartSpec | None:
        """One line per audience: the share of attention, or views on a log axis if needed."""
        shown = pairs[:_MAX_LINES]
        if normalised:
            series = [
                ChartSeries(label=self._pair(p), x=_months(s), y=list(s.values))
                for p in shown
                if (s := p.per_million) is not None
            ]
            if not series:
                return None
            return ChartSpec(
                id="share",
                kind="lines",
                size="wide",
                title=self._t.t("chart.share_title"),
                subtitle=self._t.t("chart.share_subtitle"),
                y_label=self._t.t("chart.axis_per_million"),
                series=series,
            )
        observed = [p for p in shown if p.views is not None and p.views.observed]
        if not observed:
            return None
        means = [fmean(p.views.observed) for p in observed if p.views is not None]
        log_y = min(means) > 0 and max(means) / min(means) > _LOG_SCALE_RATIO
        return ChartSpec(
            id="views",
            kind="lines",
            size="wide",
            title=self._t.t("chart.views_compare_title"),
            y_label=self._t.t("chart.axis_views_log" if log_y else "chart.axis_views"),
            series=[
                ChartSeries(label=self._pair(p), x=_months(p.views), y=list(p.views.values))
                for p in observed
                if p.views is not None
            ],
            log_y=log_y,
        )

    # -- one pair ---------------------------------------------------------------------------

    def against_edition(self, pair: PairAnalysis) -> ChartSpec | None:
        """The article and its whole edition on one scale: both start at 100."""
        views = pair.views
        if views is None:
            return None
        article = _index(views)
        edition = _index(pair.edition_total)
        if article is None or edition is None:
            return None
        return ChartSpec(
            id=self._id("edition", pair),
            kind="lines",
            size="half",
            title=self._t.t("chart.edition_title"),
            y_label=self._t.t("chart.axis_index"),
            series=[
                ChartSeries(label=self._t.t("chart.series_article"), x=_months(views), y=article),
                ChartSeries(
                    label=self._t.t("chart.series_edition", project=pair.project.domain),
                    x=_months(views),
                    y=edition,
                ),
            ],
            reference_y=100.0,
        )

    def season_bars(self, pair: PairAnalysis) -> ChartSpec | None:
        """Each calendar month against the usual level, in percent."""
        profile = pair.findings.seasonality
        if profile is None or not self._seasonal(pair):
            return None
        return ChartSpec(
            id=self._id("season", pair),
            kind="bars",
            size="half",
            title=self._t.t("chart.season_title"),
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

    def daily(self, pair: PairAnalysis) -> ChartSpec | None:
        """Daily views with the named bursts shaded, so their dates can be read off."""
        daily = pair.daily
        if daily is None or not daily.observed:
            return None
        burst_days = {
            day.isoformat()
            for burst in pair.findings.anomalies
            for day in _days_between(burst.start, burst.end)
        }
        return ChartSpec(
            id=self._id("daily", pair),
            kind="trend",
            size="half",
            title=self._t.t("chart.daily_title"),
            y_label=self._t.t("chart.axis_daily"),
            series=[
                ChartSeries(
                    label=self._pair(pair),
                    x=[p.period.isoformat() for p in daily.points],
                    y=list(daily.values),
                )
            ],
            highlight_x=sorted(burst_days),
        )

    # -- several pairs ----------------------------------------------------------------------

    def edition_growth(self, pairs: Sequence[PairAnalysis]) -> ChartSpec | None:
        """Per edition, the article's growth next to its whole edition's, same months."""
        compared = [(p, p.findings.edition) for p in pairs if p.findings.edition is not None]
        if not compared:
            return None
        bases = {edition.basis for _, edition in compared if edition is not None}
        basis = bases.pop() if len(bases) == 1 else "mixed"
        labels = [self._short(p.topic_id, p.project) for p, _ in compared]
        return ChartSpec(
            id="edition-growth",
            kind="grouped_bars",
            size="half",
            title=self._t.t("chart.edition_growth_title", basis=self._t.t(f"basis.{basis}")),
            y_label=self._t.t("chart.axis_growth"),
            series=[
                ChartSeries(
                    label=self._t.t("chart.series_article"),
                    x=labels,
                    y=[round(e.article_change * _PERCENT, 1) for _, e in compared if e],
                ),
                ChartSeries(
                    label=self._t.t("chart.series_edition_short"),
                    x=labels,
                    y=[round(e.edition_change * _PERCENT, 1) for _, e in compared if e],
                ),
            ],
            reference_y=0.0,
            value_suffix="%",
        )

    def season_lines(self, pairs: Sequence[PairAnalysis]) -> ChartSpec | None:
        """Seasonal profiles of the editions that have one, on one chart."""
        profiled = [(p, p.findings.seasonality) for p in pairs[:_MAX_LINES] if self._seasonal(p)]
        if not profiled:
            return None
        months = [self._t.t(f"month.short.{m}") for m in range(1, _MONTHS + 1)]
        return ChartSpec(
            id="season",
            kind="lines",
            size="half",
            title=self._t.t("chart.season_title"),
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

    def ranking(self, analysis: AnalysisResult) -> ChartSpec | None:
        """Ranking score per audience, best first."""
        if not analysis.ranking:
            return None
        return ChartSpec(
            id="ranking-score",
            kind="bars",
            size="half",
            title=self._t.t("chart.score_title"),
            y_label=self._t.t("chart.axis_score"),
            series=[
                ChartSeries(
                    label=self._t.t("chart.score_title"),
                    x=[self._short(r.topic_id, r.project) for r in analysis.ranking],
                    y=[round(r.score, 4) for r in analysis.ranking],
                )
            ],
        )


def _months(series: Series) -> list[str]:
    return [_month_label(p.period) for p in series.points]


def _month_label(day: date) -> str:
    return day.strftime("%Y-%m")


def _index(series: Series) -> list[float | None] | None:
    """The series as an index: the mean of its first year (or first third) is 100."""
    values = series.values
    span = min(_INDEX_BASE_MONTHS, max(1, len(values) // 3))
    base_values = [v for v in values[:span] if v is not None]
    if not base_values or fmean(base_values) <= 0:
        return None
    base = fmean(base_values)
    return [None if v is None else round(v / base * _PERCENT, 1) for v in values]


def _days_between(start: date, end: date) -> list[date]:
    return [date.fromordinal(o) for o in range(start.toordinal(), end.toordinal() + 1)]
