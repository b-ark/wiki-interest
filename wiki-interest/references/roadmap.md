# How to grow this skill

The skill answers the basic questions: is interest in a topic growing in a language edition,
how do editions compare, which audiences look promising, and how far to trust that. This
document explains how to take it further, in the order that pays off first, and how to keep
quality measurable while doing it. Read it when a user asks for something the pipeline cannot
do yet, or when planning the next iteration.

## The loop every change goes through

1. **A real request fails or disappoints.** It becomes a scenario in `evals/evals.json` with
   assertions for what "right" means and, where needed, an oracle request.
2. **`skill-evals oracle`** proves the new assertions pass for an ideal answer and fail for an
   empty one, before any model is paid for.
3. **The fix goes where it belongs:** code for anything deterministic (numbers, resolution,
   wording), `SKILL.md` only for agent behaviour. Code fixes come with unit tests.
4. **`skill-evals run` + `compare`** on the old and new version, three or more repetitions;
   the change is kept only if it beats the noise floor printed in `benchmark.md` and costs no
   more turns.
5. Summaries land in `evals/results/`, so the history of what worked is visible.

Every fix so far followed this path. For example, the first Haiku transcript showed the agent
trying to write inside `.claude/` and fighting a PowerShell byte-order mark; the fix
(requests in the working directory, BOM-tolerant loading) cut the run from 10 turns to 6.

## Next steps, in order of value

### 1. Topic discovery, not only topic checking

Today the user must name the topic. The Pageviews API also publishes the most-viewed
articles per edition and month (`/metrics/pageviews/top`). A `discover` question type would
take an edition and a seed area (via Wikidata classes such as "sport", "diet", "science"),
collect articles that entered the top lists or grew fastest, and hand them to the existing
`assess` path. It reuses resolution, metrics and reports; the new parts are a top-list
adapter and a candidate filter.

### 2. Larger studies: many topics x many editions

The API path is fine for tens of series; a study of 200 topics in 30 editions means thousands
of requests. The architecture already isolates this behind `PageviewsSource`:

- add a `DumpPageviewsSource` that reads the monthly per-article dumps
  (`dumps.wikimedia.org/other/pageview_complete/`) into Parquet once, then answers from
  DuckDB; no domain or report code changes;
- batch requests as one `request.json` with many topics and let the loader deduplicate
  (it already does across bundles);
- keep one run directory per study with a `summary.json` per topic and a cross-topic ranking
  table, so the agent still relays one short summary.

### 3. Stronger statistics where decisions need them

- confidence intervals on growth by block bootstrap over months, so "−12 %" becomes
  "−12 % (−18 % to −6 %)";
- seasonal decomposition (STL) so a September school spike is separated from the trend,
  and year-over-year growth is computed on the deseasonalised series;
- change-point detection, so "interest collapsed in March 2025" is reported as an event,
  not as a trend;
- a baseline per edition: growth relative to all articles in the same Wikidata class, which
  separates "this topic is rising" from "the whole edition is shrinking".

Each of these is a pure domain function with synthetic-series tests and a new reliability
rule, so the verdict explains when it fires.

### 4. Geography inside a language

Spanish or English editions mix many countries. The Pageviews API's per-country data
(`top-by-country`, `top-per-country`) can split an audience by country where the
anonymisation thresholds allow it, which answers "Spanish in Mexico or in Spain?".

### 5. Long-lived research

A founder returns weekly. Sessions already group runs; the next step is scheduled re-runs of
a saved request and a diff against the previous run (`scripts/run.py --diff` exists), with a
short "what changed since last time" summary.

### 6. More agents, more models

- the harness already speaks to OpenRouter models, so the same scenarios can certify the skill
  on non-Claude models before claiming support for them;
- `skill-evals trigger` measures whether the description activates the skill on the right
  requests and not on near-misses; rerun it whenever the description changes.

## What not to do

- Do not move analysis into `SKILL.md`. Instructions that ask the model to compute are the
  first thing a cheap model gets wrong, and they cannot be unit-tested.
- Do not add a metric without a reliability rule that says when it is not trustworthy.
- Do not grow the scenario set only with cases the current version passes; add the failures.
