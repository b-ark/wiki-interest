# wiki-interest (skill)

Agent skill that turns Wikipedia pageview statistics into evidence for product decisions:
which topics are gaining interest, in which language editions, and how much the trend can be trusted.

Status: under construction. This README describes what exists now and is extended as the code lands.

## Layout

```
wiki-interest/
├── SKILL.md            # agent-facing instructions (Agent Skills format)
├── wiki_interest/      # Python package
│   ├── domain/         # pure calculations: metrics, trend tests, reliability rules, ranking
│   ├── application/    # use-cases orchestrating the ports
│   ├── ports/          # Protocol interfaces to the outside world
│   ├── adapters/       # Wikimedia REST, Wikidata, MediaWiki, cache, chart and report renderers
│   ├── contracts/      # pydantic schemas for request.json and summary.json
│   └── cli/            # typer commands used by scripts/
├── scripts/            # thin entry points the agent runs
├── references/         # methodology, request schema, API notes, troubleshooting (loaded on demand)
├── assets/             # report theme, i18n strings, example requests
└── tests/              # unit, contract (recorded API fixtures), live API smoke tests
```

Dependency direction is enforced with import-linter: `cli -> application | adapters -> ports -> contracts -> domain`.
The domain never imports an adapter, so every calculation is testable offline.

Agent evaluations are still pending: the harness is in `../tools/skill-evals`, but the planned
`evals/` scenario suite and benchmark summaries are not included yet. Passing Python tests
does not measure how reliably an agent selects the skill or explains its results.

## Setup

```bash
./scripts/setup.sh        # Linux/macOS: installs uv if needed, then `uv sync`
scripts\setup.ps1         # Windows PowerShell
```

Without uv:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is exported from `uv.lock` (`uv export --no-dev -o requirements.txt`) and pins
every transitive dependency, so both paths give the same environment.

## Development

```bash
uv sync                          # includes the dev group
uv run pytest -n auto --cov      # tests in parallel (~30 s); add `-m live` to also hit the real APIs
uv run ruff check . && uv run ruff format .
uv run mypy
uv run lint-imports
uv run agentskills validate ../wiki-interest   # Agent Skills spec compliance (needs the dir name)
```

## License

MIT.
