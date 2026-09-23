"""The agent writes the report text; the code checks it against the facts and renders it.

Runs use the fake world (no network): ``astronomy`` in uk.wikipedia (37.9 per million,
+21 %) and cs.wikipedia. The template text the code writes must pass its own checks in every
language; each broken variant must be rejected with a problem the agent can act on. Only
English has a catalog: in any other language the template is English with that language's
numbers, and the agent must also translate the interface labels (``facts.template.ui``).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pypdf import PdfReader

from fakes import AstronomyWorld, astronomy_world, fake_container
from wiki_interest.application.narrative_check import check_narrative
from wiki_interest.application.pipeline import Pipeline
from wiki_interest.application.summary_builder import RunContext
from wiki_interest.contracts.narrative import Facts, Narrative, PairText
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.domain.models import Access, Agent, Granularity, WikiProject
from wiki_interest.i18n import CATALOGS

TOPIC = {"query": "astronomy", "query_language": "en", "id": "astronomy"}


def _run(
    tmp_path: Path,
    language: str,
    overrides: Mapping[str, object] | None = None,
    *,
    run_id: str = "r1",
    world: AstronomyWorld | None = None,
) -> tuple[Pipeline, Path]:
    data: dict[str, object] = {
        "question_type": "compare",
        "topics": [TOPIC],
        "projects": ["uk", "cs"],
        "period": {"start": "2024-09", "end": "2026-08"},
        "report": {"language": language},
        "session": "astro",
        **(overrides or {}),
    }
    pipeline = fake_container(world or astronomy_world(), tmp_path).pipeline()
    run_dir = tmp_path / "runs" / "astro" / run_id
    context = RunContext(run_id, "astro", run_dir, datetime(2026, 9, 22, tzinfo=UTC))
    outcome = pipeline.run(AnalysisRequest.model_validate(data), context)
    assert outcome.summary.status == "ok"
    return pipeline, run_dir


def _facts(run_dir: Path) -> Facts:
    return Facts.model_validate_json((run_dir / "facts.json").read_text(encoding="utf-8"))


def _template(run_dir: Path) -> Narrative:
    return _facts(run_dir).template


def _messages(facts: Facts, narrative: Narrative) -> list[str]:
    return [f"{p.block}: {p.message}" for p in check_narrative(facts, narrative)]


def _with_ui(facts: Facts, narrative: Narrative) -> Narrative:
    """``narrative`` with every label of ``facts.template.ui`` answered (kept in English)."""
    return narrative.model_copy(update={"ui": dict(facts.template.ui)})


def _russian(facts: Facts, template: Narrative) -> Narrative:
    """A text in the agent's own words, with its own term for the share and the labels."""
    return _with_ui(facts, template).model_copy(
        update={
            "glossary": {
                "attention_share": "доля просмотров",
                "article_views": "просмотры статьи",
                "edition_traffic": "трафик раздела",
            },
            "headline": "Интерес к астрономии растёт в украинской Википедии.",
            "happening": [
                "Доля просмотров темы: uk.wikipedia 37,9 на миллион, cs.wikipedia 40,0.",
                "Доля просмотров в uk.wikipedia за последние 12 месяцев выросла на 21 %.",
            ],
        }
    )


class TestFacts:
    def test_run_writes_facts_and_template_with_numbers_metrics_and_caveats(
        self, tmp_path: Path
    ) -> None:
        _, run_dir = _run(tmp_path, "ru")
        facts = _facts(run_dir)
        assert facts.language == "ru"
        uk = next(p for p in facts.pairs if p.id == "astronomy/uk")
        share = next(n for n in uk.numbers if n.id == "astronomy/uk.per_million")
        assert (share.metric, share.value, share.display) == ("attention_share", 37.9, "37,9")
        change = next(n for n in uk.numbers if n.id == "astronomy/uk.change")
        assert change.unit == "fraction"
        assert change.display.startswith("+21")
        assert uk.states["momentum"] == "growing"
        assert {c.id for c in facts.caveats} >= {"curiosity_not_demand", "coverage_differs"}
        assert facts.template.ui  # no Russian catalog: the agent translates the labels
        assert facts.template.language == "ru"
        assert not (run_dir / "narrative.template.json").exists()  # one file to read

    def test_english_needs_no_interface_labels(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "en")
        assert _facts(run_dir).template.ui == {}

    @pytest.mark.parametrize("language", ["ru", "de"])
    def test_language_without_a_catalog_asks_for_the_interface_labels(
        self, tmp_path: Path, language: str
    ) -> None:
        _, run_dir = _run(tmp_path, language)
        ui = _facts(run_dir).template.ui
        # A section heading of the PDF, as the English template the agent translates.
        assert ui["report.decision"] == CATALOGS["en"]["report.decision"]
        # The chat answer's labels are translated with the report's.
        assert ui["chat.pdf"] == CATALOGS["en"]["chat.pdf"]
        assert "chart.no_data" not in ui or ui["chart.no_data"]


