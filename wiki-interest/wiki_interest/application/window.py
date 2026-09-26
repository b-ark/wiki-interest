"""Use-case: the analysis window against the history, and the window's verdict of each pair.

The window is the period the user asked for (the last 24 complete months by default): the
headline, the verdict of each language, the comparison between them and the recommendation
read it alone. The history before it is context: the charts show it from the first January
of the six years the observations read, and the text names it as such.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from datetime import date

from wiki_interest.application.control import ControlBaskets, RenameLog
from wiki_interest.application.loading import LoadedSeries
from wiki_interest.application.resolution import ResolvedTopic
from wiki_interest.contracts.request import Period
from wiki_interest.contracts.summary import BreakpointOut, ReasonOut, TrendOut, TrustOut
from wiki_interest.domain.models import WikiProject
from wiki_interest.domain.observations import (
    Observation,
    ObservationSettings,
    PairHistory,
    Quoted,
    Step,
    Weight,
    edition_name,
    first_data,
    pair_steps,
    round_count,
    round_share,
)
from wiki_interest.domain.trust import (
    Breakpoint,
    TrendVerdict,
    Trust,
    TrustSettings,
    WindowTrend,
    assess_trust,
    breakpoint_verdict,
    control_step,
    day_spike_months,
    segment_slope,
    window_trend,
)
from wiki_interest.errors import UpstreamError
from wiki_interest.i18n import Translator

__all__ = [
    "ControlSeries",
    "DayShares",
    "WindowReading",
    "compact_trust_line",
    "context_range",
    "headline",
    "read_day_shares",
    "read_trends",
    "read_trust",
    "read_window",
    "reason_text",
    "trend_outs",
    "trust_line",
    "trust_observation",
    "trust_out",
    "verdict_phrase",
    "with_lines",
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
    spikes: Mapping[str, Collection[date]] | None = None,
    settings: TrustSettings | None = None,
    observation_settings: ObservationSettings | None = None,
) -> dict[str, WindowTrend]:
    """The window's verdict of every pair with data, keyed by ``<topic>/<language>``.

    ``spikes``: months one day dominated, per pair; they are left out of the slope.
    """
    trust = settings or TrustSettings()
    observed = observation_settings or ObservationSettings()
    out: dict[str, WindowTrend] = {}
    for history in histories:
        trimmed = first_data(history)
        if trimmed is None:
            continue
        steps, adjusted, _ = pair_steps(trimmed, observed, threshold=trust.split_step)
        left_out = set((spikes or {}).get(history.pair, ()))
        excluded = [k for k, m in enumerate(trimmed.months) if m in left_out]
        out[history.pair] = window_trend(
            trimmed,
            window_start=window_start,
            steps=steps,
            adjusted=adjusted,
            excluded=excluded,
            settings=trust,
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
    trust: Mapping[str, Trust] | None = None,
) -> list[TrendOut]:
    """The verdicts as the summary keeps them: rounded as shown, with their lines.

    Args:
        trends: The window's verdict of each pair.
        labels: ``<topic>/<language>`` -> how the charts name the pair (``ru``).
        t: The report-language translator.
        substitutes: Pairs measured through another article.
        trust: The trust in each verdict (:func:`read_trust`).
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
            trust=trust_out(trust[pair]) if trust and pair in trust else None,
        )
        out.append(with_lines(item, t))
    return out


def with_lines(item: TrendOut, t: Translator) -> TrendOut:
    """``item`` with its verdict line and its trust line in the report's language."""
    lines: dict[str, object] = {"line": verdict_line(item, t)}
    if item.trust is not None:
        lines["trust"] = item.trust.model_copy(update={"line": trust_line(item, t)})
    return item.model_copy(update=lines)


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


# -- trust --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DayShares:
    """What the daily views say about one pair: each month's largest one-day share, the spikes."""

    by_month: dict[date, float]
    spikes: tuple[date, ...]


def read_day_shares(
    daily: Mapping[str, Sequence[tuple[date, float | None]]],
    settings: TrustSettings | None = None,
) -> dict[str, DayShares]:
    """Each pair's months that one day dominated, from its daily views.

    Args:
        daily: ``<topic>/<language>`` -> ``(day, views)`` of the main article.
        settings: ``day_spike_share``.
    """
    out = {}
    for pair, days in daily.items():
        shares, spikes = day_spike_months(days, settings or TrustSettings())
        out[pair] = DayShares(shares, spikes)
    return out


