"""The recommendation: choice, why, confidence and a next check the skill can run itself."""

# ruff: noqa: RUF001  -- Ukrainian text in the expectations is intentional.

from __future__ import annotations

from fakes import FakeEntity, FakeWikidata
from wiki_interest.application.recommend import (
    recommend,
    recommendation_lines,
    recommendation_observation,
)
from wiki_interest.application.related import Related, RelatedTopics, local_names
from wiki_interest.contracts.summary import TrendOut, TrustOut
from wiki_interest.domain.models import WikiProject
from wiki_interest.i18n import Translator

RU, CS, EN = WikiProject("ru"), WikiProject("cs"), WikiProject("en")


def _verdict(
    language: str,
    verdict: str,
    *,
    views: float,
    start: float = 10.0,
    end: float = 9.0,
    slope: float = -5.0,
    confidence: str = "medium",
    step: str | None = None,
) -> TrendOut:
    return TrendOut(
        topic_id="veganism",
        project=f"{language}.wikipedia",
        label=language,
        verdict=verdict,  # type: ignore[arg-type]
        window_start="2024-09",
        window_end="2026-08",
        segment_start=step or "2024-09",
        after_step=step,
        step_change=-25.0 if step else None,
        slope_pct_per_year=slope,
        level_start=start,
        level_end=end,
        views_avg=views,
        trust=TrustOut(confidence=confidence),  # type: ignore[arg-type]
    )


REFERENCE = [
    _verdict("ru", "stable", views=6_900, start=8.9, end=8.2, slope=-5, step="2024-12"),
    _verdict("cs", "declining", views=750, start=12.0, end=7.7, slope=-30, step="2025-05"),
]
NEIGHBOURS = [
    Related("Q83364", "вегетаріанство", ("ru.wikipedia", "cs.wikipedia")),
    Related("Q7201457", "рослинна дієта", ("ru.wikipedia",)),
]


class TestChoice:
    def test_the_reference_picks_the_stable_edition_and_says_none_grows(self) -> None:
        rec = recommend("veganism", REFERENCE, related=NEIGHBOURS)
        assert rec is not None
        assert rec.choice == "veganism/ru"
        assert rec.none_growing
        assert rec.confidence == "medium"
        assert rec.next_check is not None
        assert rec.next_check.kind == "related"
        assert [i.label for i in rec.next_check.items] == ["вегетаріанство", "рослинна дієта"]
        lines = recommendation_lines(rec, REFERENCE, Translator("uk"))
        assert lines.line == (
            "Рекомендація: ru: інтерес стабілізувався після спаду (8,9 → 8,2, −5 %/рік); "
            "cs: інтерес продовжує падати (12,0 → 7,7, −30 %/рік). Жоден мовний розділ не "
            "показує зростання. Якщо обирати — російська Вікіпедія: тут і краща динаміка "
            "інтересу, і найбільша аудиторія. Довіра до вибору: середня."
        )
        assert lines.next_line == (
            "Наступна перевірка: суміжні статті — вегетаріанство, рослинна дієта; я можу додати "
            "їх до цього аналізу."
        )

    def test_growth_beats_a_larger_audience(self) -> None:
        verdicts = [
            _verdict("ru", "stable", views=10_000),
            _verdict("cs", "growing", views=500, slope=20),
        ]
        rec = recommend("veganism", verdicts)
        assert rec is not None
        assert rec.choice == "veganism/cs"
        assert not rec.none_growing
        assert (rec.decided_by, rec.largest) == ("verdict", "veganism/ru")
        # The chart of views shows ru's bars twenty times taller: the line says why cs wins.
        line = recommendation_lines(rec, verdicts, Translator("uk")).line
        assert (
            "Якщо обирати — чеська Вікіпедія: вирішує динаміка інтересу, хоча найбільша "
            "аудиторія — російська Вікіпедія." in line
        )

    def test_between_equal_verdicts_trust_then_audience_decides(self) -> None:
        verdicts = [
            _verdict("ru", "stable", views=10_000, confidence="low"),
            _verdict("cs", "stable", views=500, confidence="high"),
        ]
        rec = recommend("veganism", verdicts)
        assert rec is not None
        assert rec.choice == "veganism/cs"
        assert (rec.decided_by, rec.largest) == ("trust", "veganism/ru")
        assert "the largest audience is the Russian Wikipedia" in (
            recommendation_lines(rec, verdicts, Translator("en")).line
        )
        same = [_verdict("ru", "stable", views=10_000), _verdict("cs", "stable", views=500)]
        chosen = recommend("veganism", same)
        assert chosen is not None
        assert chosen.choice == "veganism/ru"
        assert (chosen.decided_by, chosen.largest) == ("size", None)
        assert "the size of the audience decides." in (
            recommendation_lines(chosen, same, Translator("en")).line
        )

    def test_a_larger_audience_with_a_weaker_verdict_is_named_even_after_a_tie(self) -> None:
        verdicts = [
            _verdict("ru", "stable", views=500),
            _verdict("cs", "stable", views=400),
            _verdict("pl", "declining", views=10_000),
        ]
        rec = recommend("veganism", verdicts)
        assert rec is not None
        assert (rec.choice, rec.decided_by, rec.largest) == ("veganism/ru", "size", "veganism/pl")
        assert "the largest audience overall is the Polish Wikipedia." in (
            recommendation_lines(rec, verdicts, Translator("en")).line
        )

    def test_one_edition_gives_its_verdict_not_a_choice(self) -> None:
        rec = recommend("veganism", REFERENCE[:1])
        assert rec is not None
        assert rec.single
        assert (rec.decided_by, rec.largest) == (None, None)
        line = recommendation_lines(rec, REFERENCE[:1], Translator("en")).line
        assert "If you pick one" not in line
        assert line.startswith("Recommendation: ru: interest has stabilised after a drop")

    def test_no_verdict_no_recommendation(self) -> None:
        assert recommend("veganism", [_verdict("ru", "insufficient_data", views=40)]) is None


