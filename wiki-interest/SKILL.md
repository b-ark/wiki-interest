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
how much can that be trusted. Output: a one-page `report.pdf` with charts (for the user) and
your answer in the chat.

## Who does what

The code measures: it fetches the data, computes every number, decides the states (growing,
steady, robust or not), draws the charts. You write the analysis in the user's language:
the headline, what happened, how robust it is, what it means for their decision, the next
step, the caveats. The code then checks your text against its numbers, puts it into the PDF
and builds your chat answer from it. Everything you say to the user, questions included, is
in the language they write in.

So: never compute a number yourself, never call the Wikimedia API, never write analysis
code. Every number you write is copied from `facts.json` (`numbers[].display`); rounding is
fine, deriving is not (no ratios, differences, sums, "1 in N").

## Workflow

`<skill>` below is this skill's base directory (shown when the skill loads). Work from the
user's current directory: the request and the reports belong there, not inside `<skill>`,
which may be read-only.

1. **Decide what the user means before running anything.** Many names have several
   meanings: "Mercury" is a planet, a chemical element, a god, a singer. If the conversation
   settles it ("our chemistry app"), write that meaning into the request (step 3) and use the
   name that has that meaning as `query`. If it does not, list the common meanings and ask,
   in the user's language; do not run. Search goes by spelling, not meaning: Ukrainian
   "Меркурій" finds the planet first, the element is "ртуть". Interest in learning or
   teaching a subject ("learning English", "an astronomy course") is measured on the subject
   itself: `query` is "English language", "astronomy"; articles about learning it are missing
   from most editions.
2. **Needs only `uv`.** The first run creates the Python environment by itself (about ten
   seconds). If `uv` is missing, run `<skill>/scripts/setup.sh` (Windows:
   `<skill>/scripts/setup.ps1`) once.
3. **Write `request.json`** in the current directory with your file-writing tool. Copy the
   closest example from `<skill>/assets/examples/` and change only what the user asked for:
   - `question_type`: `compare` (editions or topics against each other), `assess` (is one
     topic growing and can we trust it), `rank` (which audiences to pursue next);
   - inside each topic: `query` in the user's own words, `query_language` = the language of
     that wording, `query_en` = the topic in English (skip it if the query is English), and
     a short Latin `id`. These fields go in `topics[]`, never at the top level;
   - `topics[].meaning`: what the user means in a few English words ("the chemical element
     Hg"), when you decided it in step 1;
   - `projects`: language codes such as `["pl", "cs"]`;
   - `period` only if the user named one (default: last 24 complete months);
   - `report.language`: the language the user writes in (`ru`, `de`, `es`...), never the
     language of an edition and never the example's value;
   - `report.audience_note`: one line of context if the user gave any, in their language
     (the PDF prints it);
   - `report.seasonality: "show"` only if the user asks about timing (which months, seasons,
     when to launch);
   - `session`: a short slug for this conversation, reused for follow-ups.
   Every other field has a sensible default. Full reference: `references/request-schema.md`.
4. **Run:**

   ```
   uv run --project "<skill>" "<skill>/scripts/run.py" request.json
   ```

   It prints one JSON object on stdout (ignore stderr) with `run_dir` and `facts_json`. A
   first run can take a few minutes: give the command a 10-minute timeout (600000 ms) and
   wait for it; never send it to the background.
5. **Check the topic.** `topics[]` in the output names the entity that was analysed, with
   its description and other meanings. If it is not what the user meant, set `topics[].qid`
   to the right one and rerun.
6. **Write `narrative.json`** in one go, after reading `facts_json` once: `pairs[]` (states
   and numbers per edition), `conclusion`, `findings`, `caveats`, and `blocks` and `rules`
   (how each field is written). `facts.template` is the code's own text in the same schema
   (in English when the language has no catalog): rewrite it for this user and their
   question. Fields:
   - `language` = `facts.language`; `glossary`: your term for each metric, used in every
     sentence with a number (`{"attention_share": "доля внимания", "article_views": ...,
     "edition_traffic": ...}`);
   - `topic`: which item was analysed, one line in the user's language ("ртуть, хімічний
     елемент"); the chat answer opens with it;
   - `headline`, `happening[]`, `robustness[]` (one `{"pair": pairs[].id, "text": ...}` per
     measured pair, naming its edition), `decision[]`, `next_step`;
   - `caveats[]`: every caveat of `facts.caveats`, one short item each; `covered_caveats`:
     their ids;
   - `ui`: the interface labels, in the template in English: translate each value, keep
     `{placeholders}`.
   The code builds your chat reply from these blocks; do not write one.
7. **Render:**

   ```
   uv run --project "<skill>" "<skill>/scripts/render.py" <run_dir> --narrative narrative.json
   ```

   - exit 0, `status: accepted`: send `chat_answer` (built from your text) as your final
     message, word for word: nothing before or after it ("Here is the report", "Done!"), no
     summary of it, no other language. The checks ran on that text; anything you change is
     unchecked.
   - exit 2, `status: rejected`: fix every item of `problems` in one rewrite of
     `narrative.json` and render once more; where a problem says "write it as ...", use
     exactly those words.
   - `status: fallback` (rejected twice): the report keeps the code's text; relay
     `summary_md` instead, in the user's language (it is in English when the language has
     no catalog), numbers exactly as written.
