"""The agent writes the report text from the observations; the code checks it and renders it.

Runs use the fake world (no network): ``astronomy`` in uk.wikipedia (+21 % over the last
year against a flat edition) and cs.wikipedia (flat). The template text the code writes must
pass its own checks in every language; each broken variant must be rejected with a problem
the agent can act on. Only English has a catalog: in any other language the template is
English, and the agent must also translate the interface labels (``facts.ui``).
"""

# ruff: noqa: RUF001  -- Russian text in the fixtures is intentional.

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pypdf import PdfReader

from fakes import AstronomyWorld, astronomy_world, fake_container
from wiki_interest.application.facts import template_narrative
from wiki_interest.application.narrative_check import check_narrative
from wiki_interest.application.pipeline import Pipeline
from wiki_interest.application.runs import load_summary
from wiki_interest.application.summary_builder import RunContext
from wiki_interest.contracts.narrative import Facts, Narrative, Paragraph
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.contracts.summary import ObservationOut
from wiki_interest.i18n import CATALOGS, Translator

TOPIC = {"query": "astronomy", "query_language": "en", "id": "astronomy"}
VS_UK = "vs_edition:astronomy/uk"
EDITIONS = "editions:astronomy"
VERDICT_UK = "decision:verdict:astronomy/uk"
START_WITH = "decision:editions:astronomy"


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
    """The code's own text for the run, with the labels still to translate."""
    summary = load_summary(run_dir)
    translator = Translator(summary.request.report.language)
    return template_narrative(summary, translator, ui=_facts(run_dir).ui)


def _messages(facts: Facts, narrative: Narrative) -> list[str]:
    return [f"{p.block}: {p.message}" for p in check_narrative(facts, narrative)]


def _with_ui(facts: Facts, narrative: Narrative) -> Narrative:
    """``narrative`` with every label of ``facts.ui`` answered (kept in English)."""
    return narrative.model_copy(update={"ui": dict(facts.ui)})


def _russian(facts: Facts) -> Narrative:
    """A text in the agent's own words that explains the observations it cites."""
    return _with_ui(
        facts,
        Narrative(
            language="ru",
            topic="Астрономия — наука о небесных телах (Q333).",
            headline="Интерес к астрономии растёт в украинской Википедии, в чешской он ровный.",
            story=[
                Paragraph(
                    text=(
                        "В украинской Википедии статью открывают около 4 200 раз в месяц. "
                        "За последний год её доля в чтении раздела выросла на 21 %, хотя сам "
                        "раздел читают столько же: тема набирает внимание сама."
                    ),
                    uses=["size:astronomy/uk", VS_UK],
                ),
                Paragraph(
                    text=(
                        "С поправкой на размер раздела интерес в обеих Википедиях примерно "
                        "одинаковый, но украинская аудитория больше: около 4 200 просмотров "
                        "в месяц против 2 000."
                    ),
                    uses=[EDITIONS],
                ),
            ],
            meaning=Paragraph(
                text="Википедия поддерживает идею; начинать логично с украинской аудитории.",
                uses=[VERDICT_UK, START_WITH],
            ),
            check="Проверьте, как часто ищут курсы астрономии, и запустите небольшой тест.",
            limits="Просмотры показывают любопытство, а не готовность платить; раздел — это "
            "язык, а не страна.",
        ),
    )