class TestNextCheck:
    def test_neighbours_in_the_chosen_edition_come_first(self) -> None:
        only_cs = [Related("Q1", "x", ("cs.wikipedia",)), Related("Q2", "y", ("ru.wikipedia",))]
        rec = recommend("veganism", REFERENCE, related=only_cs)
        assert rec is not None
        assert rec.next_check is not None
        assert [i.qid for i in rec.next_check.items] == ["Q2"]

    def test_without_neighbours_more_editions(self) -> None:
        rec = recommend("veganism", REFERENCE, more_editions=["en", "de"])
        assert rec is not None
        assert rec.next_check is not None
        assert rec.next_check.kind == "editions"
        line = recommendation_lines(rec, REFERENCE, Translator("uk")).next_line
        assert "англійська Вікіпедія, німецька Вікіпедія" in line

    def test_outside_wikipedia_only_when_nothing_is_left(self) -> None:
        rec = recommend("veganism", REFERENCE)
        assert rec is not None
        assert rec.next_check is not None
        assert rec.next_check.kind == "external"
        assert "Google Trends" in recommendation_lines(rec, REFERENCE, Translator("en")).next_line


def test_the_observation_asks_the_text_to_explain_the_choice() -> None:
    rec = recommend("veganism", REFERENCE, related=NEIGHBOURS)
    assert rec is not None
    observation = recommendation_observation(rec, REFERENCE, "veganism")
    assert observation.id == "recommendation:veganism"
    assert "If you pick one: the Russian Wikipedia: it has both" in observation.statement
    assert "never picks another" in observation.statement
    assert any(q.value == 8.9 for q in observation.numbers)


def _wikidata() -> FakeWikidata:
    return FakeWikidata(
        [
            FakeEntity(
                "Q181138",
                {"en": "veganism", "uk": "веганізм"},
                sitelinks={RU: "Веганство", CS: "Veganství", EN: "Veganism"},
                claims={"P279": ["Q83364"], "P1889": ["Q83364", "Q7201457"]},
            ),
            FakeEntity(
                "Q83364",
                {"en": "vegetarianism", "uk": "вегетаріанство"},
                sitelinks={RU: "Вегетарианство", CS: "Vegetariánství"},
            ),
            FakeEntity(
                "Q7201457",
                {"en": "plant-based diet", "uk": "Рослинна дієта"},
                sitelinks={RU: "Растительное питание"},
            ),
            FakeEntity("Q1", {"en": "Paris", "uk": "Париж"}, sitelinks={RU: "Париж"}),
        ]
    )


def test_neighbours_are_found_through_wikidata_and_named_in_the_report_language() -> None:
    related = RelatedTopics(_wikidata()).neighbours("Q181138", [RU, CS], "uk")
    assert [(r.qid, r.label, r.projects) for r in related] == [
        ("Q83364", "вегетаріанство", ("ru.wikipedia", "cs.wikipedia")),
        ("Q7201457", "рослинна дієта", ("ru.wikipedia",)),
    ]
    assert RelatedTopics(_wikidata()).more_editions("Q181138", [RU, CS]) == ["en"]


def test_a_common_noun_is_lower_case_and_a_name_keeps_its_capital() -> None:
    wikidata = _wikidata()
    wikidata.entities["Q181138"].sitelinks[WikiProject("uk")] = "Веганство"
    names = local_names(wikidata, ["Q181138", "Q1"], "uk")
    assert names == {"Q181138": "веганство", "Q1": "Париж"}


def test_a_disambiguation_is_left_out_of_the_name() -> None:
    wikidata = _wikidata()
    wikidata.entities["Q1"].sitelinks[WikiProject("uk")] = "Париж (місто)"
    assert local_names(wikidata, ["Q1"], "uk") == {"Q1": "Париж"}