8. **Follow-ups:** edit the same `request.json`, keep the same `session`, run again (cached
   data makes it fast), write a new `narrative.json` from the *new* `facts.json`:

   | The user says | Change |
   |---|---|
   | "over five years", "since 2020" | `period` (`{"start": "2021-09", "end": "2026-08"}`) |
   | "add German", "also Slovak" | append to `projects` |
   | "that article is not what I meant" | `topics[].qid` of the right meaning from `topics[]` |
   | "raw numbers", "without normalisation" | `normalization: "absolute"` |
   | "which months are strongest", "when to launch" | `report.seasonality: "show"` |
   | "growth matters most" | `ranking_weights` |
   | "how exactly was this computed", "show the method" | `report.appendix: true` (a second PDF page); `method.md` is always in the run directory |

   The chat answer of a follow-up says itself what changed against the run before it. For
   more detail, compare the two runs:
   `uv run --project "<skill>" "<skill>/scripts/run.py" --diff <run_dir-a> <run_dir-b>`.

## Exit codes of run.py

| Code | Meaning | Do this |
|---|---|---|
| 0 | done | write `narrative.json`, render (steps 6–7) |
| 2 | request invalid | fix the field named in `error`, rerun |
| 3 | a decision is needed | Nothing has been measured yet; `clarification.kind` says what. `ambiguous_topic`: if the conversation clearly means one of the `candidates`, set its `qid` and rerun, and say which meaning you chose; otherwise ask. `missing_article`: some edition has no article; say so and show the numbered options from `summary.md` in the user's language, each with its link, then ask which to use and end your turn with that question. Only after the user answers, copy that option's `choose` value into `topics[].substitutes` and rerun; never choose for the user. `topic_not_found`: say plainly that nothing was found and ask for a link to a Wikipedia article about what they mean; put it into `topics[].article_url`, rerun. |
| 4 | Wikimedia unreachable or no data for the period | say so, offer to retry or change the period |
| 5 | internal error | report `error`; run `uv run --project "<skill>" "<skill>/scripts/doctor.py"` and include its output |

Errors are JSON on stdout with `error`, `exit_code` and `hint`.

## What your text must get right

The render step checks numbers, metric names, edition labels, caveats and lengths. What it
cannot check is meaning, so:

- Say which meaning of the topic was analysed, in one line ("Python, the programming
  language"), even when it seems obvious.
- Follow the states in `facts.json`: `momentum`, `robustness`, `outcome`, `conclusion`. A
  declining share is a decline even for the largest audience; when everything declines, say
  so, then which edition declines least. Do not replace the conclusion with your own.
- The size of interest is the attention share: views per million views of that edition,
  not people and not a market size.
- Wikipedia views measure attention and curiosity, not demand or willingness to pay; a
  language edition is not a country.
- An edition without an article has "no article", not "no interest"; a substitute
  (`pl.wikipedia (Post)`) is named every time.
- State any change you made to what the user asked for: a period moved because data starts
  in 2015-07, a topic reworded, an edition dropped.

## When to read more

- `references/request-schema.md`: any field you are unsure about, follow-up patterns.
- `references/methodology.md`: the user asks how a number was computed or what the states
  mean.
- `references/troubleshooting.md`: a command fails or output looks wrong.
- `references/api-notes.md`: only when debugging data issues.
- `references/roadmap.md`: the user asks for something the skill cannot do yet (topic
  discovery, hundreds of topics, confidence intervals, countries); explain what is planned.
