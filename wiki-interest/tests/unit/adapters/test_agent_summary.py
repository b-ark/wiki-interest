"""Agent summary: short, structured, localised, with a clarification branch."""

from pathlib import Path

import pytest

from fixtures.summaries import example_summary
from wiki_interest.adapters.agent_summary import AgentSummaryRenderer
from wiki_interest.contracts.request import SubstituteSpec
from wiki_interest.contracts.summary import (
    AnalysisSummary,
    CandidateOut,
    Clarification,
    CoverageGapOut,
    CoverageOptionOut,
)
from wiki_interest.errors import RenderError
from wiki_interest.i18n import Translator

MAX_LINES_FOR_TWO_PROJECT_COMPARE = 80
"""About one screen: the answer, its cards, the edition and decision sections, the table."""


def _build(summary: AnalysisSummary) -> str:
    return AgentSummaryRenderer(Translator(summary.request.report.language)).build(summary)


def test_english_summary_has_its_sections_in_order(compare_summary: AnalysisSummary) -> None:
    text = _build(compare_summary)
    positions = [
        text.index(marker)
        for marker in (
            "**Answer:** Interest in intermittent fasting is growing faster",
            "| Attention share, per 1 million edition views (average) | 98.6 | 117.8 |",
            "## Is the topic growing faster or slower than its Wikipedia?",
            "## How robust is this conclusion?",
            "## What this means for the decision",
            "## Also worth knowing",
            "## Caveats",
            "## What can be refined",
            "## Articles analysed",
            "## Files",
        )
    ]
    assert positions == sorted(positions)


def test_summary_is_short_for_two_project_compare(compare_summary: AnalysisSummary) -> None:
    assert len(_build(compare_summary).splitlines()) <= MAX_LINES_FOR_TWO_PROJECT_COMPARE


def test_robustness_lines_and_the_data_line(compare_summary: AnalysisSummary) -> None:
    text = _build(compare_summary)
    assert "| Do the last 3 months confirm the trend? | yes | no, the share is steady |" in text
    assert "- cs.wikipedia: mixed signal. Attention share, last 12 months vs the 12 before" in text
    assert "Data: 24 months of data; bursts do not drive the result." in text
    assert "cs.wikipedia: months missing: 2." in text
    assert "statistically significant (p" not in text


def test_artifacts_are_listed_with_absolute_paths(compare_summary: AnalysisSummary) -> None:
    text = _build(compare_summary)
    assert "- report.pdf: `/runs/fasting-uk-cs/20260922-120000-abcd/report.pdf`" in text
    assert "- intermittent-fasting-uk-trend.png: `/runs/fasting-uk-cs/" in text


def test_bundles_name_the_measured_article_and_its_redirects(
    compare_summary: AnalysisSummary,
) -> None:
    text = _build(compare_summary)
    assert "- **uk.wikipedia**: found — Інтервальне голодування (+1 redirects)\n" in text


def test_findings_and_general_caveats_are_listed(
    compare_summary: AnalysisSummary,
) -> None:
    text = _build(compare_summary)
    assert "- Czech views per million rose +32% year over year; Ukrainian +12%" in text
    # General limitations close the caveats, after the ones specific to the run.
    caveats = text[text.index("## Caveats") :]
    assert caveats.index("Two Czech months") < caveats.index("Wikipedia interest is a signal")


def test_labels_come_from_the_agent_translations_without_a_catalog() -> None:
    translator = Translator("uk")
    translator.override({"summary.answer": "Відповідь", "summary.caveats": "Застереження"})
    text = AgentSummaryRenderer(translator).build(example_summary(language="uk"))
    assert "**Відповідь:**" in text
    assert "## Застереження" in text
    assert "**Answer:**" not in text


def test_rank_summary_includes_ranking_table() -> None:
    text = _build(example_summary(question_type="rank"))
    assert "| # | Topic | Edition | Score | Profile | Reliability | Why |" in text
    assert "| 3 | Post przerywany | pl.wikipedia | 0.22 | insufficient data | low |" in text
    assert "- **pl.wikipedia**: found via search — Post przerywany" in text


def test_clarification_branch_shows_question_and_candidates_only() -> None:
    text = _build(example_summary(with_clarification=True))
    assert "## Clarification needed" in text
    assert '**Which entity do you mean by "intermittent fasting"?**' in text
    assert "1. **intermittent fasting** (Q1666254) — diet · " in text
    assert "3. **Intermittent Fasting (film)** (Q99999999)" in text
    assert "_If the conversation makes clear which meaning the user wants" in text
    assert "## Key numbers" not in text
    assert "## Files" not in text


def test_clarification_without_details_falls_back_to_headline() -> None:
    summary = example_summary(with_clarification=True).model_copy(update={"clarification": None})
    text = _build(summary)
    assert "## Clarification needed" in text
    assert summary.verdict.headline in text


def test_empty_optional_sections_are_skipped() -> None:
    summary = example_summary().model_copy(
        update={
            "limitations": [],
            "general_limitations": [],
            "next_steps": [],
            "resolution": [],
            "reliability": [],
            "assessments": [],
            "decision": None,
            "verdict": example_summary().verdict.model_copy(update={"bullets": []}),
        }
    )
    text = _build(summary)
    for heading in (
        "## Caveats",
        "## What can be refined",
        "## Articles analysed",
        "## Why trust",
        "## Also worth knowing",
        "## What this means",
        "## Is the topic growing",
    ):
        assert heading not in text


