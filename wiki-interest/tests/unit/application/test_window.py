"""The analysis window against the history: context range, verdict lines and the headline."""

# ruff: noqa: RUF001  -- Ukrainian text in the expectations is intentional.

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from wiki_interest.application.window import (
    context_range,
    headline,
    read_trends,
    trend_outs,
)
from wiki_interest.contracts.request import Period
from wiki_interest.domain.observations import PairHistory
from wiki_interest.i18n import Translator

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "v02_veganism.json"
WINDOW = Period(start=date(2024, 9, 1), end=date(2026, 8, 1))


def _reference() -> list[PairHistory]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))["pairs"]
    return [
        PairHistory(
            topic_id="veganism",
            topic="веганство",
            project=project,
            months=tuple(date(int(m[:4]), int(m[5:]), 1) for m in pair["months"]),
            views=tuple(pair["views"]),
            edition=tuple(pair["edition"]),
        )
        for project, pair in data.items()
    ]


def test_the_context_starts_at_the_first_january_of_the_history() -> None:
    assert context_range(WINDOW, date(2020, 9, 1)) == Period(
        start=date(2021, 1, 1), end=date(2026, 8, 1)
    )
    # A window that starts earlier starts the context too.
    early = Period(start=date(2019, 3, 1), end=date(2026, 8, 1))
    assert context_range(early, date(2020, 9, 1)).start == date(2019, 3, 1)


def test_the_reference_headline_and_lines_read_the_window_alone() -> None:
    """ru is stable in the window after a drop, cs keeps falling: never "falling in both"."""
    t = Translator("uk")
    trends = read_trends(_reference(), WINDOW.start)
    items = trend_outs(trends, {"veganism/ru": "ru", "veganism/cs": "cs"}, t)
    assert [(v.label, v.verdict) for v in items] == [("ru", "stable"), ("cs", "declining")]
    text = headline("веганство", items, t)
    assert text == (
        "Веганство: у російській Вікіпедії інтерес стабілізувався після спаду; "
        "у чеській Вікіпедії інтерес продовжує падати."
    )
    ru, cs = items
    assert ru.line.startswith("ru: інтерес стабілізувався після спаду. Частка уваги з 2024-12:")
    assert cs.line.startswith("cs: інтерес продовжує падати. Частка уваги з 2025-05:")
    assert "−" in cs.line  # the slope is written with the minus sign


def test_a_substitute_is_left_out_of_the_headline() -> None:
    t = Translator("en")
    trends = read_trends(_reference(), WINDOW.start)
    items = trend_outs(trends, {}, t, substitutes={"veganism/cs"})
    text = headline("veganism", items, t)
    assert text is not None
    assert "Czech" not in text
