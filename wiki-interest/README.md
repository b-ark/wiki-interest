# wiki-interest (skill)

An Agent Skill that turns Wikipedia pageview statistics into evidence for product decisions:
whether interest in a topic is growing in a language Wikipedia, how languages compare, which
audiences to research next, and how far each answer can be trusted. Version 0.2.0.

`SKILL.md` is what the agent reads. This file is for people installing, configuring or
changing the skill.

## How an agent uses it

```bash
uv run --project <skill> <skill>/scripts/run.py request.json          # measure and decide
uv run --project <skill> <skill>/scripts/render.py <run_dir> --narrative narrative.json   # check the text, render
```

1. The agent writes `request.json` (question type, the topic in the user's words, language
   Wikipedias, optional period and report options; [`references/request-schema.md`](references/request-schema.md)).
2. `run.py` resolves the topic, reads the views, decides the verdicts, the trust and the
   recommendation, and writes `facts.json`: the observations the text may use, the rules
   for writing it and a worked example. When the topic is ambiguous, not found or missing
   in some language, it stops before measuring and says what to ask (exit code 3).
3. The agent writes `narrative.json` in the user's language, citing observations.
4. `render.py` checks the text (numbers, citations, required observations, wording) and
   either renders the PDF and returns the chat answer, or returns the problems to fix. After
   a second rejection the report keeps the code's own text.

A follow-up edits the same `request.json` under the same `session` and runs again; cached
data make it fast, and its chat answer says what changed.

## What a run writes

`wiki-interest-runs/<session>/<run-id>/` in the current directory (reports belong to the
user's project, not to the skill directory, which may be read-only):

| File | Contents |
|---|---|
| `report.pdf` | One page: headline, the attention share over the context with each language's trend line, views by calendar year, the story, what it means with the recommendation and the trust line, limits. `report.appendix: true` adds a page on the method. |
| `summary.json` | Everything decided: the analysis window and context, a verdict per language with its trust and reasons, the recommendation with what decided it and the next check, observations, provenance. |
| `summary.md` | The same, readable. |
| `facts.json` | What the agent reads to write its text. |
| `method.md` | How every number was computed, with the thresholds in force for this run. |
| `charts/` | Every chart as SVG and PNG. |
| `chat_brief.md` | The chat answer, built from the checked text (after `render.py`). |

## Configuration

Every setting has a default and can be overridden with an environment variable
`WIKI_INTEREST_<FIELD>` ([`wiki_interest/config.py`](wiki_interest/config.py)); the trust
thresholds use `WIKI_INTEREST_TRUST_<NAME>` (`TrustSettings` in
[`domain/trust.py`](wiki_interest/domain/trust.py)). The ones most often touched:

| Variable | Default | Meaning |
|---|---|---|
| `WIKI_INTEREST_CACHE_PATH` | `<skill>/.cache/http.sqlite` | HTTP cache, shared across projects |
| `WIKI_INTEREST_RUNS_DIR` | `./wiki-interest-runs` | Where runs are written |
| `WIKI_INTEREST_CLOSED_PERIOD_TTL_S` | none (forever) | Cache lifetime of series in closed months |
| `WIKI_INTEREST_OPEN_PERIOD_TTL_S` | 86400 | Cache lifetime of series that reach the current month |
| `WIKI_INTEREST_USER_AGENT` | `wiki-interest/<version> (<project URL>)` | Sent to Wikimedia, as its policy requires |
| `WIKI_INTEREST_TRUST_STABLE_PCT_PER_YEAR`, `..._SPLIT_STEP` and others | 10, 1.25 | Verdict and trust thresholds (`TrustSettings`) |

`scripts/doctor.py` checks Python, fonts, the cache and the three APIs, and prints what to
fix.

## Layout

```
wiki-interest/
├── SKILL.md            # agent-facing instructions (Agent Skills format)
├── wiki_interest/      # Python package
│   ├── domain/         # pure calculations: series, verdicts and trust, observations, seasons, steps
│   ├── application/    # use-cases: resolution, loading, window, recommendation, facts, text checks
│   ├── ports/          # Protocol interfaces to the outside world
│   ├── adapters/       # Wikimedia REST, Wikidata, MediaWiki, SQLite cache, charts, PDF
│   ├── contracts/      # pydantic schemas: request, summary, facts, narrative, charts
│   ├── i18n/           # report interface in English, Russian and Ukrainian; names of 40 Wikipedias
│   └── cli/            # typer commands used by scripts/
├── scripts/            # thin entry points the agent runs: run.py, render.py, doctor.py, setup
├── references/         # methodology, request schema, API notes, troubleshooting, roadmap
├── assets/             # report theme, example requests
├── evals/              # agent scenarios, grader checks and results of real runs
└── tests/              # unit, contract (recorded API responses), live API smoke tests
```

Dependency direction is enforced with import-linter:
`cli -> application | adapters -> ports -> contracts -> domain`. The domain never imports an
adapter, so every calculation is testable offline.

The method (window and context, verdicts, trust, control articles, steps, recommendation,
observations, text checks, charts) is documented in
[`references/methodology.md`](references/methodology.md); how to take the skill further, in
[`references/roadmap.md`](references/roadmap.md); how its quality is measured on a real
agent, in [`evals/README.md`](evals/README.md).

## Setup

```bash
./scripts/setup.sh        # Linux/macOS: installs uv if needed, then `uv sync`
scripts\setup.ps1         # Windows PowerShell
```

The agent needs only `uv`: the first `uv run --project` creates the environment by itself.
Without uv:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is exported from `uv.lock` (`uv export --no-dev -o requirements.txt`) and
pins every transitive dependency, so both paths give the same environment.

## Development

```bash
uv sync                          # includes the dev group
uv run pytest -n auto --cov      # tests in parallel; add `-m live` to also hit the real APIs
uv run ruff check . && uv run ruff format .
uv run mypy
uv run lint-imports
uv run agentskills validate ../wiki-interest   # Agent Skills spec compliance (needs the dir name)
```

Changes to thresholds or wording are logged in [`CHANGELOG_v0.2.md`](CHANGELOG_v0.2.md) with
the evaluation run that tested them.

## License

MIT.
