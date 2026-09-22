---
name: wiki-interest
description: Analyse interest in a topic using Wikipedia pageview statistics across language editions, compare growth between languages, assess how trustworthy a trend is, draw charts and produce a one-page PDF report. Use whenever a user asks which topic to develop, which language or market to launch in, whether interest in something is growing or fading, which audiences to research next, or wants Wikipedia traffic data compared, charted or reported, even if they do not say "Wikipedia".
compatibility: Requires Python 3.12+ with uv (or pip) and network access to wikimedia.org and wikidata.org.
metadata:
  author: b-ark
  version: "0.1.0"
---

# Wiki Interest

Turns Wikipedia pageview statistics into a short, data-backed answer: is interest in a topic
growing, how does it differ between language editions, which audiences look promising, and
how much can that be trusted. Output: `summary.md` (for you to relay), a one-page
`report.pdf` and charts (for the user), `summary.json` (every number).

## The one rule

The code does the thinking; you translate. Write a small `request.json`, run one script,
relay what it wrote. Never compute growth or percentages yourself, never call the Wikimedia
API by hand, never write your own analysis code: the script already normalises traffic by
edition size, tests the trend, checks reliability and writes the caveats. Numbers in your
answer come only from `summary.md`.

## Workflow

1. **Set up once per machine.** From the skill directory run `scripts/setup.sh`
   (Windows: `scripts/setup.ps1`). It installs `uv` if needed and syncs the environment.
2. **Write `request.json`.** Copy the closest example from `assets/examples/` and change
   only what the user asked for:
   - `question_type`: `compare` (editions or topics against each other), `assess` (is one
     topic growing and can we trust it), `rank` (which audiences to pursue next);
   - `topics[].query` in the user's own words and `query_language` = the language of that
     wording; give each topic a short Latin `id`;
   - `projects`: language codes such as `["pl", "cs"]`;
   - `period` only if the user named one (default: last 24 complete months);
   - `report.language`: the language the user writes in (`uk`, `ru`, `en`, `pl`, `cs`);
   - `report.audience_note`: one line of context if the user gave any;
   - `session`: a short slug for this conversation, reused for follow-ups.
   Every other field has a sensible default. Full reference: `references/request-schema.md`.
3. **Run** from the skill directory:

   ```
   uv run scripts/run.py request.json
   ```

   It prints one JSON object. On success it contains `summary_md`, `report_pdf` and
   `run_dir` paths.
4. **Answer.** Read `summary_md` and relay it almost verbatim in the user's language: the
   one-line answer, the key numbers table, the trust level with its reasons, the caveats.
   Tell the user where `report.pdf` and the charts are. Keep every number exactly as written.
5. **Follow-ups** ("and over five years?", "add German", "that article is not what I
   meant"): edit the same `request.json`, keep the same `session`, run again. Cached data
   makes it fast. `uv run scripts/run.py --diff <run-a> <run-b>` lists what changed between
   two runs so you can explain the effect of the new assumption.

## Exit codes

| Code | Meaning | Do this |
|---|---|---|
| 0 | done | relay `summary.md`, point to the PDF |
| 2 | request invalid | fix the field named in `error`, rerun |
| 3 | clarification needed | the output lists `candidates`; ask the user which one they mean, then set `topics[].qid` and rerun. Do not guess. |
| 4 | Wikimedia unreachable or no data for the period | say so, offer to retry or change the period |
| 5 | internal error | report `error`; run `uv run scripts/doctor.py` and include its output |

Errors are JSON on stdout with `error`, `exit_code` and `hint`.

## What the answer must contain

- The trust level (`high` / `medium` / `low`) and the reasons behind it. A low level is not a
  failure; it tells the user a decision should not rest on this signal alone.
- The caveat that Wikipedia readership measures curiosity, not willingness to pay, and that
  editions differ in how well they cover a topic. `summary.md` phrases these for you.
- When an edition has no article for the topic, say "no article", not "no interest".
- The bundle composition (which articles were counted) if the user might dispute it, and
  the offer to exclude or add articles.

## When to read more

- `references/request-schema.md`: any field you are unsure about, follow-up patterns.
- `references/methodology.md`: the user asks how a number was computed or what the trust
  level means.
- `references/troubleshooting.md`: a command fails or output looks wrong.
- `references/api-notes.md`: only when debugging data issues.
