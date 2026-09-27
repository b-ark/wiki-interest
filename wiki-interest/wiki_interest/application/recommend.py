"""Use-case: the recommendation, with every field computed from the window's verdicts.

- ``choice``: the edition (or, in one edition, the topic) with the strongest verdict
  (growing, then stable, then declining), then the higher trust, then the larger audience;
  it is named even when none grows ("if you must pick one"), and ``none_growing`` says so.
  The line says which of the three decided and, when the choice is not the largest audience,
  where the largest is: a growing audience ten times smaller beats a stable one, which is
  right for "where to invest next", but the chart of views shows the loser's tall bars.
- ``why``: each candidate's verdict with its trend line's levels and slope over the window.
- ``confidence``: the trust in the chosen verdict.
- ``next_check``: what the skill can check next on its own: neighbouring articles, else more
  language editions; a check outside Wikipedia only when neither is left.

The lines the report prints are composed at render time from these fields, in the report's
language; the agent's text explains the choice and never makes another.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from wiki_interest.application.related import Related
from wiki_interest.application.window import (
    edition_nominative,
    signed_percent,
    verdict_phrase,
)
from wiki_interest.contracts.summary import (
    NextCheckOut,
    NextItemOut,
    RecommendationOut,
    TrendOut,
)
from wiki_interest.domain.observations import Observation, Quoted, Weight, edition_name
from wiki_interest.domain.trust import TrendVerdict
from wiki_interest.i18n import Translator

__all__ = [
    "recommend",
    "recommendation_lines",
    "recommendation_observation",
]

_VERDICT_RANK = {
    TrendVerdict.GROWING.value: 2,
    TrendVerdict.STABLE.value: 1,
    TrendVerdict.DECLINING.value: 0,
}
_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}


def recommend(
    topic_id: str,
    verdicts: Sequence[TrendOut],
    *,
    related: Sequence[Related] = (),
    more_editions: Sequence[str] = (),
    by_topic: bool = False,
) -> RecommendationOut | None:
    """The recommendation for one topic (or, ``by_topic``, for the topics of one edition).

    Args:
        topic_id: The topic (or the edition, ``by_topic``) it is about.
        verdicts: The candidates' verdicts; substitutes are never chosen.
        related: Neighbouring articles the skill can add next.
        more_editions: Language codes of editions the skill can add next.
        by_topic: Candidates are topics of one edition, not editions of one topic.
    """
    candidates = [v for v in verdicts if not v.substitute and v.verdict in _VERDICT_RANK]
    if not candidates:
        return None
    ranked = sorted(candidates, key=_rank, reverse=True)
    best = ranked[0]
    largest = max(candidates, key=lambda v: v.views_avg or 0.0)
    return RecommendationOut(
        topic_id=topic_id,
        choice=f"{best.topic_id}/{best.project.split('.')[0]}",
        choice_project=best.project,
        choice_label=best.label,
        by_topic=by_topic,
        single=len(candidates) == 1,
        none_growing=all(v.verdict != TrendVerdict.GROWING.value for v in candidates),
        why=[_pair(v) for v in candidates],
        decided_by=_decided_by(best, ranked[1]) if len(ranked) > 1 else None,
        largest=None if largest is best else _pair(largest),
        confidence=best.trust.confidence if best.trust else None,
        next_check=_next_check(best, related, more_editions),
    )


def _rank(v: TrendOut) -> tuple[int, int, float]:
    """The order of the choice: the verdict, then the trust in it, then the audience."""
    return (
        _VERDICT_RANK[v.verdict],
        _CONFIDENCE_RANK.get(v.trust.confidence if v.trust else "low", 0),
        v.views_avg or 0.0,
    )


def _decided_by(best: TrendOut, runner_up: TrendOut) -> Literal["verdict", "trust", "size"]:
    """Which of the three criteria set ``best`` apart from the next best candidate."""
    ours, theirs = _rank(best), _rank(runner_up)
    if ours[0] != theirs[0]:
        return "verdict"
    if ours[1] != theirs[1]:
        return "trust"
    return "size"


def _pair(v: TrendOut) -> str:
    return f"{v.topic_id}/{v.project.split('.')[0]}"


def _next_check(
    best: TrendOut, related: Sequence[Related], more_editions: Sequence[str]
) -> NextCheckOut:
    """Neighbouring articles in the chosen edition, else more editions, else outside."""
    near = [r for r in related if best.project in r.projects] or list(related)
    if near:
        return NextCheckOut(
            kind="related",
            items=[NextItemOut(label=r.label, qid=r.qid) for r in near],
            change='append to topics, one per item: {"id": <short id>, "query": <label>, '
            '"qid": <qid>}; keep projects',
        )
    if more_editions:
        return NextCheckOut(
            kind="editions",
            items=[NextItemOut(label=code, project=f"{code}.wikipedia") for code in more_editions],
            change="append to projects: " + ", ".join(more_editions),
        )
    return NextCheckOut(kind="external", change="none: a check outside Wikipedia")


def recommendation_lines(
    rec: RecommendationOut, verdicts: Sequence[TrendOut], t: Translator
) -> RecommendationOut:
    """``rec`` with its two lines in the report's language: the choice, and the next check."""
    by_pair = {_pair(v): v for v in verdicts}
    facts = [_why(by_pair[pair], t) for pair in rec.why if pair in by_pair]

    def name(pair: str | None, label: str = "") -> str:
        v = by_pair.get(pair or "")
        if v is None:
            return label
        return v.label if rec.by_topic else edition_nominative(v.project, t)

    parts = [t.t("rec.why", parts="; ".join(facts))]
    if rec.none_growing and not rec.single:
        parts.append(t.t("rec.none_growing_topics" if rec.by_topic else "rec.none_growing"))
    if not rec.single:
        parts.append(_pick(rec, name(rec.choice, rec.choice_label), name(rec.largest), t))
    if rec.confidence:
        parts.append(t.t("rec.confidence", level=t.t(f"trust.level.{rec.confidence}")))
    line = t.t("rec.line", text=" ".join(parts))
    return rec.model_copy(update={"line": line, "next_line": _next_line(rec.next_check, t)})


