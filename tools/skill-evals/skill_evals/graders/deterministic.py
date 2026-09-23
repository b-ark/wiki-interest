"""Deterministic graders: one function per assertion type.

Each grader looks only at evidence the runner already saved (the trajectory and the copied
artifacts under the case directory) and returns pass/fail with a human-readable evidence
string. Nothing here calls a model or the network, so the same case always grades the same.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from skill_evals.graders.numbers import ground_numbers, summary_numeric_leaves
from skill_evals.providers.base import Trajectory
from skill_evals.scenarios import (
    AnswerContains,
    AnswerNotContains,
    Assertion,
    CaveatsRelayed,
    ClarificationAsked,
    FileExists,
    MaxCostUsd,
    MaxTurns,
    NarrativeAccepted,
    NoToolCalled,
    NumbersGrounded,
    PdfPages,
    SummaryField,
    ToolCalled,
)

__all__ = ["GradeContext", "GradeOutcome", "describe", "grade", "resolve_path"]

_CAVEAT_TOKEN_MIN_LEN = 4
_CAVEAT_OVERLAP = 0.5
_NON_HIGH = {"medium", "low"}
_CAVEAT_STATUSES = {"warn", "fail"}
_CHAT_BRIEF = "chat_brief.md"
"""Written next to ``summary.json`` when the skill accepts the agent's report text."""
_STATUS_RE = re.compile(r'"status"\s*:\s*"(\w+)"|^\s*status\s*:\s*(\w+)', re.MULTILINE)
"""The status of a render: JSON as printed, or the list PowerShell makes of it when the agent
pipes the output through ``ConvertFrom-Json`` (verified 2026-09-23)."""
_RUN_ID_RE = re.compile(r"\d{8}-\d{6}-[0-9a-f]{4}")
"""A run directory's name (``20260923-171010-345b``). Taken from the command first: PowerShell
wraps long paths in its output, so a path read back from there may be split."""


@dataclass(frozen=True, slots=True)
class GradeContext:
    """Evidence available to graders: the copied artifacts and the parsed trajectory."""

    case_dir: Path
    trajectory: Trajectory

    def files(self, pattern: str) -> list[Path]:
        """Artifacts matching ``pattern`` under the case directory, sorted for determinism."""
        return sorted(p for p in self.case_dir.glob(pattern) if p.is_file())

    def summaries(self, pattern: str) -> list[dict[str, object]]:
        """Parsed ``summary.json`` documents matching ``pattern`` (unparsable files skipped)."""
        docs: list[dict[str, object]] = []
        for path in self.files(pattern):
            try:
                loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(loaded, dict):
                docs.append(loaded)
        return docs

    def latest_summary(self, pattern: str) -> dict[str, object] | None:
        """The most recently written summary matching ``pattern``, or ``None``.

        The final answer relays the last pipeline run. Earlier runs in the same case may be
        abandoned attempts (verified 2026-09-23: a query that matched no article anywhere,
        retried with better wording), and their caveats must not be demanded of the answer.
        """
        found = self.latest_summary_file(pattern)
        return found[1] if found else None

    def latest_summary_file(self, pattern: str) -> tuple[Path, dict[str, object]] | None:
        """Like :meth:`latest_summary`, with the path of the file it was read from."""
        paths = sorted(self.files(pattern), key=lambda p: (p.stat().st_mtime, str(p)))
        for path in reversed(paths):
            try:
                loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(loaded, dict):
                return path, loaded
        return None


@dataclass(frozen=True, slots=True)
class GradeOutcome:
    """What a grader concluded and why."""

    text: str
    passed: bool
    evidence: str


def describe(assertion: Assertion) -> str:
    """Human-readable statement of what the assertion checks."""
    fields = assertion.model_dump(exclude={"type"})
    args = ", ".join(f"{k}={v!r}" for k, v in fields.items())
    return f"{assertion.type}({args})"