def _spiky_world(month_index: int = 20) -> AstronomyWorld:
    """uk.wikipedia's article at 2.5 times its level in one month, through mobile web alone."""
    world = astronomy_world()
    uk = WikiProject("uk")
    key = (uk.domain, "Астрономія", Granularity.MONTHLY, Agent.USER, Access.ALL)
    base = dict(world.pageviews.articles[key])
    month = world.months[month_index]
    world.pageviews.articles[key][month] = base[month] * 2.5
    shares = {Access.DESKTOP: 0.3, Access.MOBILE_WEB: 0.65, Access.MOBILE_APP: 0.05}
    for access, share in shares.items():
        values = {m: v * share for m, v in base.items()}
        if access is Access.MOBILE_WEB:
            values[month] = base[month] * (2.5 - 0.35)
        world.pageviews.set_article(uk, "Астрономія", values, access=access)
    return world


class TestAnalysisFacts:
    def test_states_split_data_quality_from_the_conclusion(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "en")
        uk = next(p for p in _facts(run_dir).pairs if p.id == "astronomy/uk")
        assert uk.states["recent_confirmation"] in {
            "confirmed",
            "mixed",
            "contradicts",
            "insufficient",
        }
        assert "robustness" not in uk.states
        assert uk.states["data_quality"] in {"high", "medium", "low"}
        assert uk.season is not None
        assert not uk.season.shown  # two years of history are too short
        assert uk.season.reason == "short_history"

    def test_a_month_in_the_change_is_a_fact_with_its_cause_and_a_caveat(
        self, tmp_path: Path
    ) -> None:
        world = _spiky_world()
        month = f"{world.months[20]:%Y-%m}"
        _, run_dir = _run(tmp_path, "en", world=world)
        facts = _facts(run_dir)
        uk = next(p for p in facts.pairs if p.id == "astronomy/uk")
        (anomaly,) = uk.anomalies
        assert (anomaly.month, anomaly.nature, anomaly.in_change) == (
            month,
            "possible_bot",
            True,
        )
        numbers = {n.id: n for n in uk.numbers}
        views = numbers[f"astronomy/uk.month.{month}.article_views"]
        assert views.unit == "multiple"
        assert views.display.startswith("×")
        without = numbers[f"astronomy/uk.month.{month}.change_without"]
        assert without.value < numbers["astronomy/uk.change"].value
        caveat = next(c for c in facts.caveats if c.id == "months:astronomy/uk")
        assert month in caveat.meaning
        # The template does not describe the month, so the agent has to.
        uncovered = "Cover caveat 'months:astronomy/uk'"
        messages = _messages(facts, _template(run_dir))
        assert any(uncovered in m for m in messages)
        # A text written against the per-month ids of earlier versions still covers it.
        old_id = _template(run_dir).model_copy(
            update={"covered_caveats": [f"month:astronomy/uk:{month}"]}
        )
        assert not any(uncovered in m for m in _messages(facts, old_id))


class TestChatBrief:
    def test_follow_ups_say_which_reruns_are_instant(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "en")
        follow_ups = {f.id: f for f in _facts(run_dir).follow_ups}
        assert follow_ups["seasons"].cached
        assert follow_ups["raw_views"].cached
        assert not follow_ups["add_editions"].cached
        assert not follow_ups["longer_period"].cached
        assert "appendix" in follow_ups["method_page"].change

    def test_a_caveat_of_an_edition_names_it(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "en", world=_spiky_world())
        facts, template = _facts(run_dir), _template(run_dir)
        declared = template.model_copy(
            update={"covered_caveats": [*template.covered_caveats, "months:astronomy/uk"]}
        )
        assert not any("Cover caveat" in m for m in _messages(facts, declared))
        unnamed = declared.model_copy(update={"caveats": ["Views show curiosity."]})
        assert any("must name uk.wikipedia" in m for m in _messages(facts, unnamed))

    def test_the_run_writes_the_method_next_to_the_report(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "ru")
        method = (run_dir / "method.md").read_text(encoding="utf-8")
        assert method.startswith("# Method")
        assert "Trend test (Mann-Kendall" in method
        assert "- season_min_years: 5" in method
        assert "uk.wikipedia" in method


