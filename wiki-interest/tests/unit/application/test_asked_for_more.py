"""When the PDF may take a second page: the user asked to add to the answer."""

from __future__ import annotations

from fixtures.summaries import example_summary
from wiki_interest.application.pipeline import asked_for_more
from wiki_interest.contracts.summary import AnalysisSummary


def _seasons(summary: AnalysisSummary) -> AnalysisSummary:
    report = summary.request.report.model_copy(update={"seasonality": "show"})
    request = summary.request.model_copy(update={"report": report})
    return summary.model_copy(update={"request": request})


def test_a_first_answer_keeps_to_one_page() -> None:
    assert not asked_for_more(example_summary(), None)


def test_a_question_about_timing_adds_the_season() -> None:
    assert asked_for_more(_seasons(example_summary()), None)


def test_a_follow_up_that_adds_a_wikipedia_may_grow() -> None:
    now = example_summary()
    before = now.model_copy(update={"assessments": now.assessments[:1]})
    assert len(now.assessments) > 1
    assert asked_for_more(now, before)


def test_a_follow_up_that_adds_nothing_keeps_to_one_page() -> None:
    """A longer period or raw views change what is shown, not how much."""
    now = example_summary()
    assert not asked_for_more(now, now)
