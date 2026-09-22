# wiki-interest

An [Agent Skill](https://agentskills.io/specification) that helps B2C product teams decide which
topics to develop and which languages to launch in, using Wikipedia pageview statistics as a
demand signal. The agent resolves a topic to Wikipedia articles across language editions, pulls
pageview time series, normalises and tests them for trend, draws charts and writes a one-page
report with an explicit reliability assessment.

## Repository layout

| Path | What it is |
|---|---|
| [`wiki-interest/`](wiki-interest/) | The skill itself: `SKILL.md`, the `wiki_interest` Python package, scripts, references, and tests. Self-contained and installable on its own. |
| [`tools/skill-evals/`](tools/skill-evals/) | Development-only harness that runs the skill through a real agent (headless Claude Code on Haiku 4.5, or OpenRouter models), grades the outputs and compares `SKILL.md` versions. Not part of the skill package. |
| [`task.md`](task.md) | The original assignment. |

Agent quality is measured, not assumed: [`wiki-interest/evals/`](wiki-interest/evals/)
describes the scenarios, how answers are graded, and holds the results of real runs on
Claude Haiku 4.5.

## Quick start

```bash
cd wiki-interest
./scripts/setup.sh                                  # or scripts/setup.ps1; installs uv if missing
uv run scripts/doctor.py                            # checks Python, fonts, cache, the three APIs
uv run scripts/run.py assets/examples/assess-astronomy-uk.json
```

The last command writes `wiki-interest-runs/<session>/<run-id>/` with `summary.md`,
`summary.json`, a one-page `report.pdf`, `report.md` and charts. To use it as a skill, place
the `wiki-interest/` directory where your agent loads skills (for Claude Code:
`~/.claude/skills/` or `<project>/.claude/skills/`).

See [`wiki-interest/README.md`](wiki-interest/README.md) for usage and the architecture overview.

## Development

Quality gates run locally via pre-commit and in CI on Ubuntu and Windows, Python 3.12 and 3.14:

```bash
pre-commit install                      # once
cd wiki-interest && uv sync             # dev dependencies included by default
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports                     # architecture boundaries (domain never imports adapters)
uv run pytest --cov
uv run agentskills validate ../wiki-interest   # Agent Skills spec compliance (skills-ref package)
```

## How AI tools were used, and how their output was checked

Most of the code was written with Claude Code, including parallel sub-agents. Nothing was
accepted on the strength of the model's own report. The checks, in the order they catch
problems:

1. **Contracts first.** Domain models, ports and the JSON schemas were written and reviewed
   before any parallel work. Four agents then built the domain, the API adapters, the
   renderers and the evaluation harness in isolated git worktrees against those frozen
   contracts; each report was read and every branch was merged only with all gates green.
2. **Mechanical gates on every commit:** ruff (including docstring rules), mypy `--strict`,
   import-linter for the layer boundaries, pytest with coverage (about 98 %), and the Agent
   Skills validator. They run in pre-commit and in CI on Ubuntu and Windows.
3. **Independent references for numerical code.** The Mann-Kendall test and Theil-Sen slope
   are implemented without dependencies and checked in tests against `pymannkendall` and
   `scipy` on seeded series; metrics are tested on synthetic series with known answers and with
   property-based tests.
4. **Recorded reality.** Adapter tests replay real Wikimedia, Wikidata and MediaWiki responses
   recorded on 2026-09-22; a few live smoke tests run on demand.
5. **Running the assignment's own questions on live data** and reading the output as a
   founder would. This caught what tests could not: a Polish search fallback that returned an
   article on oxidative stress for "intermittent fasting", citation identifiers (ISSN, DOI)
   entering topic bundles, fifteen related articles outweighing the main one, a Hogwarts
   school subject competing with the science of astronomy, and a headline calling a decline
   "fastest growth". Each became a fix with a regression test.
6. **Checking the graders before trusting them.** `skill-evals oracle` grades an ideal answer
   and an empty one for every scenario; the first must pass everything, the second must fail
   everything that requires work.
7. **Reading agent transcripts, not just scores.** The first Haiku run passed 8 of 9 checks, but
   its transcript showed ten turns spent on a denied file write and a PowerShell byte-order mark.
   Fixing the skill and the harness brought the same task to 9 of 9 checks in six turns.