def grade(assertion: Assertion, ctx: GradeContext) -> GradeOutcome:  # noqa: PLR0911, PLR0912 - dispatcher
    """Dispatch to the grader for the assertion's type."""
    match assertion:
        case FileExists():
            return _file_exists(assertion, ctx)
        case PdfPages():
            return _pdf_pages(assertion, ctx)
        case NumbersGrounded():
            return _numbers_grounded(assertion, ctx)
        case AnswerContains():
            return _answer_contains(assertion, ctx)
        case AnswerNotContains():
            return _answer_not_contains(assertion, ctx)
        case ToolCalled():
            return _tool_called(assertion, ctx)
        case NoToolCalled():
            return _no_tool_called(assertion, ctx)
        case MaxTurns():
            return _max_turns(assertion, ctx)
        case MaxCostUsd():
            return _max_cost(assertion, ctx)
        case SummaryField():
            return _summary_field(assertion, ctx)
        case CaveatsRelayed():
            return _caveats_relayed(assertion, ctx)
        case ClarificationAsked():
            return _clarification_asked(assertion, ctx)
        case NarrativeAccepted():
            return _narrative_accepted(assertion, ctx)


def _outcome(assertion: Assertion, passed: bool, evidence: str) -> GradeOutcome:
    return GradeOutcome(text=describe(assertion), passed=passed, evidence=evidence)


def _file_exists(a: FileExists, ctx: GradeContext) -> GradeOutcome:
    found = ctx.files(a.glob)
    names = ", ".join(str(p.relative_to(ctx.case_dir)) for p in found[:5])
    return _outcome(a, len(found) >= a.min_count, f"{len(found)} file(s) match: {names or '-'}")


def _pdf_pages(a: PdfPages, ctx: GradeContext) -> GradeOutcome:
    found = ctx.files(a.glob)
    if not found:
        return _outcome(a, False, "no PDF matches the glob")
    counts: list[str] = []
    passed = True
    for path in found:
        try:
            pages = len(PdfReader(path).pages)
        except Exception as exc:
            counts.append(f"{path.name}: unreadable ({exc})")
            passed = False
            continue
        counts.append(f"{path.name}: {pages} page(s)")
        passed = passed and pages <= a.max_pages
    return _outcome(a, passed, "; ".join(counts))


def _numbers_grounded(a: NumbersGrounded, ctx: GradeContext) -> GradeOutcome:
    docs = ctx.summaries(a.summary_glob)
    if not docs:
        return _outcome(a, False, "no summary.json to ground numbers against")
    leaves = [leaf for doc in docs for leaf in summary_numeric_leaves(doc)]
    report = ground_numbers(
        ctx.trajectory.final_answer,
        leaves,
        tolerance_rel=a.tolerance_rel,
        tolerance_abs=a.tolerance_abs,
        ignore_below=a.ignore_below,
    )
    missing = ", ".join(n.text for n in report.ungrounded[:10])
    evidence = f"{len(report.checked)} number(s) checked against {len(docs)} summary file(s)"
    if report.ungrounded:
        evidence += f"; not found: {missing}"
    return _outcome(a, report.passed, evidence)


def _answer_contains(a: AnswerContains, ctx: GradeContext) -> GradeOutcome:
    answer = ctx.trajectory.final_answer
    hits = [p for p in a.patterns if re.search(p, answer, flags=re.IGNORECASE | re.DOTALL)]
    passed = len(hits) == len(a.patterns) if a.mode == "all" else bool(hits)
    return _outcome(a, passed, f"matched {len(hits)}/{len(a.patterns)} pattern(s): {hits}")


def _answer_not_contains(a: AnswerNotContains, ctx: GradeContext) -> GradeOutcome:
    answer = ctx.trajectory.final_answer
    hits = [p for p in a.patterns if re.search(p, answer, flags=re.IGNORECASE | re.DOTALL)]
    return _outcome(
        a, not hits, f"forbidden pattern(s) present: {hits}" if hits else "none present"
    )


def _matching_calls(pattern: str, ctx: GradeContext) -> list[str]:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    return [c.signature() for c in ctx.trajectory.tool_calls if regex.search(c.signature())]