def read_trust(  # noqa: PLR0913 -- a verdict and all that weighs on it
    histories: Sequence[PairHistory],
    trends: Mapping[str, WindowTrend],
    *,
    controls: Mapping[str, ControlSeries] | None = None,
    moves: Mapping[str, Sequence[date]] | None = None,
    days: Mapping[str, DayShares] | None = None,
    settings: TrustSettings | None = None,
    observation_settings: ObservationSettings | None = None,
) -> dict[str, Trust]:
    """The trust in each pair's window verdict.

    Args:
        histories: The pairs' long series.
        trends: The window's verdict of each pair (:func:`read_trends`).
        controls: Edition domain -> its control articles' monthly shares.
        moves: ``<topic>/<language>`` -> the days the article was moved.
        days: ``<topic>/<language>`` -> its daily shares (:func:`read_day_shares`).
        settings: Thresholds of the trust.
        observation_settings: The step detector's thresholds (the history's steps).
    """
    trust = settings or TrustSettings()
    observed = observation_settings or ObservationSettings()
    out: dict[str, Trust] = {}
    for history in histories:
        trimmed = first_data(history)
        trend = trends.get(history.pair)
        if trimmed is None or trend is None:
            continue
        steps, adjusted, _ = pair_steps(trimmed, observed)
        aligned = _aligned((controls or {}).get(history.project), trimmed.months)
        shares = [
            v / e * 1e6 if v is not None and e else None
            for v, e in zip(trimmed.views, trimmed.edition, strict=True)
        ]
        found = _breakpoints(
            trimmed,
            trend,
            steps=steps,
            adjusted=adjusted,
            controls=aligned,
            moves=(moves or {}).get(history.pair, ()),
            settings=trust,
        )
        day = (days or {}).get(history.pair)
        out[history.pair] = assess_trust(
            trend,
            shares=shares,
            breakpoints=found,
            controls=aligned,
            day_shares=day.by_month if day else None,
            spike_months=day.spikes if day else (),
            settings=trust,
        )
    return out


def _breakpoints(  # noqa: PLR0913 -- the pair, its steps and what checks them
    history: PairHistory,
    trend: WindowTrend,
    *,
    steps: Sequence[Step],
    adjusted: Sequence[float | None],
    controls: Sequence[Sequence[float | None]],
    moves: Sequence[date],
    settings: TrustSettings,
) -> list[Breakpoint]:
    """The history's steps and the one the window's trend starts at, each checked."""
    chosen = {s.index: s for s in steps}
    if trend.step is not None:
        chosen.setdefault(trend.step.index, trend.step)
    ordered = [chosen[i] for i in sorted(chosen)]
    out = []
    for n, step in enumerate(ordered):
        previous = ordered[n - 1].index if n else 0
        following = ordered[n + 1].index if n + 1 < len(ordered) else len(history.months)
        change = (step.ratio - 1) * _PERCENT
        control = control_step(controls, step.index) if controls else None
        renamed = any(
            abs(_months_between(step.month, day.replace(day=1))) <= settings.rename_months
            for day in moves
        )
        out.append(
            Breakpoint(
                month=step.month,
                change_pct=change,
                control_change_pct=control,
                renamed=renamed,
                verdict=breakpoint_verdict(change, control, renamed=renamed, settings=settings),
                slope_before=segment_slope(adjusted, previous, step.index),
                slope_after=segment_slope(adjusted, step.index, following),
                in_window=step.month >= trend.window_start,
            )
        )
    return out


@dataclass(frozen=True, slots=True)
class ControlSeries:
    """An edition's control articles: their monthly shares over ``months``."""

    months: tuple[date, ...]
    shares: tuple[tuple[float | None, ...], ...]


def _aligned(
    control: ControlSeries | None, months: Sequence[date]
) -> list[tuple[float | None, ...]]:
    """The control shares over ``months`` (a pair's series may start later than the edition's)."""
    if control is None or not months or months[0] not in control.months:
        return []
    first = control.months.index(months[0])
    return [series[first : first + len(months)] for series in control.shares]


def _months_between(a: date, b: date) -> int:
    return (a.year - b.year) * _YEAR + a.month - b.month


