"""Use-case: choose which further observations a report mentions beyond its answer.

The answer itself (size, momentum, the topic against its edition) comes from
:mod:`wiki_interest.application.assessment`. This module picks the facts that qualify it:
a step change in the level, dated bursts, a seasonal pattern, editions where the topic was
not measured. The last months against a year earlier are not repeated here: the robustness
line of each audience states them. The detectors in
:mod:`wiki_interest.domain.findings` produce candidates for every (topic, edition) pair; the
strongest few are kept, and the same statement about several editions becomes one line.

Seasonality is always computed but mentioned only when it is material, and drawn only when
the history is long enough to trust it (or when the user asked about timing): three years
give three observations of each month, which can suggest a pattern but not establish one.

The output is language-neutral: a kind (the message key), an importance and the raw
parameters. :mod:`wiki_interest.application.summary_builder` turns it into sentences.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

from wiki_interest.application.analysis import AnalysisResult, PairAnalysis
from wiki_interest.domain.models import WikiProject

__all__ = [
    "Insight",
    "InsightSettings",
    "ParamValue",
    "SeasonVisibility",
    "season_visibility",
    "select_insights",
]

ParamValue = float | int | str | date
_MONTHS_PER_YEAR = 12


@dataclass(frozen=True, slots=True)
class InsightSettings:
    """What is worth saying, and how much of it.

    Attributes:
        max_findings: Findings kept for the report, strongest first.
        max_per_pair: Findings kept per (topic, edition), so one edition cannot crowd out the
            others in a comparison.
        max_bursts_per_pair: Dated bursts named per pair.
        min_seasonality_strength: Share of variation the calendar must explain for a
            seasonal pattern to be mentioned.
        min_seasonal_range: Peak month minus trough month, relative to the usual level.
        season_confident_years: Years of history from which a material pattern is stated as
            a fact rather than as a sign that needs a longer history.
        season_chart_strength: Share of variation the calendar must explain for the pattern
            to get its own chart without being asked for.
    """

    max_findings: int = 5
    max_per_pair: int = 3
    max_bursts_per_pair: int = 1
    min_seasonality_strength: float = 0.3
    min_seasonal_range: float = 0.25
    season_confident_years: int = 5
    season_chart_strength: float = 0.5


_DEFAULT_SETTINGS = InsightSettings()


class SeasonVisibility(StrEnum):
    """How much of a pair's seasonal pattern the report shows."""

    HIDDEN = "hidden"
    TENTATIVE = "tentative"
    """One line: signs of a pattern, a longer history is needed to be sure."""
    STATED = "stated"
    """One line stating the pattern."""
    CHART = "chart"
    """The line and a chart."""


@dataclass(frozen=True, slots=True)
class Insight:
    """One statement for the report, before it is put into words.

    Attributes:
        kind: Message key suffix: ``finding.<kind>``.
        importance: Ranking score in ``[0, 1]``.
        params: Values for the message template; dates, fractions and counts stay raw so the
            builder can format them for the report language.
        topic_id: Topic the statement is about, ``None`` across topics.
        project: Edition it is about, ``None`` across editions.
    """

    kind: str
    importance: float
    params: Mapping[str, ParamValue] = field(default_factory=dict)
    topic_id: str | None = None
    project: WikiProject | None = None
    members: tuple[Insight, ...] = ()
    """For a ``group.*`` insight: the per-edition statements it stands for."""


def season_visibility(
    pair: PairAnalysis,
    settings: InsightSettings = _DEFAULT_SETTINGS,
    *,
    requested: bool = False,
) -> SeasonVisibility:
    """Compute always, show when material and reliable enough, or when the user asked.

    A pattern is material when the calendar explains at least ``min_seasonality_strength``
    of the variation and the peak and trough months are ``min_seasonal_range`` apart. It is
    stated as a fact from ``season_confident_years`` of history, and charted when it is also
    strong. When the user asked about timing, whatever profile exists is shown and charted.
    """
    found = pair.findings
    season, strength = found.seasonality, found.seasonality_strength
    if season is None or strength is None:
        return SeasonVisibility.HIDDEN
    if requested:
        return SeasonVisibility.CHART
    material = (
        strength >= settings.min_seasonality_strength
        and season.peak - season.trough >= settings.min_seasonal_range
    )
    if not material:
        return SeasonVisibility.HIDDEN
    if _years(pair) < settings.season_confident_years:
        return SeasonVisibility.TENTATIVE
    if strength >= settings.season_chart_strength:
        return SeasonVisibility.CHART
    return SeasonVisibility.STATED


def _years(pair: PairAnalysis) -> int:
    """Complete years in the analysed window: how often each calendar month was observed."""
    return len(pair.views.points) // _MONTHS_PER_YEAR if pair.views is not None else 0


