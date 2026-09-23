"""Coverage advisor: which editions lack an article and what could stand in for it."""

from __future__ import annotations

from datetime import date

from fakes import FakeEntity, FakeMediaWiki, FakePage, FakePageviews, FakeWikidata
from wiki_interest.application.coverage import CoverageAdvisor, CoverageGap, CoverageOption
from wiki_interest.application.resolution import TopicResolver
from wiki_interest.contracts.request import AnalysisRequest
from wiki_interest.domain.models import Access, Agent, Granularity, WikiProject, Window
from wiki_interest.ports.mediawiki import Mention

PL, CS = WikiProject("pl"), WikiProject("cs")
TODAY = date(2026, 9, 22)
LAST_YEAR = [date(2025, 9, 1)] + [date(2026, m, 1) for m in range(1, 9)]
"""Months inside the 12-month window before ``TODAY``; views outside it must not count."""


class _World:
    """Intermittent fasting: an article in cs, none in pl; "fasting" is the broader item."""

    def __init__(self) -> None:
        self.wikidata = FakeWikidata(
            [
                FakeEntity(
                    "Q1666254",
                    {"en": "intermittent fasting", "cs": "přerušovaný půst"},
                    sitelinks={CS: "Přerušovaný půst"},
                    claims={"P279": ["Q44602"], "P361": ["Q1"]},
                    description="a diet",
                ),
                FakeEntity("Q44602", {"en": "fasting"}, sitelinks={PL: "Post", CS: "Půst"}),
                FakeEntity("Q1", {"en": "dieting"}, sitelinks={CS: "Dieta"}),
            ]
        )
        self.mediawiki = FakeMediaWiki()
        self.mediawiki.add_page(CS, FakePage("Přerušovaný půst", qid="Q1666254"))
        self.mediawiki.add_page(PL, FakePage("Post", qid="Q44602"))
        self.mediawiki.add_page(
            PL,
            FakePage(
                "Głodówka",
                qid="Q9284146",
                redirects=["Post przerywany"],
                redirect_sections={"Post przerywany": "Odmiany"},
            ),
        )
        self.pageviews = FakePageviews()
        self.pageviews.set_article(PL, "Post", dict.fromkeys(LAST_YEAR, 1500.0))
        self.pageviews.set_article(
            PL, "Post przerywany", {LAST_YEAR[0]: 30.0, date(2024, 1, 1): 9e9}
        )
        self.pageviews.set_article(PL, "Insulinooporność", dict.fromkeys(LAST_YEAR, 800.0))

    def advisor(self) -> CoverageAdvisor:
        return CoverageAdvisor(self.wikidata, self.mediawiki, self.pageviews)

    def gaps(self, **topic: object) -> tuple[CoverageGap, ...]:
        request = _request(**topic)
        resolved = TopicResolver(self.wikidata, self.mediawiki).resolve_request(request)
        return self.advisor().gaps(request, resolved, TODAY)


def _request(**topic: object) -> AnalysisRequest:
    spec: dict[str, object] = {"id": "if", "query": "intermittent fasting", "query_language": "en"}
    spec.update(topic)
    return AnalysisRequest.model_validate(
        {"question_type": "compare", "topics": [spec], "projects": ["pl", "cs"]}
    )


def _kinds(options: tuple[CoverageOption, ...]) -> list[tuple[str, str | None]]:
    return [(o.kind, o.title) for o in options]


class TestWhenToAsk:
    def test_only_editions_without_an_article_are_gaps(self) -> None:
        gaps = _World().gaps()
        assert [(g.topic_id, g.project) for g in gaps] == [("if", PL)]

    def test_a_decided_edition_is_not_asked_again(self) -> None:
        world = _World()
        assert world.gaps(substitutes={"pl": "skip"}) == ()
        # Even a substitute that turns out not to exist counts as decided: asking again loops.
        assert world.gaps(substitutes={"pl": {"title": "Nope", "kind": "broader"}}) == ()

    def test_no_gap_means_no_lookups(self) -> None:
        world = _World()
        world.gaps(substitutes={"pl": "skip"})
        assert world.pageviews.calls == []
        assert not any(name == "summary" for name, _ in world.wikidata.calls)


