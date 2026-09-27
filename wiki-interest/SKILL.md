---
name: wiki-interest
description: Analyse interest in a topic using Wikipedia pageview statistics across language editions, compare growth between languages, assess how trustworthy a trend is, draw charts and produce a one-page PDF report. Use whenever a user asks which topic to develop, which language or market to launch in, whether interest in something is growing or fading, which audiences to research next, or wants Wikipedia traffic data compared, charted or reported, even if they do not say "Wikipedia".
compatibility: Requires Python 3.12+ with uv (or pip) and network access to wikimedia.org and wikidata.org.
metadata:
  author: b-ark
  version: "0.2.0"
---

# Wiki Interest

Turns Wikipedia pageview statistics into a short, data-backed answer: is interest in a topic
growing, how does it differ between language Wikipedias, which audiences look promising, and
how much can that be trusted. Output: a `report.pdf` with charts (for the user; one page, a
second when a follow-up adds the season, topics or Wikipedias) and your answer in the chat.

## Who does what

The code measures, decides and observes. It reads the **analysis window** (the period the
user named, by default the last 24 complete months) and gives each language a verdict on its
attention share: `growing`, `stable`, `declining` or `insufficient_data`. It says how far each
verdict can be trusted (`high`, `medium`, `low`, with its reasons: year-on-year months, the
trend's interval, the control articles of the same Wikipedia, renames). It recommends which language to
pick and what to check next. It writes the headline, one verdict line and one trust line per
language, and the recommendation line: those go into the PDF and the chat word for word. The
six years before the window are context: the charts show them and some observations describe
them, always named as context. The code also writes observations: true statements with their
numbers (a step in October 2024, where the audience is bigger).

You explain: pick the observations that answer the user's question and connect them into a
short story in the user's language, then explain the code's recommendation. Tell each
language's direction as its verdict does, never another; do not rephrase or repeat the code's
lines (the verdict, trust and recommendation lines are printed as they are). The code checks
your text against the observations it cites, puts it into the PDF and builds your chat answer
from it. Everything you say to the user, questions included, is in the language they write
in.

So: never compute a number yourself, never call the Wikimedia API, never write analysis
code. Every number you write is copied from an observation your paragraph cites; rounding is
fine, deriving is not (no ratios, "N times", differences, sums, "1 in N").

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
   from most Wikipedias.

   **Which Wikipedias.** If the conversation names no language Wikipedia, ask which ones to
   look at before running, however clear the topic is ("Is interest in Stoicism growing?"
   names none). One short question in the user's language, with a few suggestions (their own
   language, English, the languages of markets they mentioned); do not pick for them. A
   market that means one language names it ("the Polish market": `pl`); a follow-up keeps the
   Wikipedias of the run before it. If the topic needs a meaning too, ask both in one message.
   If the user then leaves the choice to you, take their language and English and say so.
2. **Needs only `uv`.** The first run creates the Python environment by itself (about ten
   seconds). If `uv` is missing, run `<skill>/scripts/setup.sh` (Windows:
   `<skill>/scripts/setup.ps1`) once.