def test_render_writes_file_and_is_deterministic(
    compare_summary: AnalysisSummary, tmp_path: Path
) -> None:
    renderer = AgentSummaryRenderer(Translator("en"))
    first = renderer.render(compare_summary, [], tmp_path / "a" / "summary.md")
    second = renderer.render(compare_summary, [], tmp_path / "b" / "summary.md")
    assert first.read_bytes() == second.read_bytes()
    assert b"\r\n" not in first.read_bytes()


def test_unwritable_output_raises_render_error(
    compare_summary: AnalysisSummary, tmp_path: Path
) -> None:
    blocker = tmp_path / "summary.md"
    blocker.mkdir()
    with pytest.raises(RenderError):
        AgentSummaryRenderer(Translator("en")).render(compare_summary, [], blocker)


def test_not_found_bundle_is_reported_honestly() -> None:
    summary = example_summary(question_type="rank")
    topic = summary.resolution[0]
    bundles = [
        b.model_copy(update={"status": "not_found", "articles": []})
        if b.project == "pl.wikipedia"
        else b
        for b in topic.bundles
    ]
    summary = summary.model_copy(
        update={"resolution": [topic.model_copy(update={"bundles": bundles})]}
    )
    text = _build(summary)
    assert "- **pl.wikipedia**: not found" in text


def _coverage_summary() -> AnalysisSummary:
    base = example_summary(with_clarification=True)
    option = CoverageOptionOut(
        number=1,
        kind="broader",
        title="Post",
        views_avg=1502.0,
        description='The broader article "Post": 1,502 views/month.',
        choose={"pl.wikipedia": SubstituteSpec(title="Post", kind="broader")},
    )
    skip = CoverageOptionOut(
        number=2,
        kind="skip",
        description="Leave pl.wikipedia out.",
        choose={"pl.wikipedia": "skip"},
    )
    gap = CoverageGapOut(
        topic_id="if",
        query="post przerywany",
        project="pl.wikipedia",
        topic_note='The topic is "intermittent fasting" (Q1666254).',
        terms=["post przerywany"],
        question='pl.wikipedia has no article on "post przerywany".',
        options=[option, skip],
    )
    clarification = Clarification(
        kind="missing_article",
        topic_id="if",
        query="post przerywany",
        question="Ask the user.",
        gaps=[gap, gap.model_copy(update={"project": "cs.wikipedia"})],
    )
    return base.model_copy(update={"clarification": clarification})


def test_coverage_question_lists_options_then_values_for_the_agent() -> None:
    text = _build(_coverage_summary())
    assert "## Decision needed: no article" in text
    assert text.count('The topic is "intermittent fasting" (Q1666254).') == 1
    assert '1. The broader article "Post": 1,502 views/month.' in text
    assert "2. Leave pl.wikipedia out." in text
    assert "_Ask the user._" in text
    assert (
        '- if · pl.wikipedia · 1: `{"pl.wikipedia": {"title": "Post", "kind": "broader"}}`' in text
    )
    assert '- if · pl.wikipedia · 2: `{"pl.wikipedia": "skip"}`' in text
    assert "## Key numbers" not in text


def test_substitute_bundle_says_what_was_measured() -> None:
    summary = example_summary()
    topic = summary.resolution[0]
    bundles = [
        b.model_copy(
            update={
                "status": "substitute",
                "substitute_kind": "broader",
                "articles": [b.articles[0].model_copy(update={"title": "Půst"})],
            }
        )
        if b.project == "cs.wikipedia"
        else b
        for b in topic.bundles
    ]
    summary = summary.model_copy(
        update={"resolution": [topic.model_copy(update={"bundles": bundles})]}
    )
    text = _build(summary)
    assert '**cs.wikipedia**: no article; measured through the broader article "Půst"' in text


def test_candidates_show_where_they_have_articles() -> None:
    summary = example_summary(with_clarification=True)
    assert summary.clarification is not None
    first, *rest = summary.clarification.candidates
    clarification = summary.clarification.model_copy(
        update={
            "candidates": [first.model_copy(update={"article_projects": ["uk.wikipedia"]}), *rest]
        }
    )
    text = _build(summary.model_copy(update={"clarification": clarification}))
    assert "(Q1666254) — diet · articles in uk.wikipedia" in text
    assert "no article in the requested editions" in text


def test_topic_not_found_asks_for_a_link_only() -> None:
    summary = example_summary(with_clarification=True)
    clarification = Clarification(
        kind="topic_not_found", topic_id="x", query="blorbix", question="Ask for a link."
    )
    summary = summary.model_copy(
        update={
            "clarification": clarification,
            "verdict": summary.verdict.model_copy(update={"headline": "Nothing was found."}),
        }
    )
    text = _build(summary)
    assert "## Topic not found" in text
    assert "Nothing was found." in text
    assert "_Ask for a link._" in text
    assert "Candidates" not in text


def test_topic_line_names_the_entity_and_other_meanings() -> None:
    summary = example_summary()
    topic = summary.resolution[0].model_copy(
        update={
            "qid": "Q925",
            "label": "ртуть",
            "description": "chemical element",
            "alternatives": [CandidateOut(qid="Q308", label="Mercury", description="planet")],
        }
    )
    text = _build(summary.model_copy(update={"resolution": [topic, *summary.resolution[1:]]}))
    assert (
        'Topic: "ртуть" — chemical element (Q925). '
        "Other meanings of this name: Mercury (Q308) — planet." in text
    )
