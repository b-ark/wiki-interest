# request.json reference

The pipeline takes one JSON file. Start from a bundled example in `assets/examples/` and change
only what the user asked for; every field not listed there has a sensible default.

```
uv run --project "<skill>" "<skill>/scripts/run.py" request.json
# full pipeline -> ./wiki-interest-runs/<session>/<run-id>/
```

Write `request.json` in the current working directory, not inside the skill directory.

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
| `session` | slug | none | Groups related runs of one conversation under `wiki-interest-runs/<session>/`. Reuse it for follow-up questions so cached data and earlier runs stay together. |

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
| `query_en` | string | none | The topic in English. Tried only when the search in `query_language` finds nothing: Wikidata often has no label in exactly the languages that lack an article ("post przerywany" finds nothing, "intermittent fasting" finds the item). Always fill it when `query_language` is not `en`. |
| `id` | slug | derived | Stable identifier used in outputs and file names. Derived from a Latin query; for non-Latin queries it becomes `topic-1`, `topic-2`... so set an explicit id like `"fasting"`. |
| `qid` | `"Q…"` | none | Pin a Wikidata item and skip the search. Use it after `ambiguous_topic` (exit code 3), or when the "Topic:" line shows the wrong entity and the right one is among the other meanings. |
| `meaning` | string | none | What the user means, in a few English words ("the chemical element Hg"), decided from the conversation. Not interpreted by the code; recorded so the analysed entity can be checked against it. |
| `article_url` | `https://pl.wikipedia.org/wiki/…` | none | A Wikipedia article about the topic, given by the user after `topic_not_found`. Its Wikidata item replaces the search; an article without an item is analysed on its own in its edition. |
| `local_terms` | `{"pl.wikipedia": "post przerywany"}` | `{}` | How the topic is called in an edition's language. Optional; used only for editions without an article, to find a redirect or articles that mention the topic. Add it when the output says the local name is unknown. |
| `substitutes` | `{"pl.wikipedia": {"title": "Post", "kind": "broader"}}` or `{"pl.wikipedia": "skip"}` | `{}` | The user's decision for an edition without an article, copied from the `choose` value of the option they picked (exit code 3, `missing_article`). `kind` is `redirect`, `broader` or `mention`; `"skip"` leaves the edition out. |

## report

| Field | Type | Default | Meaning |
|---|---|---|---|
| `language` | language code (`ru`, `de`, `es`...) | `en` | The language the user writes in: you write the report text in it. Only `en` has built-in interface labels; for any other language `facts.json` lists the labels (`ui_strings`) for you to translate in `narrative.json` (once per session: later runs reuse them). |
| `title` | string | derived | Report title. |
| `audience_note` | string | none | One line of context that goes into the report ("educational app considering an astronomy course"). |
| `seasonality` | `auto` / `show` | `auto` | `show` when the user asks about timing (which months, seasons, when to launch): the seasonal pattern is then always reported and charted, with a caveat if it is not solid. `auto` states it only when it is solid on the article's whole history (5+ full years, repeated in 80 % of years, material). |
| `appendix` | `true` / `false` | `false` | `true` adds a second PDF page with the method and data checks (the content of `method.md`, which every run writes next to the report). The report is one page otherwise. |

## Examples

Compare two editions (`assets/examples/compare-fasting-pl-cs.json`):

```json
{
  "question_type": "compare",
  "topics": [{ "query": "intermittent fasting", "query_language": "en", "id": "intermittent-fasting" }],
  "projects": ["pl.wikipedia", "cs.wikipedia"],
  "period": { "start": "2024-09", "end": "2026-08" },
  "report": { "language": "en" },
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
- "that article is not what I meant" -> pin `qid` from the other meanings the run lists, or `article_url`;
- "compare raw numbers" -> `normalization: "absolute"`;
- different priorities -> `ranking_weights`.

Cached data makes re-runs fast; `scripts/run.py --diff <run_dir-a> <run_dir-b>` explains what changed.

## Exit codes

| Code | Meaning | What to do |
|---|---|---|
| 0 | success | relay `summary.md`, attach the PDF |
| 2 | request invalid | fix the field named in the message and rerun |
| 3 | a decision is needed | `clarification.kind` says which: `ambiguous_topic` -> pick the candidate the conversation clearly means (say so) or ask, rerun with `qid`; `missing_article` -> show the numbered options from `summary.md`, ask, copy the chosen option's `choose` value into `topics[].substitutes`, rerun; `topic_not_found` -> say so, ask for a Wikipedia link, rerun with `article_url`. Nothing was measured yet in any case. |
| 4 | Wikimedia services unreachable after retries, or no data for the period | tell the user, offer to retry or change the period |
| 5 | internal error | report the message; run `scripts/doctor.py` |

Errors are printed as JSON on stdout with `error`, `exit_code` and `hint` fields; logs go to stderr.