class TestOptions:
    def test_order_redirect_broader_mention_skip_with_views(self) -> None:
        world = _World()
        world.mediawiki.add_mentions(
            PL,
            "Post przerywany",
            [Mention("Insulinooporność", "stosować post przerywany"), Mention("Post", "…")],
        )
        (gap,) = world.gaps(local_terms={"pl": "Post przerywany"})
        assert gap.terms == ("Post przerywany",)
        assert _kinds(gap.options) == [
            ("redirect", "Post przerywany"),
            ("broader", "Post"),
            ("mention", "Insulinooporność"),
            ("skip", None),
        ]
        redirect, broader, mention, skip = gap.options
        assert (redirect.target, redirect.section) == ("Głodówka", "Odmiany")
        assert redirect.views_avg == 30.0  # views before the 12-month window are ignored
        assert broader.views_avg == 1500.0
        assert mention.snippet == "stosować post przerywany"
        assert mention.views_avg == 800.0
        assert skip.views_avg is None

    def test_option_views_use_the_last_twelve_full_months_and_request_filters(self) -> None:
        world = _World()
        world.gaps()
        (call,) = [args for name, args in world.pageviews.calls if args[1] == "Post"]
        window = call[2]
        assert isinstance(window, Window)
        assert (window.granularity, window.start, window.end) == (
            Granularity.MONTHLY,
            date(2025, 9, 1),
            date(2026, 8, 1),
        )
        assert call[3:] == (Access.ALL, Agent.USER)

    def test_english_labels_are_never_searched_in_another_language(self) -> None:
        world = _World()
        world.mediawiki.add_mentions(PL, "intermittent fasting", [Mention("Stres oksydacyjny", "")])
        (gap,) = world.gaps()
        assert gap.terms == ()
        assert "mention" not in [o.kind for o in gap.options]
        assert not any(name == "mentions" for name, _ in world.mediawiki.calls)

    def test_query_in_the_edition_language_is_a_local_term(self) -> None:
        world = _World()
        world.wikidata.entities["Q1666254"].labels["pl"] = "Post przerywany"
        (gap,) = world.gaps(query="post przerywany", query_language="pl", qid="Q1666254")
        # The label and the query differ only in case, so one term is searched.
        assert gap.terms == ("Post przerywany",)

    def test_broader_articles_are_capped_and_deduplicated(self) -> None:
        world = _World()
        world.wikidata.entities["Q1666254"].claims["P361"] = ["Q44602", "Q2", "Q3"]
        world.wikidata.add(FakeEntity("Q2", {"en": "a"}, sitelinks={PL: "A"}))
        world.wikidata.add(FakeEntity("Q3", {"en": "b"}, sitelinks={PL: "B"}))
        (gap,) = world.gaps()
        assert _kinds(gap.options) == [("broader", "Post"), ("broader", "A"), ("skip", None)]

    def test_mentions_are_capped_across_terms(self) -> None:
        world = _World()
        world.mediawiki.add_mentions(PL, "one", [Mention(f"M{i}", "") for i in range(2)])
        world.mediawiki.add_mentions(PL, "two", [Mention("M1", ""), Mention("M9", "")])
        (gap,) = world.gaps(
            local_terms={"pl": "one"}, query="two", query_language="pl", qid="Q1666254"
        )
        mentions = [o.title for o in gap.options if o.kind == "mention"]
        assert mentions == ["M0", "M1", "M9"]

    def test_topic_without_entity_still_gets_options_where_it_is_missing(self) -> None:
        world = _World()
        world.mediawiki.add_page(CS, FakePage("Zzz článek"))
        world.mediawiki.add_search(CS, "zzz", ["Zzz článek"])
        world.mediawiki.add_mentions(PL, "zzz", [Mention("Z", "zzz")])
        (gap,) = world.gaps(query="zzz", query_language="pl")
        assert gap.entity is None
        assert _kinds(gap.options) == [("mention", "Z"), ("skip", None)]


class TestEntity:
    def test_gap_carries_the_entity_and_how_it_was_found(self) -> None:
        world = _World()
        (gap,) = world.gaps(
            query="post przerywany", query_language="pl", query_en="intermittent fasting"
        )
        assert gap.entity is not None
        assert gap.entity.qid == "Q1666254"
        assert gap.entity.languages == ("cs",)
        assert gap.matched_in_english is True
