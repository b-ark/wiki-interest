# request.json reference

The pipeline takes one JSON file. Start from a bundled example in `assets/examples/` and change
only what the user asked for; every field not listed there has a sensible default.

```
scripts/run.py request.json          # full pipeline -> runs/<session>/<run-id>/
```

## Top level

| Field | Type | Default | Meaning |
|---|---|---|---|
| `schema_version` | `"1"` | `"1"` | Schema version. Leave as is. |
| `question_type` | `compare` / `assess` / `rank` | required | See below. |
| `topics` | list of Topic, 1-10 | required | What to analyse. |
| `projects` | list of strings, 1-10 | required | Language editions: `"uk"`, `"uk.wikipedia"`, `"ukwiki"` and `"uk.wikipedia.org"` all mean Ukrainian Wikipedia. Duplicates are dropped. |
| `period` | `{"start": "YYYY-MM", "end": "YYYY-MM"}` | last 24 complete months | Inclusive whole months. Data starts 2015-07. The current month is never complete, so leave it out unless the user insists. |
| `agent` | `user` / `all-agents` | `user` | Traffic class. `user` excludes crawlers and known automated traffic; keep it unless the user asks for raw totals. |
| `access` | `all-access` / `desktop` / `mobile-web` / `mobile-app` | `all-access` | Access method filter. |
| `normalization` | `per_million` / `absolute` | `per_million` | Primary metric. `per_million` = article views per million views of the whole edition; the only fair way to compare editions of different size. |
| `ranking_weights` | object | growth 0.4, volume 0.3, stability 0.2, reliability 0.1 | Only used by `rank`. Any non-negative numbers; normalised automatically. |
| `report` | object | see below | Report language and framing. |
| `session` | slug | none | Groups related runs of one conversation under `runs/<session>/`. Reuse it for follow-up questions so cached data and earlier runs stay together. |

Unknown keys are rejected on purpose: a misspelled field would otherwise be silently ignored.

### question_type

| Value | Use when the user asks... | Needs |
|---|---|---|
| `compare` | how interest differs between editions or topics ("Poland vs Czechia", "topic A vs B") | at least two (topic, project) combinations |
| `assess` | whether interest in one topic is growing and how much to trust that | one topic, one or more projects |
| `rank` | which audiences to pursue or research next | one or more topics across several projects |

## Topic

| Field | Type | Default | Meaning |
|---|---|---|---|
| `query` | string | required | The topic as the user phrased it, in any language ("інтервальне голодування", "intermittent fasting"). |
| `query_language` | language code | `en` | Language of `query`. Set it correctly: it drives the Wikidata search. |
| `id` | slug | derived | Stable identifier used in outputs and file names. Derived from a Latin query; for non-Latin queries it becomes `topic-1`, `topic-2`... so set an explicit id like `"fasting"`. |
| `qid` | `"Q…"` | none | Pin a Wikidata item and skip the search. Use it after a clarification (exit code 3) once the user picked a candidate. |
| `bundle` | `main` / `auto` / `manual` | `auto` | `auto`: main article plus related articles found through Wikidata and lead-section links (the same concepts in every edition). `main`: main article only. `manual`: exactly the titles in `extra_titles`. |
| `extra_titles` | `{"uk.wikipedia": ["Телескоп"]}` | `{}` | Additional articles per project, added to the bundle with role `manual`. |
| `exclude_titles` | same shape | `{}` | Articles to drop from the automatic bundle (use when the user says "that one is not what I mean"). |

## report

| Field | Type | Default | Meaning |
|---|---|---|---|
| `language` | `en` / `uk` / `ru` / `pl` / `cs` | `en` | Language of the report, summary and chart labels. Match the language the user writes in. |
| `title` | string | derived | Report title. |
| `audience_note` | string | none | One line of context that goes into the report ("educational app considering an astronomy course"). |
| `formats` | list of `pdf` / `md` | both | Which report files to write. `summary.md` and `summary.json` are always written. |

## Examples

Compare two editions (`assets/examples/compare-fasting-pl-cs.json`):

```json
{
  "question_type": "compare",
  "topics": [{ "query": "intermittent fasting", "query_language": "en", "id": "intermittent-fasting" }],
  "projects": ["pl.wikipedia", "cs.wikipedia"],
  "period": { "start": "2024-09", "end": "2026-08" },
  "report": { "language": "uk" },
  "session": "fasting-pl-cs"
}
```

Assess one topic with default period (`assets/examples/assess-astronomy-uk.json`):

```json
{
  "question_type": "assess",
  "topics": [{ "query": "астрономія", "query_language": "uk", "id": "astronomy" }],
  "projects": ["uk.wikipedia"],
  "report": { "language": "uk", "audience_note": "Educational app considering an astronomy course" },
  "session": "astronomy-uk"
}
```

Rank audiences (`assets/examples/rank-english-learning.json`): one topic, five projects, custom weights.

## Follow-up requests

Keep the same `session` and change only what the user changed:

- a longer or different period -> edit `period`;
- another edition -> append to `projects`;
- "that article is not what I meant" -> `exclude_titles`, or pin `qid` after a clarification;
- "compare raw numbers" -> `normalization: "absolute"`;
- different priorities -> `ranking_weights`.

Cached data makes re-runs fast; `scripts/run.py --diff <run-a> <run-b>` explains what changed.

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | success | relay `summary.md`, attach the PDF |
| 2 | request invalid | fix the field named in the message and rerun |
| 3 | clarification needed | show the candidates from the output to the user and ask; then rerun with `qid` |
| 4 | Wikimedia services unreachable after retries, or no data for the period | tell the user, offer to retry or change the period |
| 5 | internal error | report the message; run `scripts/doctor.py` |

Errors are printed as JSON on stdout with `error`, `exit_code` and `hint` fields; logs go to stderr.