def trust_out(trust: Trust, settings: TrustSettings | None = None) -> TrustOut:
    """The trust as the summary keeps it: rounded as the report shows it."""
    floor = (settings or TrustSettings()).volume_floor
    return TrustOut(
        confidence=trust.confidence.value,
        yoy_down=trust.yoy_down,
        yoy_up=trust.yoy_up,
        yoy_months=trust.yoy_months,
        yoy_consistency=None if trust.yoy_consistency is None else round(trust.yoy_consistency, 2),
        slope_pct_per_year=_whole(trust.slope_pct_per_year),
        ci90=None if trust.ci90 is None else [round(trust.ci90[0]), round(trust.ci90[1])],
        snr=None if trust.snr is None else round(trust.snr, 1),
        control_change=_whole(trust.control_change),
        control_articles=trust.control_articles,
        breakpoints=[
            BreakpointOut(
                month=f"{b.month:%Y-%m}",
                change=round(b.change_pct),
                control_change_same_month=_whole(b.control_change_pct),
                renamed=b.renamed,
                verdict=b.verdict.value,
                slope_before=_whole(b.slope_before),
                slope_after=_whole(b.slope_after),
                in_window=b.in_window,
            )
            for b in trust.breakpoints
        ],
        max_day_share=None if trust.max_day_share is None else round(trust.max_day_share, 2),
        spike_months=[f"{m:%Y-%m}" for m in trust.spike_months],
        views_avg=None if trust.views_avg is None else round_count(trust.views_avg),
        volume_floor=floor,
        reasons=[ReasonOut(code=r.code, params=dict(r.params)) for r in trust.reasons],
    )


def _whole(value: float | None) -> float | None:
    return None if value is None else float(round(value))


_LIMITING = (
    "control_explains",
    "yoy_against",
    "volume_low",
    "window_short",
    "few_months",
    "ci_zero",
    "snr_low",
    "ci_wide",
    "step_not_trend",
    "artifact",
)
"""Reasons that hold a verdict's trust back, the most telling first: the compact line names one."""


def compact_trust_line(verdicts: Sequence[TrendOut], t: Translator) -> str | None:
    """The trust of every verdict in one line: "Trust: ru medium (…); cs high".

    One line for the page: each language's level and the reason that limits it most, none
    for a high level. The full lines stay in the chat answer and ``summary.json``.
    """
    items = []
    for v in verdicts:
        trust = v.trust
        if trust is None or v.substitute:
            continue
        level = t.t(f"trust.level.{trust.confidence}")
        limiting = next((r for code in _LIMITING for r in trust.reasons if r.code == code), None)
        why = t.t("trust.compact_why", reason=reason_text(limiting, t)) if limiting else ""
        items.append(t.t("trust.compact_item", label=v.label, level=level, why=why))
    return t.t("trust.compact", items="; ".join(items)) if items else None


def trust_line(item: TrendOut, t: Translator) -> str:
    """The trust line: "Trust (cs): high - down in 12 of 12 months year on year; ..."."""
    trust = item.trust
    if trust is None:
        return ""
    return t.t(
        "trust.line",
        label=item.label,
        level=t.t(f"trust.level.{trust.confidence}"),
        reasons="; ".join(reason_text(r, t) for r in trust.reasons),
    )


def reason_text(reason: ReasonOut, t: Translator) -> str:  # noqa: PLR0911 -- one wording per code
    """One reason in the report's language, its numbers written as the report writes them."""
    p = reason.params
    code = reason.code
    if code == "yoy":
        verdict = p.get("verdict")
        if verdict == TrendVerdict.DECLINING.value:
            return t.t("trust.reason.yoy_down", count=p["down"], months=p["months"])
        if verdict == TrendVerdict.GROWING.value:
            return t.t("trust.reason.yoy_up", count=p["up"], months=p["months"])
        return t.t("trust.reason.yoy_mixed", down=p["down"], up=p["up"], months=p["months"])
    if code == "slope":
        slope = signed_percent(float(p["slope"]), t)
        if "low" in p:
            return t.t(
                "trust.reason.slope",
                slope=slope,
                low=signed_number(float(p["low"]), t),
                high=signed_number(float(p["high"]), t),
            )
        return t.t("trust.reason.slope_no_ci", slope=slope)
    if code in ("control", "control_explains"):
        return t.t(f"trust.reason.{code}", change=signed_percent(float(p["change"]), t))
    if code == "snr_low":
        return t.t("trust.reason.snr_low", snr=t.number(float(p["snr"]), 1))
    return t.t(f"trust.reason.{code}", **dict(p))


