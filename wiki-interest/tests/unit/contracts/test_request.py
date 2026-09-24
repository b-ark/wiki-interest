"""Validation and normalisation rules of request.json."""

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from wiki_interest.contracts.request import (
    AnalysisRequest,
    Period,
    SubstituteSpec,
    TopicSpec,
)
from wiki_interest.domain.models import WikiProject

EXAMPLES = sorted((Path(__file__).resolve().parents[3] / "assets" / "examples").glob("*.json"))


def _minimal(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "question_type": "assess",
        "topics": [{"query": "astronomy"}],
        "projects": ["uk"],
    }
    data.update(overrides)
    return data


class TestDefaultsAndNormalisation:
    def test_minimal_request_gets_sensible_defaults(self) -> None:
        request = AnalysisRequest.model_validate(_minimal())
        assert request.schema_version == "1"
        assert request.projects == ["uk.wikipedia"]
        assert request.project_objects == (WikiProject("uk"),)
        assert request.period is None
        assert request.agent == "user"
        assert request.normalization == "per_million"
        assert request.report.language == "en"

    def test_projects_are_normalised_and_deduplicated(self) -> None:
        request = AnalysisRequest.model_validate(
            _minimal(projects=["UK", "uk.wikipedia.org", "cswiki", "cs.wikipedia"])
        )
        assert request.projects == ["uk.wikipedia", "cs.wikipedia"]

    def test_topic_id_is_derived_from_latin_query(self) -> None:
        request = AnalysisRequest.model_validate(
            _minimal(topics=[{"query": "Intermittent Fasting"}])
        )
        assert request.topics[0].id == "intermittent-fasting"

    def test_topic_id_falls_back_to_index_for_non_latin_query(self) -> None:
        request = AnalysisRequest.model_validate(
            _minimal(topics=[{"query": "астрономія"}, {"query": "Post przerywany"}])
        )
        assert [t.id for t in request.topics] == ["topic-1", "post-przerywany"]

    def test_topic_spec_instances_also_get_ids(self) -> None:
        request = AnalysisRequest.model_validate(_minimal(topics=[TopicSpec(query="Astronomy")]))
        assert request.topics[0].id == "astronomy"

    def test_per_project_keys_are_normalised(self) -> None:
        request = AnalysisRequest.model_validate(
            _minimal(topics=[{"query": "astronomy", "local_terms": {"ukwiki": "астрономія"}}])
        )
        assert request.topics[0].local_terms == {"uk.wikipedia": "астрономія"}

    def test_request_is_immutable(self) -> None:
        request = AnalysisRequest.model_validate(_minimal())
        with pytest.raises(ValidationError):
            request.question_type = "rank"  # type: ignore[misc]


class TestRejections:
    def test_unknown_field_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra"):
            AnalysisRequest.model_validate(_minimal(granularity="daily"))

    def test_duplicate_topic_ids_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            AnalysisRequest.model_validate(
                _minimal(topics=[{"query": "a", "id": "x"}, {"query": "b", "id": "x"}])
            )

    def test_terms_for_unlisted_project_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="not in the request"):
            AnalysisRequest.model_validate(
                _minimal(topics=[{"query": "a", "local_terms": {"pl": "x"}}])
            )

    def test_compare_needs_two_combinations(self) -> None:
        with pytest.raises(ValidationError, match="at least two"):
            AnalysisRequest.model_validate(_minimal(question_type="compare"))
        AnalysisRequest.model_validate(_minimal(question_type="compare", projects=["uk", "pl"]))

    def test_removed_bundle_fields_are_rejected(self) -> None:
        for field in ({"bundle": "main"}, {"extra_titles": {"uk": ["X"]}}):
            with pytest.raises(ValidationError, match="extra"):
                AnalysisRequest.model_validate(_minimal(topics=[{"query": "a", **field}]))

    def test_invalid_project_is_reported(self) -> None:
        with pytest.raises(ValidationError, match="Invalid Wikipedia language code"):
            AnalysisRequest.model_validate(_minimal(projects=["not a project"]))

    def test_invalid_qid_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="qid"):
            AnalysisRequest.model_validate(_minimal(topics=[{"query": "a", "qid": "333"}]))


