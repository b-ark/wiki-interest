"""Scenario schema and loader for ``evals.json``.

A scenario is one conversation with the agent (one or more user turns) plus the checks that
decide whether the agent did the right thing. Checks come in two kinds: typed ``assertions``
graded by deterministic code (see :mod:`skill_evals.graders.deterministic`) and free-text
``rubric`` criteria graded by an LLM judge. The schema is strict (``extra="forbid"``) so a typo
in a scenario file fails at load time rather than silently never being checked.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

__all__ = [
    "AnswerContains",
    "AnswerNotContains",
    "Assertion",
    "CaveatsRelayed",
    "ClarificationAsked",
    "FileExists",
    "MaxCostUsd",
    "MaxTurns",
    "NoToolCalled",
    "NumbersGrounded",
    "PdfPages",
    "RubricItem",
    "Scenario",
    "ScenarioFile",
    "ScenarioLoadError",
    "SummaryField",
    "ToolCalled",
    "load_scenarios",
]

_SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


class _Strict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class FileExists(_Strict):
    """At least ``min_count`` files matching ``glob`` exist among the copied artifacts."""

    type: Literal["file_exists"]
    glob: str
    min_count: int = Field(default=1, ge=1)


class PdfPages(_Strict):
    """Every PDF matching ``glob`` has at most ``max_pages`` pages (the one-page report rule)."""

    type: Literal["pdf_pages"]
    glob: str = "**/report.pdf"
    max_pages: int = Field(default=1, ge=1)


class NumbersGrounded(_Strict):
    """Every number in the final answer appears among the numeric leaves of ``summary.json``.

    Years and small integers are ignored because they are not claims about the data.
    Percentages in the answer are also compared against fractions in the summary times 100.
    """

    type: Literal["numbers_grounded"]
    summary_glob: str = "**/summary.json"
    tolerance_rel: float = Field(default=0.02, ge=0)
    tolerance_abs: float = Field(default=0.5, ge=0)
    ignore_below: int = Field(default=10, ge=0)


class AnswerContains(_Strict):
    """The final answer matches the regex ``patterns`` (``any`` or ``all`` of them)."""

    type: Literal["answer_contains"]
    patterns: list[str] = Field(min_length=1)
    mode: Literal["any", "all"] = "all"


class AnswerNotContains(_Strict):
    """The final answer matches none of the regex ``patterns``."""

    type: Literal["answer_not_contains"]
    patterns: list[str] = Field(min_length=1)


class ToolCalled(_Strict):
    """Some tool call in the trajectory matches ``pattern`` (tool name or command text)."""

    type: Literal["tool_called"]
    pattern: str


class NoToolCalled(_Strict):
    """No tool call in the trajectory matches ``pattern``."""

    type: Literal["no_tool_called"]
    pattern: str


class MaxTurns(_Strict):
    """The agent used at most ``n`` model turns across the whole conversation."""

    type: Literal["max_turns"]
    n: int = Field(ge=1)


class MaxCostUsd(_Strict):
    """The conversation cost at most ``value`` USD according to the provider."""

    type: Literal["max_cost_usd"]
    value: float = Field(gt=0)


class SummaryField(_Strict):
    """A field of ``summary.json`` (dotted path, ``a.b[0].c`` or ``a.b.0.c``) has a value.

    Exactly one of ``equals`` or ``regex`` must be given.
    """

    type: Literal["summary_field"]
    summary_glob: str = "**/summary.json"
    path: str
    equals: str | int | float | bool | None = None
    regex: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> SummaryField:
        if (self.regex is None) == (self.equals is None):
            msg = "summary_field needs exactly one of 'equals' or 'regex'"
            raise ValueError(msg)
        return self


class CaveatsRelayed(_Strict):
    """When reliability is not ``high``, the answer repeats at least ``min_reasons`` check messages.

    Matching is fuzzy (token overlap) because agents paraphrase; the threshold lives in the
    grader and is documented there.
    """

    type: Literal["caveats_relayed"]
    summary_glob: str = "**/summary.json"
    min_reasons: int = Field(default=1, ge=1)


class ClarificationAsked(_Strict):
    """The agent asked the user a question and did not produce ``report.pdf``."""

    type: Literal["clarification_asked"]


Assertion = Annotated[
    FileExists
    | PdfPages
    | NumbersGrounded
    | AnswerContains
    | AnswerNotContains
    | ToolCalled
    | NoToolCalled
    | MaxTurns
    | MaxCostUsd
    | SummaryField
    | CaveatsRelayed
    | ClarificationAsked,
    Field(discriminator="type"),
]


class RubricItem(_Strict):
    """One property the LLM judge decides independently (one call per criterion)."""

    id: str = Field(pattern=_SLUG.pattern)
    criterion: str = Field(min_length=1)


class Scenario(_Strict):
    """One conversation with the agent and the checks applied to it."""

    id: str = Field(pattern=_SLUG.pattern)
    name: str
    tags: list[str] = Field(default_factory=list)
    turns: list[str] = Field(min_length=1)
    expected: str = ""
    assertions: list[Assertion] = Field(default_factory=list)
    rubric: list[RubricItem] = Field(default_factory=list)
    should_trigger: bool = True

    @field_validator("rubric")
    @classmethod
    def _unique_rubric_ids(cls, rubric: list[RubricItem]) -> list[RubricItem]:
        ids = [item.id for item in rubric]
        if len(ids) != len(set(ids)):
            msg = "rubric ids must be unique within a scenario"
            raise ValueError(msg)
        return rubric


class ScenarioFile(_Strict):
    """Top-level shape of ``evals.json``."""

    skill_name: str
    scenarios: list[Scenario] = Field(min_length=1)

    @field_validator("scenarios")
    @classmethod
    def _unique_ids(cls, scenarios: list[Scenario]) -> list[Scenario]:
        ids = [s.id for s in scenarios]
        if len(ids) != len(set(ids)):
            dupes = sorted({i for i in ids if ids.count(i) > 1})
            msg = f"duplicate scenario ids: {dupes}"
            raise ValueError(msg)
        return scenarios


class ScenarioLoadError(ValueError):
    """The scenario file is missing, not JSON, or does not match the schema."""


def load_scenarios(path: Path) -> ScenarioFile:
    """Load and validate ``evals.json``.

    Args:
        path: Path to the scenario file.

    Returns:
        The validated scenario set, in file order.

    Raises:
        ScenarioLoadError: With a readable message when the file cannot be used.
    """
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        msg = f"scenario file not found: {path}"
        raise ScenarioLoadError(msg) from exc
    except json.JSONDecodeError as exc:
        msg = f"scenario file is not valid JSON: {path}: {exc}"
        raise ScenarioLoadError(msg) from exc
    try:
        return ScenarioFile.model_validate(raw)
    except ValidationError as exc:
        msg = f"scenario file does not match the schema: {path}\n{exc}"
        raise ScenarioLoadError(msg) from exc