def select_insights(
    analysis: AnalysisResult,
    settings: InsightSettings = _DEFAULT_SETTINGS,
    *,
    season_requested: bool = False,
) -> tuple[Insight, ...]:
    """The strongest findings of a run, at most ``max_findings``, strongest first.

    Pairs measured through another subject's article (a broader or mentioning substitute)
    contribute nothing: a burst in "Fasting" says nothing about intermittent fasting. The same
    kind of statement about several editions becomes one grouped line.
    """
    measured = [p for p in analysis.pairs if p.metrics is not None and p.measures_topic]
    # A season the user asked about is kept whatever else competes for the space.
    pinned = _SEASON_KINDS if season_requested else frozenset()
    candidates: list[Insight] = []
    for pair in measured:
        per_pair = sorted(
            _pair_insights(pair, settings, season_requested), key=lambda i: -i.importance
        )
        candidates.extend(per_pair[: settings.max_per_pair])
        candidates.extend(i for i in per_pair[settings.max_per_pair :] if i.kind in pinned)
    candidates = _grouped(candidates)
    candidates.extend(_unmeasured(analysis.pairs))
    candidates.sort(key=lambda i: (i.kind.removeprefix("group.") not in pinned, -i.importance))
    return tuple(candidates[: settings.max_findings])


def _unmeasured(pairs: Sequence[PairAnalysis]) -> list[Insight]:
    """Editions where the topic itself was not measured.

    They rank near the top so that nobody reads a gap as zero interest, or a neighbouring
    article's numbers as the topic's.
    """
    out: list[Insight] = []
    for pair in pairs:
        if pair.metrics is None:
            out.append(Insight("no_article", 0.95, {}, pair.topic_id, pair.project))
        elif not pair.measures_topic and pair.bundle.main is not None:
            kind = pair.bundle.substitute_kind
            params: dict[str, ParamValue] = {
                "title": pair.bundle.main.title,
                "substitute": kind.value if kind is not None else "",
            }
            out.append(Insight("substitute", 0.9, params, pair.topic_id, pair.project))
    return out


_SEASON_KINDS = frozenset({"season", "season_tentative"})
_GROUPS = {
    "season": "season",
    "season_tentative": "season_tentative",
}
"""Per-edition kinds that are merged when several editions share them, and their group."""
_SHARED_PARAMS = ("basis",)
"""Parameters that are the same for every member of a group and stated once."""


def _grouped(insights: Sequence[Insight]) -> list[Insight]:
    groups: dict[tuple[str | None, str], list[Insight]] = {}
    for insight in insights:
        key = _GROUPS.get(insight.kind)
        if key is not None:
            groups.setdefault((insight.topic_id, key), []).append(insight)
    merged: list[Insight] = []
    grouped_ids: set[int] = set()
    for (topic_id, key), members in groups.items():
        if len(members) < 2:  # noqa: PLR2004 -- a group needs two editions
            continue
        grouped_ids.update(id(m) for m in members)
        params: dict[str, ParamValue] = {"count": len(members)}
        for name in _SHARED_PARAMS:
            if name in members[0].params:
                params[name] = members[0].params[name]
        merged.append(
            Insight(
                f"group.{key}",
                max(m.importance for m in members) + 0.05,
                params,
                topic_id,
                members=tuple(members),
            )
        )
    kept = [i for i in insights if id(i) not in grouped_ids]
    return [*kept, *merged]


# -- per pair ---------------------------------------------------------------------------------


def _pair_insights(
    pair: PairAnalysis, settings: InsightSettings, season_requested: bool
) -> list[Insight]:
    found = pair.findings
    out: list[Insight] = []

    def add(kind: str, importance: float, **params: ParamValue) -> None:
        out.append(Insight(kind, min(1.0, importance), params, pair.topic_id, pair.project))

    shift = found.level_shift
    if shift is not None:
        add(
            "level_shift",
            0.7 + min(0.3, abs(shift.change) / 2),
            start_month=shift.start,
            change=shift.change,
            before=shift.before,
            after=shift.after,
            months=shift.months_after,
            unit="per_million" if pair.per_million is not None else "views",
        )
    for burst in found.anomalies[: settings.max_bursts_per_pair]:
        kind = "burst_day" if burst.start == burst.end else "burst"
        add(
            kind,
            0.4 + min(0.4, burst.share * 2),
            start=burst.start,
            end=burst.end,
            peak_day=burst.peak_day,
            peak_views=burst.peak_views,
            baseline=burst.baseline,
            multiple=burst.multiple,
            share=burst.share,
        )
    visibility = season_visibility(pair, settings, requested=season_requested)
    season = found.seasonality
    if visibility is not SeasonVisibility.HIDDEN and season is not None:
        spread = season.peak - season.trough
        # Asked-for patterns are shown however short the history, but still with the caveat.
        if _years(pair) < settings.season_confident_years:
            kind, importance = "season_tentative", 0.3
        else:
            kind, importance = "season", 0.4 + min(0.3, spread / 3)
        add(
            kind,
            importance,
            peak_month=season.peak_month,
            peak=season.peak,
            trough_month=season.trough_month,
            trough=season.trough,
        )
    return out