def _tool_called(a: ToolCalled, ctx: GradeContext) -> GradeOutcome:
    hits = _matching_calls(a.pattern, ctx)
    sample = hits[0][:160] if hits else "-"
    return _outcome(a, bool(hits), f"{len(hits)} matching call(s); first: {sample}")


def _no_tool_called(a: NoToolCalled, ctx: GradeContext) -> GradeOutcome:
    hits = _matching_calls(a.pattern, ctx)
    sample = hits[0][:160] if hits else "-"
    return _outcome(a, not hits, f"{len(hits)} matching call(s); first: {sample}")


def _max_turns(a: MaxTurns, ctx: GradeContext) -> GradeOutcome:
    turns = ctx.trajectory.num_turns
    return _outcome(a, turns <= a.n, f"{turns} turn(s), budget {a.n}")


def _max_cost(a: MaxCostUsd, ctx: GradeContext) -> GradeOutcome:
    cost = ctx.trajectory.cost_usd
    if cost is None:
        return _outcome(a, True, "provider reported no cost; nothing to compare")
    return _outcome(a, cost <= a.value, f"cost {cost:.4f} USD, budget {a.value:.4f}")


def resolve_path(data: object, path: str) -> object:
    """Walk ``data`` by a dotted path; ``a.b[0].c`` and ``a.b.0.c`` are equivalent.

    Raises:
        KeyError: When a segment does not exist.
    """
    node = data
    for segment in re.split(r"\.|\[|\]", path):
        if not segment:
            continue
        if isinstance(node, list):
            node = node[int(segment)]
        elif isinstance(node, dict) and segment in node:
            node = node[segment]
        else:
            raise KeyError(segment)
    return node


def _summary_field(a: SummaryField, ctx: GradeContext) -> GradeOutcome:
    docs = ctx.summaries(a.summary_glob)
    if not docs:
        return _outcome(a, False, "no summary.json found")
    observed: list[str] = []
    for doc in docs:
        try:
            value = resolve_path(doc, a.path)
        except (KeyError, IndexError, ValueError):
            observed.append("<missing>")
            continue
        observed.append(json.dumps(value, ensure_ascii=False))
        if _field_matches(a, value):
            return _outcome(a, True, f"{a.path} = {observed[-1]}")
    return _outcome(a, False, f"{a.path} observed: {observed}")


def _field_matches(a: SummaryField, value: object) -> bool:
    if a.regex is not None:
        return re.search(a.regex, json.dumps(value, ensure_ascii=False).strip('"')) is not None
    if isinstance(a.equals, bool) or isinstance(value, bool):
        return a.equals == value
    if isinstance(a.equals, int | float) and isinstance(value, int | float):
        return float(a.equals) == float(value)
    return a.equals == value


def _caveats_relayed(a: CaveatsRelayed, ctx: GradeContext) -> GradeOutcome:
    found = ctx.latest_summary_file(a.summary_glob)
    if found is None:
        return _outcome(a, False, "no summary.json found")
    path, latest = found
    messages = _caveat_messages([latest])
    if not messages:
        return _outcome(a, True, "reliability is high everywhere; nothing to relay")
    answer = ctx.trajectory.final_answer
    if _report_language(latest) != "en":
        return _caveats_in_other_language(a, path.parent, latest, answer)
    relayed = [m for m in messages if _is_relayed(m, answer)]
    evidence = f"{len(relayed)}/{len(messages)} caveat(s) relayed (need {a.min_reasons})"
    if relayed:
        evidence += f"; e.g. {relayed[0][:100]!r}"
    return _outcome(a, len(relayed) >= a.min_reasons, evidence)


def _report_language(summary: dict[str, object]) -> str:
    """The report language of a summary; English when the summary does not say."""
    try:
        return str(resolve_path(summary, "request.report.language"))
    except KeyError:
        return "en"