def _pick(rec: RecommendationOut, choice: str, largest: str, t: Translator) -> str:
    """The "if you pick one" sentence: what decided it and, for a smaller choice, the largest."""
    reason = rec.decided_by or "verdict"
    if not largest:
        return t.t(f"rec.pick.{reason}", choice=choice)
    return t.t(f"rec.pick.{reason}_smaller", choice=choice, largest=largest)


def _why(v: TrendOut, t: Translator) -> str:
    phrase = verdict_phrase(v, t)
    if v.level_start is None or v.level_end is None or v.slope_pct_per_year is None:
        return t.t("rec.why_part_none", label=v.label, verdict=phrase)
    return t.t(
        "rec.why_part",
        label=v.label,
        verdict=phrase,
        start=t.number(v.level_start, 1),
        end=t.number(v.level_end, 1),
        slope=signed_percent(v.slope_pct_per_year, t),
    )


def _next_line(check: NextCheckOut | None, t: Translator) -> str:
    if check is None:
        return ""
    if check.kind == "related":
        return t.t("rec.next.related", items=", ".join(i.label for i in check.items))
    if check.kind == "editions":
        names = ", ".join(edition_nominative(i.project or "", t) for i in check.items)
        return t.t("rec.next.editions", items=names)
    return t.t("rec.next.external")


def recommendation_observation(
    rec: RecommendationOut, verdicts: Sequence[TrendOut], topic: str
) -> Observation:
    """The recommendation as an observation the agent's meaning explains (English)."""
    t = Translator("en")
    lines = recommendation_lines(rec, verdicts, t)
    numbers: list[Quoted] = []
    for v in verdicts:
        if f"{v.topic_id}/{v.project.split('.')[0]}" not in rec.why:
            continue
        for value in (v.level_start, v.level_end):
            if value is not None:
                numbers.append(Quoted(value))
        if v.slope_pct_per_year is not None:
            numbers.append(Quoted(v.slope_pct_per_year, percent=True))
    chosen = rec.choice_label if rec.by_topic else edition_name(rec.choice_project or "")
    return Observation(
        id=f"recommendation:{rec.topic_id}",
        kind="recommendation",
        pair=None,
        weight=Weight.DECISION,
        statement=(
            f"The code's recommendation on {topic}: {lines.line} {lines.next_line} "
            f"The meaning explains why {chosen} is the choice and names it; it never picks "
            "another."
        ),
        numbers=tuple(numbers),
    )