class TestFacts:
    def test_run_writes_observations_rules_example_and_template(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "ru")
        facts = _facts(run_dir)
        assert facts.schema_version == "3"
        assert facts.language == "ru"
        observations = {o.id: o for o in facts.observations}
        vs = observations[VS_UK]
        assert vs.weight == "high"
        assert "+21 %" in vs.statement
        assert any(q.value == 21 and q.percent for q in vs.numbers)
        assert observations[START_WITH].weight == "decision"
        assert facts.rules
        assert facts.example["narrative"]["story"][0]["uses"]
        assert facts.ui  # no Russian catalog: the agent translates the labels
        # The code's own text is not shown: the agent retold it instead of explaining.
        assert "template" not in json.loads((run_dir / "facts.json").read_text(encoding="utf-8"))
        assert not (run_dir / "narrative.template.json").exists()  # one file to read

    @pytest.mark.parametrize(("language", "label"), [("uk", "астрономія"), ("en", "astronomy")])
    def test_the_topic_is_named_in_the_report_language(
        self, tmp_path: Path, language: str, label: str
    ) -> None:
        """The topic was searched in English; the report names it as its reader would."""
        _, run_dir = _run(tmp_path, language)
        assert _facts(run_dir).topics[0].startswith(f"astronomy: {label} (Q333)")

    def test_english_needs_no_interface_labels(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "en")
        assert _facts(run_dir).ui == {}

    @pytest.mark.parametrize("language", ["ru", "de"])
    def test_language_without_a_catalog_asks_for_the_interface_labels(
        self, tmp_path: Path, language: str
    ) -> None:
        _, run_dir = _run(tmp_path, language)
        ui = _facts(run_dir).ui
        # A section heading of the PDF, as the English template the agent translates.
        assert ui["report.decision"] == CATALOGS["en"]["report.decision"]
        # The chat answer's labels are translated with the report's.
        assert ui["chat.pdf"] == CATALOGS["en"]["chat.pdf"]

    def test_the_report_shows_the_template_story_before_the_agent_writes(
        self, tmp_path: Path
    ) -> None:
        _, run_dir = _run(tmp_path, "en")
        summary = load_summary(run_dir)
        assert summary.narrative_source == "template"
        assert any("+21" in paragraph for paragraph in summary.happening)
        assert all(a.robustness_line is None for a in summary.assessments)


class TestChatBrief:
    def test_follow_ups_say_which_reruns_are_instant(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "en")
        follow_ups = {f.id: f for f in _facts(run_dir).follow_ups}
        assert follow_ups["seasons"].cached
        assert follow_ups["raw_views"].cached
        assert not follow_ups["add_editions"].cached
        assert not follow_ups["longer_period"].cached
        assert "appendix" in follow_ups["method_page"].change

    def test_labels_left_in_english_give_way_to_forms_without_words(self, tmp_path: Path) -> None:
        pipeline, run_dir = _run(tmp_path, "de")
        facts = _facts(run_dir)
        # Only the PDF headings are translated, none of the chat's own labels.
        ui = {k: f"DE {v}" for k, v in facts.ui.items() if k.startswith("report.")}
        narrative = _template(run_dir).model_copy(update={"ui": ui})
        assert pipeline.narrate(run_dir, narrative).status == "accepted"
        brief = (run_dir / "chat_brief.md").read_text(encoding="utf-8")
        assert "Topic:" not in brief
        assert "What else I can do" not in brief
        assert brief.splitlines()[-1].startswith("PDF: ")

    def test_a_next_step_left_in_english_leaves_out_only_itself(self, tmp_path: Path) -> None:
        pipeline, run_dir = _run(tmp_path, "de")
        facts = _facts(run_dir)
        ui = {k: f"DE {v}" for k, v in facts.ui.items()}
        del ui["chat.follow_up.seasons"]
        narrative = _template(run_dir).model_copy(update={"ui": ui})
        assert pipeline.narrate(run_dir, narrative).status == "accepted"
        brief = (run_dir / "chat_brief.md").read_text(encoding="utf-8")
        assert "DE What else I can do" in brief
        assert "DE I can look at a longer period" in brief
        assert "months of the year" not in brief

    def test_a_follow_up_says_what_changed_against_the_run_before(self, tmp_path: Path) -> None:
        """The answer is sent as it is: the code, not the agent, states the comparison."""
        first, first_dir = _run(tmp_path, "en", {"question_type": "assess", "projects": ["uk"]})
        assert first.narrate(first_dir, _template(first_dir)).status == "accepted"
        pipeline, run_dir = _run(tmp_path, "en", run_id="r2")
        assert pipeline.narrate(run_dir, _template(run_dir)).status == "accepted"
        brief = (run_dir / "chat_brief.md").read_text(encoding="utf-8")
        assert "Against the previous run (2024-09 – 2026-08):" in brief
        assert "uk.wikipedia: attention share 37.9 → 37.9 per million" in brief
        assert "Editions added: cs.wikipedia." in brief

    def test_a_period_beyond_the_data_is_measured_where_they_exist_and_said(
        self, tmp_path: Path
    ) -> None:
        """ "Since 2010" is not an error: the report starts in 2015-07 and says why."""
        period = {"start": "2010-01", "end": "2026-09"}
        pipeline, run_dir = _run(tmp_path, "en", {"period": period})
        summary = load_summary(run_dir)
        assert (f"{summary.period.start:%Y-%m}", f"{summary.period.end:%Y-%m}") == (
            "2015-07",
            "2026-08",
        )
        assert pipeline.narrate(run_dir, _template(run_dir)).status == "accepted"
        brief = (run_dir / "chat_brief.md").read_text(encoding="utf-8")
        assert "Pageview data start in 2015-07, so the analysis begins there" in brief
        assert "2026-09 is not complete yet, so the analysis ends in 2026-08" in brief

    def test_a_run_the_user_never_saw_is_not_compared(self, tmp_path: Path) -> None:
        """A run the agent corrected within the same answer was never shown to the user."""
        _run(tmp_path, "en", {"question_type": "assess", "projects": ["uk"]})
        pipeline, run_dir = _run(tmp_path, "en", run_id="r2")
        assert pipeline.narrate(run_dir, _template(run_dir)).status == "accepted"
        assert "previous run" not in (run_dir / "chat_brief.md").read_text(encoding="utf-8")

    def test_a_first_run_has_nothing_to_compare(self, tmp_path: Path) -> None:
        pipeline, run_dir = _run(tmp_path, "en")
        assert pipeline.narrate(run_dir, _template(run_dir)).status == "accepted"
        assert "previous run" not in (run_dir / "chat_brief.md").read_text(encoding="utf-8")

    def test_a_text_with_no_translated_label_is_rejected(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "de")
        facts = _facts(run_dir)
        untranslated = _template(run_dir).model_copy(update={"ui": {}})
        assert any("facts.ui" in m for m in _messages(facts, untranslated))

    def test_the_run_writes_the_method_next_to_the_report(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "ru")
        method = (run_dir / "method.md").read_text(encoding="utf-8")
        assert method.startswith("# Method")
        assert "uk.wikipedia" in method