class TestPeriod:
    def test_parses_year_month_strings_and_serialises_them_back(self) -> None:
        period = Period.model_validate({"start": "2024-09", "end": "2026-08"})
        assert period.start == date(2024, 9, 1)
        assert period.end == date(2026, 8, 1)
        assert period.months == 24
        assert period.model_dump(mode="json") == {"start": "2024-09", "end": "2026-08"}

    def test_dates_are_clamped_to_first_of_month(self) -> None:
        period = Period(start=date(2024, 9, 17), end=date(2024, 10, 3))
        assert (period.start.day, period.end.day) == (1, 1)

    def test_start_before_the_data_is_moved_to_where_they_begin(self) -> None:
        period = Period.model_validate({"start": "2010-01", "end": "2016-01"})
        assert period.within_data(date(2026, 9, 24)).start == date(2015, 7, 1)

    def test_incomplete_current_month_is_left_out(self) -> None:
        period = Period.model_validate({"start": "2024-09", "end": "2026-12"})
        assert period.within_data(date(2026, 9, 24)).end == date(2026, 8, 1)

    def test_period_without_complete_data_is_rejected(self) -> None:
        period = Period.model_validate({"start": "2010-01", "end": "2014-12"})
        with pytest.raises(ValueError, match="2015-07"):
            period.within_data(date(2026, 9, 24))

    def test_rejects_end_before_start(self) -> None:
        with pytest.raises(ValidationError, match="before start"):
            Period.model_validate({"start": "2024-05", "end": "2024-04"})

    def test_rejects_malformed_strings(self) -> None:
        with pytest.raises(ValidationError, match="YYYY-MM"):
            Period.model_validate({"start": "2024/05", "end": "2024-06"})

    def test_last_full_months_excludes_current_month(self) -> None:
        period = Period.last_full_months(date(2026, 9, 22), count=24)
        assert period.end == date(2026, 8, 1)
        assert period.start == date(2024, 9, 1)
        assert period.months == 24

    def test_last_full_months_handles_january(self) -> None:
        period = Period.last_full_months(date(2026, 1, 5), count=3)
        assert (period.start, period.end) == (date(2025, 10, 1), date(2025, 12, 1))

    def test_last_full_months_never_precedes_data(self) -> None:
        period = Period.last_full_months(date(2016, 1, 1), count=24)
        assert period.start == date(2015, 7, 1)


@pytest.mark.parametrize("path", EXAMPLES, ids=[p.stem for p in EXAMPLES])
def test_bundled_examples_are_valid(path: Path) -> None:
    """The examples the agent copies from must always validate."""
    AnalysisRequest.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_examples_exist() -> None:
    assert len(EXAMPLES) >= 3


class TestCoverageFields:
    def test_local_terms_and_substitutes_are_keyed_by_project_domain(self) -> None:
        request = AnalysisRequest.model_validate(
            _minimal(
                projects=["pl", "cs"],
                topics=[
                    {
                        "query": "post przerywany",
                        "query_language": "pl",
                        "query_en": "intermittent fasting",
                        "local_terms": {"cs": "přerušovaný půst"},
                        "substitutes": {
                            "plwiki": {"title": "Post", "kind": "broader"},
                            "cs": "skip",
                        },
                    }
                ],
            )
        )
        topic = request.topics[0]
        assert topic.query_en == "intermittent fasting"
        assert topic.local_terms == {"cs.wikipedia": "přerušovaný půst"}
        assert topic.substitutes == {
            "pl.wikipedia": SubstituteSpec(title="Post", kind="broader"),
            "cs.wikipedia": "skip",
        }

    def test_unknown_substitute_kind_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TopicSpec.model_validate(
                {"query": "a", "substitutes": {"pl": {"title": "X", "kind": "guess"}}}
            )

    @pytest.mark.parametrize("field", ["local_terms", "substitutes"])
    def test_decisions_for_unlisted_projects_are_rejected(self, field: str) -> None:
        value = {"de": "skip"} if field == "substitutes" else {"de": "Fasten"}
        with pytest.raises(ValidationError, match="not in the request"):
            AnalysisRequest.model_validate(_minimal(topics=[{"query": "a", field: value}]))


class TestArticleUrl:
    def test_link_is_parsed_into_edition_and_title(self) -> None:
        topic = TopicSpec.model_validate(
            {
                "query": "a",
                "article_url": "https://pl.m.wikipedia.org/wiki/G%C5%82od%C3%B3wka_lecznicza#x",
            }
        )
        assert topic.article_ref == (WikiProject("pl"), "Głodówka lecznicza")

    def test_non_wikipedia_link_is_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TopicSpec.model_validate({"query": "a", "article_url": "https://example.com/wiki/X"})
