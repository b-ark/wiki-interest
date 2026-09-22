# wiki-interest

An [Agent Skill](https://agentskills.io/specification) that helps B2C product teams decide which
topics to develop and which languages to launch in, using Wikipedia pageview statistics as a
demand signal. The agent resolves a topic to Wikipedia articles across language editions, pulls
pageview time series, normalises and tests them for trend, draws charts and writes a one-page
report with an explicit reliability assessment.

## Repository layout

| Path | What it is |
|---|---|
| [`wiki-interest/`](wiki-interest/) | The skill itself: `SKILL.md`, the `wiki_interest` Python package, scripts, references, tests, and the eval scenarios with their result summaries. Self-contained and installable on its own. |
| [`tools/skill-evals/`](tools/skill-evals/) | Development-only harness that runs the skill through a real agent (headless Claude Code on Haiku 4.5, or OpenRouter models), grades the outputs and compares `SKILL.md` versions. Not part of the skill package. |
| [`task.md`](task.md) | The original assignment. |

## Quick start

```bash
cd wiki-interest
./scripts/setup.sh          # or scripts/setup.ps1 on Windows; installs uv if missing and syncs the env
uv run pytest               # run the test suite
```

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
