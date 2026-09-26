"""Run the v0.2 reference case and keep its PDF and key fields for the changelog.

The reference case of the v0.2.0 work: veganism (Q181138) in the Russian and Czech
Wikipedias, 2024-09 – 2026-08, report in Ukrainian. Each phase reruns it with the code's own
text (no agent) and keeps ``phase-<N>/report.pdf`` and ``phase-<N>/key-fields.json``.

Usage (from the skill directory):
    uv run python evals/v0.2/run_reference.py <phase>
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent.parent
KEYS = ("analysis_window", "context_range", "verdicts", "recommendations")
"""Summary fields the changelog quotes; those a phase has not added yet are left out."""


def main(phase: str) -> int:
    """Run the reference request and copy its outputs to ``phase-<phase>/``."""
    out = HERE / f"phase-{phase}"
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v02-ref-") as work:
        request = Path(work) / "request.json"
        shutil.copy(HERE / "reference-request.json", request)
        done = subprocess.run(
            ["uv", "run", "--project", str(SKILL), str(SKILL / "scripts" / "run.py"), str(request)],
            cwd=work,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if done.returncode != 0:
            sys.stderr.write(done.stdout + done.stderr)
            return done.returncode
        result = json.loads(done.stdout)
        run_dir = Path(result["run_dir"])
        shutil.copy(run_dir / "report.pdf", out / "report.pdf")
        summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        facts = json.loads((run_dir / "facts.json").read_text(encoding="utf-8"))
        fields: dict[str, object] = {"headline": summary["verdict"]["headline"]}
        fields.update({k: summary[k] for k in KEYS if k in summary})
        fields["observations"] = {
            o["id"]: o["statement"]
            for o in facts["observations"]
            if o["id"].split(":")[0]
            in (
                "headline",
                "trend",
                "trust",
                "vs_edition",
                "editions",
                "decision",
                "recommendation",
            )
        }
        (out / "key-fields.json").write_text(
            json.dumps(fields, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    sys.stdout.write(f"{out / 'report.pdf'}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "0"))
