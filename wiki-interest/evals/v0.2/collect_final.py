"""Copy a Haiku run's PDFs, chat answers, grades and tool-call logs into ``<out>/``.

Usage (from the skill directory, after ``skill-evals run ... -n <run>``):
    uv run python evals/v0.2/collect_final.py ../tools/skill-evals/runs/<run> <out> [scenario ...]

``<out>`` is a folder next to this script (``final-run2``, ``stage18``); the first repetition
of each scenario is kept, of the scenarios named or of all; ``<scenario>:<rep>`` keeps another.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_RESULT = 600
"""Characters of each tool result kept in the log."""


def main(run: Path, name: str, scenarios: list[str]) -> int:
    """Collect the cases of ``run`` (``scenarios``, or all) into ``<name>/<case>/``."""
    reps = dict(item.partition(":")[::2] for item in scenarios)
    for case in sorted((run / "cases").iterdir()):
        if scenarios and case.name not in reps:
            continue
        number = reps.get(case.name) or "1"
        rep = case / f"rep-{number}"
        out = HERE / name / case.name
        out.mkdir(parents=True, exist_ok=True)
        sandbox = run / "sandboxes" / f"{case.name}-rep-{number}"
        pdfs = sorted(sandbox.glob("wiki-interest-runs/**/report.pdf"))
        for n, pdf in enumerate(pdfs, start=1):
            suffix = "" if len(pdfs) == 1 else f"-{n}"
            shutil.copy(pdf, out / f"report{suffix}.pdf")
            brief = pdf.parent / "chat_brief.md"
            if brief.is_file():
                shutil.copy(brief, out / f"chat_answer{suffix}.md")
            narrative = sandbox / "narrative.json"
            if narrative.is_file():
                shutil.copy(narrative, out / "narrative.json")
        shutil.copy(rep / "grades.json", out / "grades.json")
        (out / "tool_calls.md").write_text(
            _tool_log(rep / "events.jsonl"), encoding="utf-8", newline="\n"
        )
        sys.stdout.write(f"{out}\n")
    return 0


def _tool_log(events: Path) -> str:
    """Each user turn, tool call and its result, and the final answer, as Markdown."""
    lines = [f"# Tool calls: {events.parent.parent.name}", ""]
    for raw in events.read_text(encoding="utf-8").splitlines():
        event = json.loads(raw)
        kind = event.get("type")
        if kind == "harness_turn":
            lines += [f"## User turn {event['index'] + 1}", "", f"> {event['prompt']}", ""]
        elif kind == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_use":
                    payload = json.dumps(block.get("input", {}), ensure_ascii=False)
                    lines += [f"- **{block.get('name')}** `{payload[:800]}`"]
                elif block.get("type") == "text" and block.get("text", "").strip():
                    lines += ["", "**Assistant:**", "", block["text"].strip(), ""]
        elif kind == "user":
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    content = block.get("content")
                    text = (
                        content
                        if isinstance(content, str)
                        else " ".join(
                            c.get("text", "") for c in content or [] if isinstance(c, dict)
                        )
                    )
                    lines += [f"  - result: `{text[:_RESULT].replace(chr(10), ' ')}`"]
        elif kind == "result":
            lines += [
                "",
                f"Turns: {event.get('num_turns')}, cost: {event.get('total_cost_usd')} USD, "
                f"duration: {event.get('duration_ms')} ms.",
            ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), sys.argv[2], sys.argv[3:]))
