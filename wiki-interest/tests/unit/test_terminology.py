"""Every number and every word of change in the generated text names its metric.

The reports use three metrics (article views, edition traffic, attention share). A bare
"-17 %" or "падение" leaves the reader guessing which one moved, which is how "smallest fall:
ru (-17 %)" once read as a fall in readers when it was a fall in the share. These tests render
real summaries (fake Wikimedia data, no network) and check every sentence.
"""

# ruff: noqa: RUF001  -- Cyrillic patterns and the minus sign are intentional.

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fakes import astronomy_world, fake_container
from wiki_interest.adapters.agent_summary import AgentSummaryRenderer
from wiki_interest.adapters.markdown_report import MarkdownReportRenderer
from wiki_interest.application.analysis import analyse
from wiki_interest.application.summary_builder import ProvenanceInput, RunContext, SummaryBuilder
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.contracts.summary import AnalysisSummary
from wiki_interest.i18n import Translator

METRIC = {
    "en": re.compile(r"(?i)attention share|article views|edition traffic"),
    "ru": re.compile(r"(?i)дол[а-яё]* внимания|просмотр[а-яё]* стат|трафик[а-яё]* раздела"),
    "uk": re.compile(
        r"(?i)частк[а-яіїєґ]* уваги|перегляд[а-яіїєґ]* статт|трафік[а-яіїєґ]* розділу"
    ),
}
CHANGE_WORD = {
    "en": re.compile(r"(?i)\bchange|\bfall|\bdeclin|\bgrowth\b"),
    "ru": re.compile(r"(?i)изменени|падени|рост"),
    "uk": re.compile(r"(?i)змін|падінн|зрост"),
}
PERCENT = re.compile(r"[+\-−]\s?\d[\d\s.,]*\s?%")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZА-ЯЁІЇЄҐ])")
MISSING_ARTICLE = re.compile(r"(?i)no article|нет статьи|немає статті")


def _summaries(tmp_path: Path, language: str) -> list[AnalysisSummary]:
    out: list[AnalysisSummary] = []
    for overrides in (
        {},
        {"question_type": "assess", "projects": ["uk"]},
        {"question_type": "rank"},
        {"normalization": "absolute"},
    ):
        data: dict[str, object] = {
            "question_type": "compare",
            "topics": [{"query": "astronomy", "query_language": "en", "id": "astronomy"}],
            "projects": ["uk", "cs", "pl"],
            "period": {"start": "2024-09", "end": "2026-08"},
            "report": {"language": language},
            **overrides,
        }
        request = AnalysisRequest.model_validate(data)
        run_dir = tmp_path / f"run-{len(out)}"
        container = fake_container(astronomy_world(), run_dir)
        assert request.period is not None
        resolved = container.resolver().resolve_request(request)
        loaded = container.loader(request).load(resolved, request.period)
        analysis = analyse(
            resolved,
            loaded,
            weights=request.ranking_weights.to_domain(),
            settings=container.analysis_settings(request),
        )
        context = RunContext("run", None, run_dir, datetime(2026, 9, 22, tzinfo=UTC))
        builder = SummaryBuilder(Translator(language), context, ProvenanceInput("0", "ua", ()))
        out.append(
            builder.build(
                request=request, period=request.period, resolved=resolved, analysis=analysis
            )
        )
    return out


def _sentences(summary: AnalysisSummary, tmp_path: Path) -> list[str]:
    translator = Translator(summary.request.report.language)
    documents = [
        AgentSummaryRenderer(translator).build(summary),
        MarkdownReportRenderer(translator).build(summary, [], tmp_path),
    ]
    sentences: list[str] = []
    for document in documents:
        for line in document.splitlines():
            if line.startswith(("|", "#")) or "`" in line:  # tables: by headers; paths skipped
                continue
            sentences.extend(SENTENCE_END.split(line))
    return sentences


@pytest.mark.parametrize("language", ["en", "ru", "uk"])
def test_every_percentage_names_its_metric(tmp_path: Path, language: str) -> None:
    bare = [
        s
        for summary in _summaries(tmp_path, language)
        for s in _sentences(summary, tmp_path)
        if PERCENT.search(s) and not METRIC[language].search(s)
    ]
    # Reliability reasons ("spike days account for 3 % of views") and data lines are about
    # the data, not a change; they carry no sign.
    assert bare == [], bare


@pytest.mark.parametrize("language", ["en", "ru", "uk"])
def test_no_change_word_without_its_metric(tmp_path: Path, language: str) -> None:
    bare = [
        s
        for summary in _summaries(tmp_path, language)
        for s in _sentences(summary, tmp_path)
        if CHANGE_WORD[language].search(s)
        and not METRIC[language].search(s)
        and not MISSING_ARTICLE.search(s)
    ]
    assert bare == [], bare


@pytest.mark.parametrize("language", ["en", "ru", "uk"])
def test_table_headers_name_their_metric(tmp_path: Path, language: str) -> None:
    for summary in _summaries(tmp_path, language):
        text = MarkdownReportRenderer(Translator(language)).build(summary, [], tmp_path)
        for line in text.splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if line.startswith("|") and any(PERCENT.search(c) for c in cells):
                continue  # a data row; its column header or first cell is checked below
            if line.startswith("|") and CHANGE_WORD[language].search(line):
                changed = [c for c in cells if CHANGE_WORD[language].search(c)]
                assert all(METRIC[language].search(c) for c in changed), changed


@pytest.mark.parametrize("language", ["en", "ru", "uk"])
def test_no_text_assumes_a_direction(tmp_path: Path, language: str) -> None:
    """ "Growth is not spike-driven" was printed under a falling trend."""
    tied = re.compile(r"(?i)growth is not|рост не вызван|зростання не спричинене")
    for summary in _summaries(tmp_path, language):
        assert not [s for s in _sentences(summary, tmp_path) if tied.search(s)]
