"""Use-case: the analysis window against the history, and the window's verdict of each pair.

The window is the period the user asked for (the last 24 complete months by default): the
headline, the verdict of each language, the comparison between them and the recommendation
read it alone. The history before it is context: the charts show it from the first January
of the six years the observations read, and the text names it as such.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from datetime import date

from wiki_interest.contracts.request import Period
from wiki_interest.contracts.summary import TrendOut
from wiki_interest.domain.observations import (
    ObservationSettings,
    PairHistory,
    edition_name,
    first_data,
    pair_steps,
    round_count,
    round_share,
)
from wiki_interest.domain.trust import TrendVerdict, TrustSettings, WindowTrend, window_trend
from wiki_interest.i18n import Translator

__all__ = [
    "context_range",
    "headline",
    "read_trends",
    "trend_outs",
    "verdict_phrase",
]

_YEAR = 12
_PERCENT = 100.0
MINUS = "\u2212"
"""A negative change is written with the minus sign, as the charts and observations write it."""


def context_range(period: Period, observe_from: date) -> Period:
    """The months the charts show: from the first January the history has, to the window's end.

    The observations read six years back from the window's end; the charts start at the
    first January of those, so their years are whole. A window that starts earlier starts
    the context too.
    """
    first = observe_from
    if first.month != 1:
        first = date(first.year + 1, 1, 1)
    return Period(start=min(first, period.start), end=period.end)


def read_trends(
    histories: Sequence[PairHistory],
    window_start: date,
    *,
    settings: TrustSettings | None = None,
    observation_settings: ObservationSettings | None = None,
) -> dict[str, WindowTrend]:
    """The window's verdict of every pair with data, keyed by ``<topic>/<language>``."""
    trust = settings or TrustSettings()
    observed = observation_settings or ObservationSettings()
    out: dict[str, WindowTrend] = {}
    for history in histories:
        trimmed = first_data(history)
        if trimmed is None:
            continue
        steps, adjusted, _ = pair_steps(trimmed, observed, threshold=trust.split_step)
        out[history.pair] = window_trend(
            trimmed, window_start=window_start, steps=steps, adjusted=adjusted, settings=trust
        )
    return out


def verdict_phrase(trend: TrendOut, t: Translator) -> str:
    """How the report says a verdict: "interest has stabilised after a drop".

    A verdict read after a step says so: a level that fell once and then held has
    stabilised, one that fell and still falls keeps declining.
    """
    key: str = trend.verdict
    if trend.after_step is not None and trend.step_change is not None:
        down = trend.step_change < 0
        if key == TrendVerdict.STABLE.value:
            key = "stable_after_drop" if down else "stable_after_rise"
        elif key == TrendVerdict.DECLINING.value and down:
            key = "declining_still"
        elif key == TrendVerdict.GROWING.value and not down:
            key = "growing_still"
    return t.t(f"verdict.{key}")


def trend_outs(
    trends: Mapping[str, WindowTrend],
    labels: Mapping[str, str],
    t: Translator,
    substitutes: Collection[str] = (),
) -> list[TrendOut]:
    """The verdicts as the summary keeps them: rounded as shown, with their line.

    Args:
        trends: The window's verdict of each pair.
        labels: ``<topic>/<language>`` -> how the charts name the pair (``ru``).
        t: The report-language translator.
        substitutes: Pairs measured through another article.
    """
    out: list[TrendOut] = []
    for pair, trend in trends.items():
        topic_id, language = pair.split("/")
        item = TrendOut(
            topic_id=topic_id,
            project=f"{language}.wikipedia",
            label=labels.get(pair, language),
            verdict=trend.verdict.value,
            window_start=f"{trend.window_start:%Y-%m}",
            window_end=f"{trend.window_end:%Y-%m}",
            segment_start=f"{trend.segment_start:%Y-%m}",
            after_step=f"{trend.step.month:%Y-%m}" if trend.step else None,
            step_change=round((trend.step.ratio - 1) * _PERCENT) if trend.step else None,
            slope_pct_per_year=(
                None if trend.slope_pct_per_year is None else round(trend.slope_pct_per_year)
            ),
            level_start=None if trend.level_start is None else round_share(trend.level_start),
            level_end=None if trend.level_end is None else round_share(trend.level_end),
            views_avg=None if trend.views_avg is None else round_count(trend.views_avg),
            substitute=pair in substitutes,
        )
        out.append(item.model_copy(update={"line": verdict_line(item, t)}))
    return out


def verdict_line(trend: TrendOut, t: Translator) -> str:
    """One line per language: its verdict and the trend line's levels.

    "ru: interest has stabilised after a drop. Attention share from 2024-12: 8.9 → 8.2 per
    1M views, -5% a year."
    """
    phrase = verdict_phrase(trend, t)
    if trend.level_start is None or trend.level_end is None or trend.slope_pct_per_year is None:
        return t.t("verdict.line_none", label=trend.label, verdict=phrase)
    since = t.t("verdict.since", month=trend.segment_start)
    return t.t(
        "verdict.line",
        label=trend.label,
        verdict=phrase,
        since=since,
        start=t.number(trend.level_start, 1),
        end=t.number(trend.level_end, 1),
        slope=t.percent(trend.slope_pct_per_year / _PERCENT, 0, signed=True).replace("-", MINUS),
    )


def headline(topic: str, trends: Sequence[TrendOut], t: Translator) -> str | None:
    """The report's headline: the window's verdict of every language, in one sentence.

    Built from the verdicts, never from the history, so the answer matches the verdict lines
    under it. ``None`` without a verdict.
    """
    trends = [x for x in trends if not x.substitute]
    if not trends:
        return None
    parts = [
        t.t(
            "headline.part",
            edition=edition_in(x.project, t),
            verdict=verdict_phrase(x, t),
        )
        for x in trends
    ]
    return t.t("headline.topic", topic=_capital(topic), parts="; ".join(parts))


def edition_in(project: str, t: Translator) -> str:
    """The place form of an edition in the report's language: "in the Russian Wikipedia"."""
    key = f"edition.in.{project.split('.', maxsplit=1)[0]}"
    return t.t(key) if t.has(key) else f"in {edition_name(project)}"


def edition_nominative(project: str, t: Translator) -> str:
    """The name of an edition in the report's language: "the Russian Wikipedia"."""
    key = f"edition.name.{project.split('.', maxsplit=1)[0]}"
    return t.t(key) if t.has(key) else edition_name(project)


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]
