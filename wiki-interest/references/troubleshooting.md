# Troubleshooting

Read this when a command fails or the output looks wrong. Start with the exit code.

## First step for anything unexpected

```
uv run scripts/doctor.py
```

It checks the Python version, the cache directory, the bundled fonts and probes the three
Wikimedia services. Its JSON output names the failing check and why.

## By exit code

### 2: request invalid

The `error` field names the offending field. Common causes:

- an unknown key (typo such as `"project"` instead of `"projects"`): keys are checked strictly;
- `period.start` before `2015-07` (no data exists earlier) or `end` before `start`;
- `question_type: "compare"` with a single topic and a single project;
- `bundle: "manual"` without `extra_titles`;
- `extra_titles` for a project that is not in `projects`.

Fix the field and rerun. `references/request-schema.md` lists every field.

### 3: clarification needed

The topic matched several Wikidata entities (for example a scientific term and a band of the
same name). The output contains `candidates` with `qid`, `label` and `description`. Show
them to the user, ask which one they mean, then rerun with `"qid": "Q…"` in that topic. Do
not pick one yourself.

### 4: upstream failure or no data

- `retryable: true`: Wikimedia timed out or rate-limited even after retries. Wait a minute and
  rerun; the cache keeps what was already fetched.
- `retryable: false`: the service rejected the request; the message names the URL. Report it.
- "no data": the period lies entirely before 2015-07, or the edition does not exist.

### 5: internal error

Report the `error` text and attach the doctor output. If the message mentions a missing
module, the environment was not synced: run `scripts/setup.sh` (or `uv sync`).

## Symptoms

**"No article" for an edition the user knows has one.** Wikidata has no sitelink for that
edition, and the full-text search found nothing. Add the exact title under
`extra_titles` for that project; it becomes the main article for that edition.

**The bundle contains an unrelated article.** Add it to `exclude_titles` for that project, or
set `bundle: "main"` to analyse the main article alone, or `bundle: "manual"` with the exact
titles the user wants.

**Trust level is low.** Read the reasons in `summary.md`; they are the answer. Typical: window
shorter than 12 months (choose a longer `period`), traffic dominated by a news spike (the
report says so), article found via search rather than a sitelink, mean views under 300 per
month (small edition: prefer `per_million` and say the signal is weak).

**Numbers differ from a previous run.** The current month is partial and excluded by default;
if the user set `period.end` to the current month, values will change daily. Also the cache
refreshes such windows every 24 hours. `scripts/run.py --diff <run-a> <run-b>` shows what changed.

**Cyrillic or diacritics look wrong in the PDF.** The doctor's `fonts` check must pass; the
PDF uses DejaVu Sans bundled with matplotlib. Re-sync the environment if it fails.

**`uv: command not found`.** Run `scripts/setup.sh` (or `scripts/setup.ps1`); it installs uv
for the current user. Without uv: `python -m venv .venv`, activate it, then
`pip install -r requirements.txt`.

**Stale or corrupted cache.** Delete `.cache/http.sqlite` inside the skill directory; the
next run refetches everything (a few seconds per topic and edition).

## Where things are

| What | Where |
|---|---|
| Run outputs | `runs/<session>/<run-id>/` (`summary.md`, `summary.json`, `report.pdf`, `report.md`, `charts/`) |
| HTTP cache | `.cache/http.sqlite` |
| Request examples | `assets/examples/` |
| Settings via environment | `WIKI_INTEREST_*` (see `wiki_interest/config.py`) |
