"""Scenario schema: valid files load, bad assertion types and duplicates are rejected."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from skill_evals.scenarios import (
    NumbersGrounded,
    Scenario,
    ScenarioFile,
    ScenarioLoadError,
    SummaryField,
    load_scenarios,
)

VALID = {
    "skill_name": "wiki-interest",
    "scenarios": [
        {
            "id": "compare-pl-cs",
            "name": "Compare fasting pl vs cs",
            "tags": ["compare", "uk"],
            "turns": ["Порівняй інтерес до голодування у pl та cs", "А за 5 років?"],
            "expected": "Two runs, second reuses the session.",
            "assertions": [
                {"type": "file_exists", "glob": "**/report.pdf"},
                {"type": "pdf_pages", "glob": "**/report.pdf", "max_pages": 1},
                {"type": "numbers_grounded"},
                {"type": "answer_contains", "patterns": ["pl", "cs"], "mode": "all"},
                {"type": "answer_not_contains", "patterns": ["I cannot"]},
                {"type": "tool_called", "pattern": "run\\.py"},
                {"type": "no_tool_called", "pattern": "pip install"},
                {"type": "max_turns", "n": 20},
                {"type": "max_cost_usd", "value": 0.5},
                {"type": "summary_field", "path": "reliability[0].level", "regex": "high|medium"},
                {"type": "caveats_relayed", "min_reasons": 1},
            ],
            "rubric": [{"id": "answers", "criterion": "Answers the question directly."}],
        },
        {
            "id": "ambiguous",
            "name": "Ambiguous topic",
            "turns": ["Mercury interest in de-wiki"],
            "assertions": [{"type": "clarification_asked"}],
            "should_trigger": True,
        },
    ],
}


def _write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "evals.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def test_load_valid_file_parses_every_assertion_type(tmp_path: Path) -> None:
    loaded = load_scenarios(_write(tmp_path, VALID))
    assert loaded.skill_name == "wiki-interest"
    types = [a.type for a in loaded.scenarios[0].assertions]
    assert len(types) == 11
    assert isinstance(loaded.scenarios[0].assertions[2], NumbersGrounded)
    assert loaded.scenarios[1].should_trigger is True
    assert loaded.scenarios[0].turns[1] == "А за 5 років?"


def test_numbers_grounded_defaults() -> None:
    assertion = NumbersGrounded(type="numbers_grounded")
    assert assertion.tolerance_rel == 0.02
    assert assertion.tolerance_abs == 0.5
    assert assertion.ignore_below == 10
    assert assertion.summary_glob == "**/summary.json"


def test_unknown_assertion_type_is_rejected(tmp_path: Path) -> None:
    data = json.loads(json.dumps(VALID))
    data["scenarios"][0]["assertions"].append({"type": "teleport", "where": "x"})
    with pytest.raises(ScenarioLoadError, match=r"teleport|union_tag_invalid|type"):
        load_scenarios(_write(tmp_path, data))


def test_unknown_field_in_assertion_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ScenarioFile.model_validate(
            {
                "skill_name": "x",
                "scenarios": [
                    {
                        "id": "a",
                        "name": "a",
                        "turns": ["t"],
                        "assertions": [{"type": "max_turns", "n": 3, "extra": 1}],
                    }
                ],
            }
        )


def test_summary_field_requires_exactly_one_matcher() -> None:
    with pytest.raises(ValidationError):
        SummaryField(type="summary_field", path="a.b")
    with pytest.raises(ValidationError):
        SummaryField(type="summary_field", path="a.b", equals="x", regex="y")
    assert SummaryField(type="summary_field", path="a.b", equals=False).equals is False


def test_duplicate_scenario_ids_are_rejected(tmp_path: Path) -> None:
    data = json.loads(json.dumps(VALID))
    data["scenarios"][1]["id"] = data["scenarios"][0]["id"]
    with pytest.raises(ScenarioLoadError, match="duplicate scenario ids"):
        load_scenarios(_write(tmp_path, data))


def test_duplicate_rubric_ids_are_rejected() -> None:
    with pytest.raises(ValidationError, match="rubric ids must be unique"):
        Scenario(
            id="a",
            name="a",
            turns=["t"],
            rubric=[{"id": "x", "criterion": "one"}, {"id": "x", "criterion": "two"}],
        )


def test_bad_slug_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Scenario(id="Not A Slug", name="a", turns=["t"])


def test_empty_turns_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Scenario(id="a", name="a", turns=[])


def test_missing_file_gives_readable_error(tmp_path: Path) -> None:
    with pytest.raises(ScenarioLoadError, match="not found"):
        load_scenarios(tmp_path / "nope.json")


def test_invalid_json_gives_readable_error(tmp_path: Path) -> None:
    path = tmp_path / "evals.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ScenarioLoadError, match="not valid JSON"):
        load_scenarios(path)


def test_bom_is_tolerated(tmp_path: Path) -> None:
    path = tmp_path / "evals.json"
    path.write_text(json.dumps(VALID), encoding="utf-8-sig")
    assert len(load_scenarios(path).scenarios) == 2