def signed_percent(value: float, t: Translator) -> str:
    """``-18 %``, ``+4 %``, ``0 %`` in the report's style, with the minus sign (U+2212)."""
    return t.percent(value / _PERCENT, 0, signed=True).replace("-", MINUS)


def signed_number(value: float, t: Translator) -> str:
    """``-26``, ``+4``, ``0``: a bound of an interval, with the minus sign (U+2212)."""
    text = t.number(abs(value), 0)
    if round(value) == 0:
        return text
    return (MINUS if value < 0 else "+") + text


def trust_observation(pair: str, topic: str, project: str, trust: TrustOut) -> Observation:
    """The trust of a pair as an observation the agent's text can cite (English).

    The agent says in a few words how far each verdict can be trusted; the code's own line
    stays in the report word for word.
    """
    t = Translator("en")
    reasons = "; ".join(reason_text(r, t) for r in trust.reasons)
    numbers: list[Quoted] = []
    for reason in trust.reasons:
        for name, value in reason.params.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                percent = name in ("slope", "change", "low", "high", "band")
                numbers.append(Quoted(float(value), percent=percent))
                if name in ("low", "high"):
                    numbers.append(Quoted(float(value)))
    return Observation(
        id=f"trust:{pair}",
        kind="trust",
        pair=pair,
        weight=Weight.HIGH,
        statement=(
            f"Trust in the window's verdict for {topic} in {edition_name(project)}: "
            f"{trust.confidence} ({reasons}). Say in a few words how far the verdict holds; "
            "never stronger than this."
        ),
        numbers=tuple(numbers),
    )


@dataclass(frozen=True, slots=True)
class WindowReading:
    """Everything the window says about each pair: its verdict and the trust in it."""

    trends: dict[str, WindowTrend]
    trust: dict[str, Trust]


def read_window(  # noqa: PLR0913 -- the series, the topics and the two outside checks
    histories: Sequence[PairHistory],
    loaded: Sequence[LoadedSeries],
    resolved: Sequence[ResolvedTopic],
    window_start: date,
    *,
    control: ControlBaskets | None = None,
    renames: RenameLog | None = None,
    settings: TrustSettings | None = None,
) -> WindowReading:
    """The verdict of each pair over the window, and the trust in it.

    The control basket and the move log are outside checks: when either fails (the API is
    down, the edition has no top list), the trust goes without it and says so, rather than
    the report failing.
    """
    trust_settings = settings or TrustSettings()
    daily = {
        f"{item.topic_id}/{item.project.language}": list(
            zip(item.main_daily.periods, item.main_daily.values, strict=True)
        )
        for item in loaded
        if item.main_daily is not None and item.main_views is not None
    }
    days = read_day_shares(daily, trust_settings)
    trends = read_trends(
        histories,
        window_start,
        spikes={pair: day.spikes for pair, day in days.items()},
        settings=trust_settings,
    )
    trust = read_trust(
        histories,
        trends,
        controls=_controls(control, histories),
        moves=_moves(renames, resolved),
        days=days,
        settings=trust_settings,
    )
    return WindowReading(trends=trends, trust=trust)


def _controls(
    control: ControlBaskets | None, histories: Sequence[PairHistory]
) -> dict[str, ControlSeries]:
    """Each edition's control shares over its months; none where the basket failed."""
    if control is None:
        return {}
    out: dict[str, ControlSeries] = {}
    for history in histories:
        if history.project in out:
            continue
        project = WikiProject(history.language)
        try:
            shares = control.shares(project, history.months, history.edition)
        except UpstreamError:
            continue
        out[history.project] = ControlSeries(history.months, tuple(shares))
    return out


def _moves(renames: RenameLog | None, resolved: Sequence[ResolvedTopic]) -> dict[str, list[date]]:
    """The days each pair's article (or a redirect to it) was moved; none where the log failed."""
    if renames is None:
        return {}
    out: dict[str, list[date]] = {}
    for topic in resolved:
        for bundle in topic.bundles:
            main = bundle.main
            if main is None:
                continue
            try:
                days = renames.moves(bundle.project, main.title, main.redirects)
            except UpstreamError:
                continue
            out[f"{topic.topic_id}/{bundle.project.language}"] = days
    return out