class TestTemplatePassesItsOwnChecks:
    """Once the agent answered the labels, the template must pass: the code's own text never
    trips the checks, whatever the language of the numbers and the word lists."""

    @pytest.mark.parametrize("language", ["en", "ru", "uk", "de"])
    @pytest.mark.parametrize(
        "overrides",
        [
            {},
            {"question_type": "assess", "projects": ["uk"]},
            {"question_type": "rank"},
            {"normalization": "absolute"},
        ],
        ids=["compare", "assess", "rank", "absolute"],
    )
    def test_template(self, tmp_path: Path, language: str, overrides: dict[str, object]) -> None:
        _, run_dir = _run(tmp_path, language, overrides)
        facts = _facts(run_dir)
        assert _messages(facts, _with_ui(facts, _template(run_dir))) == []

    def test_template_of_two_topics(self, tmp_path: Path) -> None:
        topics = [TOPIC, {"query": "telescope", "query_language": "en", "id": "telescope"}]
        _, run_dir = _run(tmp_path, "uk", {"topics": topics})
        facts = _facts(run_dir)
        assert _messages(facts, _with_ui(facts, _template(run_dir))) == []


class TestRejections:
    @pytest.fixture
    def ru(self, tmp_path: Path) -> tuple[Facts, Narrative]:
        _, run_dir = _run(tmp_path, "ru")
        facts = _facts(run_dir)
        return facts, _russian(facts, _template(run_dir))

    def test_own_words_and_own_glossary_pass(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        assert _messages(facts, narrative) == []

    @pytest.mark.parametrize(
        ("sentence", "expected"),
        [
            ("Доля просмотров выросла на 57 %.", "57 % is not in facts.json"),
            ("uk.wikipedia: +21 % за год.", "needs its metric"),  # a share or article views
            ("Спрос на астрономию растёт, доля просмотров +21 %.", "not demand"),
            ("Рост доли просмотров +21 % статистически значим.", "No statistical jargon"),
            ("Это 1 из 26 000 просмотров.", "1 in N"),
        ],
    )
    def test_happening(self, ru: tuple[Facts, Narrative], sentence: str, expected: str) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(update={"happening": [*narrative.happening, sentence]})
        assert any(expected in m for m in _messages(facts, broken)), _messages(facts, broken)

    @pytest.mark.parametrize(
        "text",
        [
            "uk.wikipedia 37,9 на миллион просмотров раздела.",
            "Доля просмотров за 12 месяцев:\n- uk.wikipedia: +21 %",
            "Просмотры в uk.wikipedia: 37,9 на миллион.",
            "Долю видно по окну в 24 месяца: uk.wikipedia 37,9 на миллион.",
        ],
    )
    def test_a_metric_named_by_its_own_word_or_per_million_passes(
        self, ru: tuple[Facts, Narrative], text: str
    ) -> None:
        facts, narrative = ru
        extended = narrative.model_copy(update={"happening": [*narrative.happening, text]})
        assert _messages(facts, extended) == []

    @pytest.mark.parametrize(
        "text",
        [
            "Просмотры статьи в uk.wikipedia: 37,9.",
            "- uk.wikipedia: +21 %",
            "Трафик раздела uk.wikipedia за 12 месяцев: +21 %.",
        ],
    )
    def test_a_number_several_metrics_share_or_under_another_metric_is_rejected(
        self, ru: tuple[Facts, Narrative], text: str
    ) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(update={"happening": [*narrative.happening, text]})
        messages = _messages(facts, broken)
        assert any("write it as 'доля просмотров" in m for m in messages), messages

    def test_a_number_only_one_metric_has_may_go_without_its_name(
        self, ru: tuple[Facts, Narrative]
    ) -> None:
        facts, narrative = ru
        bare = narrative.model_copy(
            update={"happening": [*narrative.happening, "uk.wikipedia: 37,9."]}
        )
        assert _messages(facts, bare) == []

    def test_characters_of_another_script_are_rejected(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(
            update={"decision": [*narrative.decision, "Учитывайте 季节性 интереса."]}
        )
        assert any("another script" in m for m in _messages(facts, broken))

    def test_headline_is_one_sentence_without_numbers(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(update={"headline": "Рост 21 %. Всё хорошо."})
        messages = _messages(facts, broken)
        assert any("no numbers" in m for m in messages)
        assert any("one sentence" in m for m in messages)

    def test_every_measured_pair_has_its_robustness_text(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(update={"robustness": narrative.robustness[:1]})
        assert any("astronomy/cs" in m for m in _messages(facts, broken))

    def test_robustness_names_its_edition_and_quotes_only_its_numbers(
        self, ru: tuple[Facts, Narrative]
    ) -> None:
        facts, narrative = ru
        cs_share = next(
            n.display
            for p in facts.pairs
            if p.id == "astronomy/cs"
            for n in p.numbers
            if n.id.endswith(".per_million")
        )
        wrong = PairText(pair="astronomy/uk", text=f"Украина: доля просмотров {cs_share}.")
        broken = narrative.model_copy(update={"robustness": [wrong, *narrative.robustness[1:]]})
        messages = _messages(facts, broken)
        assert any("uk.wikipedia" in m for m in messages)
        assert any(f"{cs_share} is not in facts.json" in m for m in messages)

    def test_every_caveat_is_declared(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(update={"covered_caveats": ["curiosity_not_demand"]})
        assert any("coverage_differs" in m for m in _messages(facts, broken))

    def test_language_and_glossary(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(update={"language": "en", "glossary": {}})
        messages = _messages(facts, broken)
        assert any("Write in 'ru'" in m for m in messages)
        assert any("missing: attention_share" in m for m in messages)

    def test_interface_labels_keep_their_placeholders(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "de")
        facts, narrative = _facts(run_dir), _template(run_dir)
        # The template carries every label to translate; one left out stays English.
        assert narrative.ui
        untranslated = narrative.model_copy(update={"ui": {}})
        assert not any(p.block == "ui" for p in check_narrative(facts, untranslated))
        ui = {key: f"DE {text}" for key, text in narrative.ui.items()}
        with_ui = narrative.model_copy(update={"ui": ui})
        assert _messages(facts, with_ui) == []
        key = next(k for k, v in narrative.ui.items() if "{" in v)
        bad = with_ui.model_copy(update={"ui": {**ui, key: "ohne Platzhalter"}})
        assert any("placeholders" in m for m in _messages(facts, bad))


class TestNarrate:
    def test_accepted_text_goes_into_the_reports_and_the_chat_brief(self, tmp_path: Path) -> None:
        pipeline, run_dir = _run(tmp_path, "ru")
        narrative = _russian(_facts(run_dir), _template(run_dir))
        outcome = pipeline.narrate(run_dir, narrative)
        assert outcome.status == "accepted"
        assert outcome.exit_code == 0
        assert outcome.summary.narrative_source == "agent"
        report = (run_dir / "summary.md").read_text(encoding="utf-8")
        assert narrative.headline in report
        assert "37,9 на миллион" in report
        assert "21\u202f%" in report  # the typed space before % no longer breaks the line
        pdf = "".join(page.extract_text() for page in PdfReader(run_dir / "report.pdf").pages)
        assert "украинской" in pdf
        # The chat answer is laid out from the accepted blocks, with next steps and the PDF.
        brief = (run_dir / "chat_brief.md").read_text(encoding="utf-8").strip()
        assert narrative.headline in brief
        assert "37,9 на миллион" in brief
        assert all(item in brief for item in narrative.caveats)
        assert "(instant: the data are already loaded)" in brief
        assert brief.endswith("report.pdf")
        payload = outcome.to_dict()
        assert payload["chat_answer"] == brief
        saved = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        assert saved["narrative_source"] == "agent"

    def test_one_rejection_then_the_template_stays(self, tmp_path: Path) -> None:
        pipeline, run_dir = _run(tmp_path, "ru")
        template_report = (run_dir / "summary.md").read_text(encoding="utf-8")
        broken = _template(run_dir).model_copy(update={"headline": "Рост 21 %."})
        first = pipeline.narrate(run_dir, broken)
        assert (first.status, first.exit_code) == ("rejected", 2)
        assert first.to_dict()["problems"]
        second = pipeline.narrate(run_dir, broken)
        assert (second.status, second.exit_code) == ("fallback", 0)
        assert "summary_md" in str(second.to_dict()["hint"])
        assert (run_dir / "summary.md").read_text(encoding="utf-8") == template_report

    def test_interface_translations_are_kept_for_the_session(self, tmp_path: Path) -> None:
        pipeline, run_dir = _run(tmp_path, "de")
        facts = _facts(run_dir)
        ui = {key: f"DE {text}" for key, text in facts.template.ui.items()}
        narrative = facts.template.model_copy(update={"ui": ui})
        assert pipeline.narrate(run_dir, narrative).status == "accepted"
        assert "DE " in (run_dir / "summary.md").read_text(encoding="utf-8")
        assert "DE PDF report" in (run_dir / "chat_brief.md").read_text(encoding="utf-8")
        cache = run_dir.parent / "ui-de.json"
        assert json.loads(cache.read_text(encoding="utf-8")) == ui
        # The next run of the session renders with them and asks only for new labels.
        _, next_dir = _run(tmp_path, "de", run_id="r2")
        assert "DE " in (next_dir / "summary.md").read_text(encoding="utf-8")
        assert not set(_facts(next_dir).template.ui) & set(ui)
