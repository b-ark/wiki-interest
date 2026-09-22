"""Related-concept ranking: weights, consensus, exclusions, cap and determinism."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from wiki_interest.domain.bundle import BundleSettings, RelatedConcept, rank_related_concepts
from wiki_interest.domain.models import ResolutionSource, WikiProject

UK, CS, PL = WikiProject("uk"), WikiProject("cs"), WikiProject("pl")
MAIN = "Q333"
S = BundleSettings()


def qids(concepts: tuple[RelatedConcept, ...]) -> list[str]:
    return [c.qid for c in concepts]


class TestWeights:
    def test_wikidata_relation_gets_wikidata_weight(self) -> None:
        (concept,) = rank_related_concepts(MAIN, {}, {"P279": ["Q1"]})
        assert concept == RelatedConcept(
            "Q1", S.wikidata_weight, ResolutionSource.WIKIDATA_RELATION, 1
        )

    def test_lead_link_in_half_of_projects_gets_consensus_weight(self) -> None:
        leads = {UK: ["Q1"], CS: ["Q1"], PL: ["Q2"]}
        by_qid = {c.qid: c for c in rank_related_concepts(MAIN, leads, {})}
        assert by_qid["Q1"].weight == S.consensus_lead_weight
        assert by_qid["Q1"].source is ResolutionSource.LEAD_LINK
        assert by_qid["Q1"].support == 2
        assert by_qid["Q2"].weight == S.single_lead_weight
        assert by_qid["Q2"].support == 1

    def test_consensus_threshold_rounds_up(self) -> None:
        leads = {UK: ["Q1"], CS: ["Q1"], PL: ["Q1"], WikiProject("de"): [], WikiProject("fr"): []}
        (concept,) = rank_related_concepts(MAIN, leads, {})
        assert concept.weight == S.consensus_lead_weight
        leads[PL] = []
        (concept,) = rank_related_concepts(MAIN, leads, {})
        assert concept.weight == S.single_lead_weight

    def test_wikidata_wins_over_lead_and_counts_both_as_support(self) -> None:
        (concept,) = rank_related_concepts(MAIN, {UK: ["Q1"]}, {"P361": ["Q1"]})
        assert concept.source is ResolutionSource.WIKIDATA_RELATION
        assert concept.support == 2

    def test_duplicate_links_within_one_lead_count_once(self) -> None:
        (concept,) = rank_related_concepts(MAIN, {UK: ["Q1", "Q1", "Q1"]}, {})
        assert concept.support == 1

    def test_custom_settings(self) -> None:
        custom = BundleSettings(max_related=1, wikidata_weight=0.9)
        (concept,) = rank_related_concepts(MAIN, {UK: ["Q2"]}, {"P279": ["Q1"]}, settings=custom)
        assert (concept.qid, concept.weight) == ("Q1", 0.9)


class TestExclusions:
    def test_main_and_excluded_never_appear(self) -> None:
        leads = {UK: [MAIN, "Q1", "Q2"]}
        result = rank_related_concepts(MAIN, leads, {"P527": [MAIN, "Q3"]}, excluded={"Q2", "Q3"})
        assert qids(result) == ["Q1"]

    def test_cap_keeps_the_best(self) -> None:
        leads = {UK: [f"Q{i}" for i in range(30)]}
        result = rank_related_concepts(
            MAIN, leads, {"P279": ["Q29"]}, settings=BundleSettings(max_related=3)
        )
        assert len(result) == 3
        assert result[0].qid == "Q29"

    def test_empty_inputs_give_empty_bundle(self) -> None:
        assert rank_related_concepts(MAIN, {}, {}) == ()
        assert rank_related_concepts(MAIN, {UK: []}, {"P279": []}) == ()


class TestOrdering:
    def test_weight_then_support_then_qid(self) -> None:
        leads = {UK: ["Q9", "Q5"], CS: ["Q5", "Q7"], PL: ["Q7", "Q1"]}
        result = rank_related_concepts(MAIN, leads, {"P279": ["Q8"]})
        assert qids(result) == ["Q5", "Q7", "Q8", "Q1", "Q9"]

    @given(
        st.lists(
            st.lists(st.sampled_from([f"Q{i}" for i in range(12)]), max_size=8),
            min_size=1,
            max_size=4,
        ),
        st.lists(st.sampled_from([f"Q{i}" for i in range(12)]), max_size=5),
    )
    def test_is_independent_of_input_order(
        self, leads: list[list[str]], related: list[str]
    ) -> None:
        projects = [UK, CS, PL, WikiProject("de")][: len(leads)]
        mapping = dict(zip(projects, leads, strict=True))
        baseline = rank_related_concepts(MAIN, mapping, {"P279": related})
        shuffled_items = list(mapping.items())
        shuffled_items.reverse()
        shuffled = rank_related_concepts(
            MAIN,
            {p: list(reversed(links)) for p, links in shuffled_items},
            {"P279": list(reversed(related))},
        )
        assert shuffled == baseline
        assert len(baseline) <= S.max_related


@pytest.mark.parametrize("n_projects", [1, 2, 3, 4])
def test_single_lead_link_reaches_consensus_only_with_two_projects_or_fewer(
    n_projects: int,
) -> None:
    projects = [UK, CS, PL, WikiProject("de")][:n_projects]
    leads = {p: (["Q1"] if p is UK else []) for p in projects}
    (concept,) = rank_related_concepts(MAIN, leads, {})
    expected = S.consensus_lead_weight if n_projects <= 2 else S.single_lead_weight
    assert concept.weight == expected