class TestTemplatePassesItsOwnChecks:
    """Once the agent answered the labels, the template must pass: the code's own text never
    trips the checks, whatever the language of the report and the word lists."""

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


def _add_to_story(narrative: Narrative, text: str, uses: list[str]) -> Narrative:
    return narrative.model_copy(
        update={"story": [*narrative.story, Paragraph(text=text, uses=uses)]}
    )


class TestRejections:
    @pytest.fixture
    def ru(self, tmp_path: Path) -> tuple[Facts, Narrative]:
        _, run_dir = _run(tmp_path, "ru")
        facts = _facts(run_dir)
        return facts, _russian(facts)

    def test_own_words_pass(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        assert _messages(facts, narrative) == []

    @pytest.mark.parametrize(
        ("text", "uses", "expected"),
        [
            ("Доля выросла на 57 %.", [VS_UK], "'57 %' is not in the observations"),
            ("Украинская аудитория в 14 раз больше.", [EDITIONS], "'14' is not in"),
            ("Статью открывают около 4 200 раз.", [VS_UK], "'4 200' is not in"),
            ("Пять лет назад интерес был другим.", [VS_UK], "not counted back from today"),
            ("Статью читают 4 200 человек в месяц.", ["size:astronomy/uk"], "not people"),
            ("В Украине интерес растёт.", [VS_UK], "not a country"),
            ("Спрос на астрономию растёт.", [VS_UK], "not demand"),
            ("Рост статистически значим.", [VS_UK], "No statistical jargon"),
            ("Это 1 из 26 000 просмотров.", [VS_UK], "1 in N"),
            ("Учитывайте 季节性 интереса.", [VS_UK], "another script"),
            ("Уровень пяти лет назад был выше.", [VS_UK], "not counted back from today"),
            ("За последний год спад ускорился.", [VS_UK], "says the change speeds up"),
            ("Україна Wikipedia читає менше.", [VS_UK], "not a country"),
            (
                "Доля +21 %, просмотры +21 %, раздел +0 %, снова +21 %, и +21 %.",
                [VS_UK],
                "percentages",
            ),
            ("Тема растёт.", ["season:astronomy/xx"], "not an observation of facts.json"),
            ("Тема растёт.", [], "List in 'uses'"),
        ],
    )
    def test_story(
        self, ru: tuple[Facts, Narrative], text: str, uses: list[str], expected: str
    ) -> None:
        facts, narrative = ru
        broken = _add_to_story(
            narrative.model_copy(update={"story": narrative.story[:1]}), text, uses
        )
        messages = _messages(facts, broken)
        assert any(expected in m for m in messages), messages

    def test_a_number_passes_once_its_observation_is_cited(
        self, ru: tuple[Facts, Narrative]
    ) -> None:
        facts, narrative = ru
        text = "Статью открывают около 4 200 раз в месяц."
        story = narrative.story[:1]
        uncited = narrative.model_copy(
            update={"story": [*story, Paragraph(text=text, uses=[VS_UK])]}
        )
        assert _messages(facts, uncited)
        cited = narrative.model_copy(
            update={"story": [*story, Paragraph(text=text, uses=["size:astronomy/uk"])]}
        )
        assert _messages(facts, cited) == []

    def test_the_edition_by_its_language_passes_and_limits_may_name_the_country(
        self, ru: tuple[Facts, Narrative]
    ) -> None:
        facts, narrative = ru
        limits = "Украинская Википедия — это язык, а не Украина."
        text = "Украинская Википедия читает астрономию всё больше."
        fine = _add_to_story(narrative, text, [VS_UK]).model_copy(update={"limits": limits})
        assert _messages(facts, fine) == []

    def test_words_for_thousands_times_and_years_pass(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        text = "Русская аудитория больше: около 4,2 тысячи просмотров против 2 тысяч."
        fine = _add_to_story(narrative, text, [EDITIONS]).model_copy(
            update={
                "headline": "Интерес растёт с 2025 года.",
                "check": "Сравните поиск курсов в Google Trends для Украины и Чехии.",
            }
        )
        assert _messages(facts, fine) == []

    def test_a_long_story_is_rejected(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        paragraph = Paragraph(text="Доля в чтении раздела растёт. " * 15, uses=[VS_UK])
        long = narrative.model_copy(update={"story": [paragraph] * 4})
        assert any("characters in all" in m for m in _messages(facts, long))

    def test_the_story_rests_on_the_main_observations(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        minor = narrative.model_copy(
            update={
                "story": [
                    Paragraph(
                        text="Последние месяцы продолжают рост.", uses=["recent:astronomy/uk"]
                    )
                ]
            }
        )
        assert any("cite at least one caution or high" in m for m in _messages(facts, minor))

    def test_the_meaning_rests_on_decision_observations(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        bare = narrative.model_copy(update={"meaning": Paragraph(text="Запускайтесь.", uses=[])})
        assert any("decision observations" in m for m in _messages(facts, bare))

    def test_every_caution_is_carried(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        caution = ObservationOut(
            id="caution:astronomy/cs",
            kind="caution",
            pair="astronomy/cs",
            weight="caution",
            statement="The Czech Wikipedia is measured through a broader article.",
        )
        with_caution = facts.model_copy(update={"observations": [*facts.observations, caution]})
        assert any("caution:astronomy/cs" in m for m in _messages(with_caution, narrative))
        carried = _add_to_story(narrative, "Чешский раздел измерен по общей статье.", [caution.id])
        assert _messages(with_caution, carried) == []

    def test_a_substitute_article_is_named_in_the_text(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        caution = ObservationOut(
            id="caution:astronomy/cs",
            kind="caution",
            pair="astronomy/cs",
            weight="caution",
            statement="The Czech Wikipedia has no article on astronomy itself; its numbers come "
            "from the broader article «Vesmír»: name «Vesmír» whenever this edition is mentioned.",
        )
        facts = facts.model_copy(update={"observations": [*facts.observations, caution]})
        unnamed = _add_to_story(narrative, "Чешский раздел измерен по общей статье.", [caution.id])
        assert any("«Vesmír»" in m for m in _messages(facts, unnamed))
        named = _add_to_story(narrative, "Чешский раздел измерен по статье «Vesmír».", [caution.id])
        assert _messages(facts, named) == []

    def test_headline_is_one_sentence_without_numbers(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        broken = narrative.model_copy(update={"headline": "Рост 21 %. Всё хорошо."})
        messages = _messages(facts, broken)
        assert any("no numbers" in m for m in messages)
        assert any("one sentence" in m for m in messages)

    def test_blocks_keep_their_shape(self, ru: tuple[Facts, Narrative]) -> None:
        facts, narrative = ru
        paragraph = narrative.story[0]
        broken = narrative.model_copy(
            update={"story": [paragraph] * 5, "check": "", "language": "en"}
        )
        messages = _messages(facts, broken)
        assert any("At most 4 paragraphs" in m for m in messages)
        assert any("'check' is empty" in m for m in messages)
        assert any("Write in 'ru'" in m for m in messages)
        long = narrative.model_copy(update={"limits": "очень " * 60})
        assert any("Shorten to 250" in m for m in _messages(facts, long))

    def test_interface_labels_keep_their_placeholders(self, tmp_path: Path) -> None:
        _, run_dir = _run(tmp_path, "de")
        facts, narrative = _facts(run_dir), _template(run_dir)
        # The template carries every label to translate; one left out stays English.
        assert narrative.ui
        some = dict(list(narrative.ui.items())[:1])
        partly = narrative.model_copy(update={"ui": some})
        assert not any(p.block == "ui" for p in check_narrative(facts, partly))
        ui = {key: f"DE {text}" for key, text in narrative.ui.items()}
        with_ui = narrative.model_copy(update={"ui": ui})
        assert _messages(facts, with_ui) == []
        key = next(k for k, v in narrative.ui.items() if "{" in v)
        bad = with_ui.model_copy(update={"ui": {**ui, key: "ohne Platzhalter"}})
        assert any("placeholders" in m for m in _messages(facts, bad))


class TestNarrate:
    def test_accepted_text_goes_into_the_reports_and_the_chat_brief(self, tmp_path: Path) -> None:
        pipeline, run_dir = _run(tmp_path, "ru")
        narrative = _russian(_facts(run_dir))
        outcome = pipeline.narrate(run_dir, narrative)
        assert outcome.status == "accepted", outcome.problems
        assert outcome.exit_code == 0
        assert outcome.summary.narrative_source == "agent"
        report = (run_dir / "summary.md").read_text(encoding="utf-8")
        assert narrative.headline in report
        assert "21 %" in report  # the typed space before % no longer breaks the line
        pdf = "".join(page.extract_text() for page in PdfReader(run_dir / "report.pdf").pages)
        assert "украинской" in pdf
        # The chat answer is laid out from the accepted blocks, with next steps and the PDF.
        brief = (run_dir / "chat_brief.md").read_text(encoding="utf-8").strip()
        assert brief.startswith(narrative.topic)  # the agent's line, in the user's language
        assert narrative.headline in brief
        assert "около 4 200 раз в месяц" in brief
        assert narrative.meaning.text in brief
        assert narrative.check in brief
        assert narrative.limits in brief
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
        ui = {key: f"DE {text}" for key, text in facts.ui.items()}
        narrative = _template(run_dir).model_copy(update={"ui": ui})
        assert pipeline.narrate(run_dir, narrative).status == "accepted"
        assert "DE " in (run_dir / "summary.md").read_text(encoding="utf-8")
        assert "DE PDF report" in (run_dir / "chat_brief.md").read_text(encoding="utf-8")
        cache = run_dir.parent / "ui-de.json"
        assert json.loads(cache.read_text(encoding="utf-8")) == ui
        # The next run of the session renders with them and asks only for new labels.
        _, next_dir = _run(tmp_path, "de", run_id="r2")
        assert "DE " in (next_dir / "summary.md").read_text(encoding="utf-8")
        assert not set(_facts(next_dir).ui) & set(ui)