def _caveats_in_other_language(
    a: CaveatsRelayed, run_dir: Path, summary: dict[str, object], answer: str
) -> GradeOutcome:
    """Caveats of a non-English report, whose check messages are English template text.

    An accepted report text has passed the skill's caveat check (every caveat declared and its
    edition named), so relaying that text relays the caveats. After a fallback there is no such
    text; the answer must then at least name every edition whose reliability is not high.
    """
    brief = run_dir / _CHAT_BRIEF
    if brief.is_file():
        text = brief.read_text(encoding="utf-8-sig")
        passed = _is_relayed(text, answer)
        return _outcome(a, passed, f"accepted text {'relayed' if passed else 'not relayed'}")
    editions = _flagged_editions(summary)
    missing = [e for e in editions if not _names_edition(e, answer)]
    evidence = (
        f"no accepted text; {len(editions) - len(missing)}/{len(editions)} flagged edition(s) named"
    )
    return _outcome(a, not missing, evidence + (f"; missing {missing}" if missing else ""))


def _flagged_editions(summary: dict[str, object]) -> list[str]:
    blocks = summary.get("reliability")
    return sorted(
        {
            str(block.get("project"))
            for block in (blocks if isinstance(blocks, list) else [])
            if isinstance(block, dict) and block.get("level") in _NON_HIGH
        }
    )


def _names_edition(project: str, answer: str) -> bool:
    """``pl.wikipedia`` is named as itself or by its language code (``pl``)."""
    code = project.split(".", maxsplit=1)[0]
    return (
        project in answer or re.search(rf"(?<![\w-]){re.escape(code)}(?![\w-])", answer) is not None
    )


def _narrative_accepted(a: NarrativeAccepted, ctx: GradeContext) -> GradeOutcome:
    regex = re.compile(a.pattern, flags=re.IGNORECASE)
    final: dict[str, str] = {}
    for call in ctx.trajectory.tool_calls:
        command = call.command or ""
        if not regex.search(command) or "--narrative" not in command:
            continue
        output = call.result or ""
        status = _STATUS_RE.search(output)
        if status is None:  # a crash or malformed file: nothing was decided about the text
            continue
        run_id = _RUN_ID_RE.search(command) or _RUN_ID_RE.search(output)
        final[run_id.group(0) if run_id else command] = status.group(1) or status.group(2)
    if not final:
        return _outcome(a, False, "no render with the agent's text")
    accepted = sum(1 for status in final.values() if status == "accepted")
    others = sorted({s for s in final.values() if s != "accepted"})
    evidence = f"{accepted}/{len(final)} rendered run(s) accepted"
    return _outcome(a, accepted == len(final), evidence + (f"; also {others}" if others else ""))


def _caveat_messages(docs: list[dict[str, object]]) -> list[str]:
    """Check messages (and reason keys) of non-passing checks where reliability is not high."""
    messages: list[str] = []
    for doc in docs:
        blocks = doc.get("reliability")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict) or block.get("level") not in _NON_HIGH:
                continue
            checks = block.get("checks")
            for check in checks if isinstance(checks, list) else []:
                if isinstance(check, dict) and check.get("status") in _CAVEAT_STATUSES:
                    messages.append(f"{check.get('message', '')} {check.get('reason_key', '')}")
    return messages


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) >= _CAVEAT_TOKEN_MIN_LEN}


def _is_relayed(message: str, answer: str) -> bool:
    """Fuzzy containment: at least half of the message's content words appear in the answer."""
    words = _tokens(message)
    if not words:
        return False
    return len(words & _tokens(answer)) / len(words) >= _CAVEAT_OVERLAP


def _clarification_asked(a: ClarificationAsked, ctx: GradeContext) -> GradeOutcome:
    answer = ctx.trajectory.final_answer
    asked = "?" in answer or "？" in answer
    requested = any(re.search(pattern, answer) for pattern in a.request_patterns)
    pdfs = ctx.files("**/report.pdf")
    how = "question mark" if asked else "request" if requested else "no question or request"
    asked = asked or requested
    evidence = f"{how}; {len(pdfs)} report.pdf"
    return _outcome(a, asked and not pdfs, evidence)