3. **Write `request.json`** in the current directory with your file-writing tool. Copy the
   closest example from `<skill>/assets/examples/` and change only what the user asked for:
   - `question_type`: `compare` (Wikipedias or topics against each other), `assess` (is one
     topic growing and can we trust it), `rank` (which audiences to pursue next);
   - inside each topic: `query` in the user's own words, `query_language` = the language of
     that wording, `query_en` = the topic in English (skip it if the query is English), and
     a short Latin `id`. These fields go in `topics[]`, never at the top level;
   - `topics[].meaning`: what the user means in a few English words ("the chemical element
     Hg"), when you decided it in step 1. The meaning never goes into `query`: `"query":
     "tesla", "meaning": "SI unit of magnetic flux density"`, not `"query": "tesla unit of
     magnetic flux density"`, which names no article;
   - `projects`: language codes such as `["pl", "cs"]`;
   - `period` only if the user named one (default: last 24 complete months);
   - `report.language`: the language the user writes in (`ru`, `de`, `es`...), never the
     language of a Wikipedia and never the example's value: "Is interest in Stoicism growing
     on German Wikipedia?" is `en`, with `projects: ["de"]`;
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
6. **Write `narrative.json`** in one go, after reading `facts_json` once. `observations[]`
   are what the data show, main ones first (`weight`: `caution`, `high`, `medium`, `low`,
   `context`, `decision`); `rules` say how to write; `example` shows observations and the
   narrative written from them on a made-up topic (the form only, none of its content).
   Fields:
   - `language` = `facts.language`; `topic`: which item was analysed, one line in the
     user's language ("ртуть, хімічний елемент"); the chat answer opens with it;
   - `story`: 2–4 short paragraphs `{"text": ..., "uses": [observation ids]}` that explain
     what is happening: start from the `trend:` (the verdict), `trust:`, caution and high
     observations that answer the question, connect them (why the numbers move, not only
     that they move), leave the rest out;
   - `meaning`: `{"text": ..., "uses": [...]}`: explain the code's recommendation
     (`recommendation:...`) in the user's words, name the Wikipedia or topic it chose, cite it
     and the decision observations you use; never pick another;
   - `limits`: one line (views show interest, not willingness to pay; a Wikipedia is a
     language, not a country);
   - `ui`: the interface labels of `facts.ui`, in English: translate each value, keep
     `{placeholders}` (nothing to do when `facts.ui` is empty).
   Leave out `headline` and `check`: the code writes the headline from the verdicts and the
   next check from the recommendation. The code builds your chat reply from these blocks; do
   not write one.
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
   | "check the neighbouring articles", "yes, add them" | append the `next_check.items` to `topics` (`{"id", "query", "qid"}`), as `recommendations[].next_check.change` says |
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
| 3 | a decision is needed | Nothing has been measured yet; `clarification.kind` says what. `ambiguous_topic`: if the conversation clearly means one of the `candidates`, set its `qid` and rerun, and say which meaning you chose; otherwise ask. With `from_search`, no item is named like the query and the candidates are guesses of a text search: take one only if its description fits what the user asked about; if none does, never the closest, say the topic was not found and ask for a link to a Wikipedia article in any language (`topics[].article_url`). `missing_article`: some Wikipedia has no article, and the code has composed the question. If `clarification.ui` lists labels, translate them into the user's language: write `question.json` as `{"ui": {...}}` (keep every `{placeholder}`) and run `render.py <run_dir> --ui question.json`. Send `ask_user` (from that output, or from `clarification` when no labels were listed) word for word as your whole message and end your turn. Only after the user answers, copy that option's `choose` value into `topics[].substitutes` and rerun; never choose for the user. "Skip Polish" or "without it" is the `skip` option: write `"skip"` for that Wikipedia and keep it in `projects`, so the report says it has no article. `topic_not_found`: say plainly that nothing was found and ask for a link to a Wikipedia article about what they mean; put it into `topics[].article_url`, rerun. |
| 4 | Wikimedia unreachable or no data for the period | say so, offer to retry or change the period |
| 5 | internal error | report `error`; run `uv run --project "<skill>" "<skill>/scripts/doctor.py"` and include its output |

Errors are JSON on stdout with `error`, `exit_code` and `hint`.

## What the result holds

`summary.json` (the run directory) and the chat answer carry what the code decided:

- `analysis_window` and `context_range`: the months the verdicts read, the months the charts
  show.
- `verdicts[]`: per language, `verdict`, `segment_start` (after a step inside the window the
  trend is read from it: "stabilised after a drop"), `level_start` → `level_end` of the trend
  line (per million views of that Wikipedia), `slope_pct_per_year`, and `trust`:
  `confidence`, `yoy_down`/`yoy_up` of `yoy_months`, `ci90`, `snr`, `control_change`,
  `breakpoints[]` (each `real`, `artifact` or `unknown`), `max_day_share`, `spike_months`,
  `reasons[]`, and its `line`.
- `recommendations[]`: `choice`, `why`, `confidence`, `next_check` (neighbouring articles
  or more Wikipedias the skill can add itself, with the `request.json` change), `line`,
  `next_line`.

When the user asks "can I trust this?", answer from `trust` (its line says it); when they
want the next check, `next_check.change` says what to change in `request.json`.

## What your text must get right

The render step checks that every number comes from an observation the paragraph cites,
that the story rests on the main observations and carries every caution, and the lengths.
What it cannot check is meaning, so:

- Say which meaning of the topic was analysed, in one line ("Python, the programming
  language"), even when it seems obvious.
- Keep each observation's direction and words: "slower than in 2025" is not "speeds up"; a
  step in one Wikipedia is not in both. Each language's direction is its verdict's: a stable
  share is not "falling" even when its views fall.
- History before the analysis window is context: say so ("in the wider context since
  2021"), and never tell it as the window's direction.
- One term per measure: the attention share ("частка уваги", "доля внимания") for views per
  million of that Wikipedia, views ("перегляди") for the article's own count; a language Wikipedia
  is a "мовний розділ" / "языковой раздел". Name periods as the observations do ("in 2021",
  "January–August 2026 against the same months of 2025"), never "five years ago"; a partial
  year is named as partial, and its caution about the season is kept.
- Every cause or guess comes from an observation and keeps its "possibly" or "probably";
  add no causes of your own and no outside events.
- Views are how often the article is opened ("the article is opened about 560 times a
  month"), not people and not a market size; they measure attention and interest, not
  demand or willingness to pay. Name each Wikipedia by its language ("the Polish Wikipedia"), never
  by country.
- A Wikipedia without an article has "no article", not "no interest"; a substitute
  (`pl.wikipedia (Post)`) is named every time.
- State any change you made to what the user asked for: a period moved because data starts
  in 2015-07, a topic reworded, a Wikipedia dropped.

## When to read more

- `references/request-schema.md`: any field you are unsure about, follow-up patterns.
- `references/methodology.md`: the user asks how a number was computed or what the states
  mean.
- `references/troubleshooting.md`: a command fails or output looks wrong.
- `references/api-notes.md`: only when debugging data issues.
- `references/roadmap.md`: the user asks for something the skill cannot do yet (topic
  discovery, hundreds of topics, confidence intervals, countries); explain what is planned.
