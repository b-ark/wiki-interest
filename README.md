# wiki-interest

An [Agent Skill](https://agentskills.io/specification) that helps founders of B2C products
decide which topics to develop next and which languages to launch in, using Wikipedia
pageview statistics. The agent names the topic, the skill's code finds its article in every
language Wikipedia asked for, reads the monthly views, decides whether interest is growing,
stable or declining and how far that can be trusted, recommends where to look next, and
renders a one-page PDF (a follow-up that adds the season, topics or Wikipedias may take a
second page). The agent writes the explanation in the user's language; the code checks
every number in it before anything reaches the user.

It is built to run well on a fast, cheap model: every decision and every number is made in
code, so the model only reads observations and writes prose. It is measured on
Claude Haiku 4.5 (see [Measured on Haiku 4.5](#measured-on-claude-haiku-45)).

## Quick start

Needs Python 3.12+ and [uv](https://docs.astral.sh/uv/) (the setup script installs uv when it is missing).

```bash
cd wiki-interest
./scripts/setup.sh                                  # Windows: scripts\setup.ps1
uv run scripts/doctor.py                            # checks Python, fonts, cache, the three APIs
uv run scripts/run.py assets/examples/assess-astronomy-uk.json
```

The last command writes `wiki-interest-runs/<session>/<run-id>/` with `summary.json`,
`summary.md`, `facts.json`, `method.md`, the charts and a `report.pdf` in the code's own
words (an agent then replaces the story with its own through `render.py --narrative`). To
use it as a skill, place the `wiki-interest/` directory where your agent loads skills (for
Claude Code: `~/.claude/skills/` or `<project>/.claude/skills/`).

See [`wiki-interest/README.md`](wiki-interest/README.md) for the package, its settings and
its architecture.

## What it answers

The three requests from the assignment, as the skill answers them (reports written by Haiku
4.5 in evaluation runs; the third on three Wikipedias, the most the charts hold):

| Request | What the report says |
|---|---|
| Compare the growth of interest in intermittent fasting in the Polish and Czech Wikipedias over the last two years | The Polish Wikipedia has no article on it, so the skill first asks whether to measure the broader article «Post» instead or leave Polish out. After "skip Polish": the Czech verdict on the attention share with its trend line, a low trust and why, the peak of 2022 as context, and the next check. [PDF](wiki-interest/evals/v0.2/stage18/compare-fasting-pl-cs/report.pdf) |
| Is interest in astronomy growing in the Ukrainian Wikipedia, and how far can that growth be trusted? | The verdict, a trust level with its reasons (months up year on year, the slope's interval, signal to noise, what the whole Wikipedia did, steps and renames), the context since 2021. [PDF](wiki-interest/evals/v0.2/stage18/assess-astronomy-uk/report.pdf) |
| Compare interest in learning English in the Ukrainian, Polish and Czech Wikipedias: which audiences to research next, and why? | Three languages side by side, a verdict and a trust level for each, the choice (with the same verdict and trust, the larger audience decides) and the order to research the others in. [PDF](wiki-interest/evals/v0.2/readme/rank-english-learning-3/report.pdf) |

Each run also writes `summary.json` (every decision and number, for follow-ups and other
tools), `method.md` (how each number was computed, with the thresholds in force) and the
charts as SVG and PNG.

## How it works

```
user question
   │  agent: decides what the user means (asks when the meaning or the Wikipedias are unclear),
   │         writes request.json
   ▼
scripts/run.py ──► resolves the topic (Wikidata, search) to an article per language
   │               reads monthly and daily views and each Wikipedia's total
   │               decides: verdict per language, trust, recommendation, next check
   │               writes observations: true statements with their numbers
   ▼
facts.json ──► agent writes narrative.json: a short story and what it means, citing observations
   ▼
scripts/render.py ──► checks the text; renders report.pdf and the chat answer
   ▼
agent sends the chat answer word for word
```

| Decided by code | Written by the model |
|---|---|
| Which article stands for the topic in each language, or a question when it is ambiguous or missing | Which meaning the user wants, when the conversation settles it; a question when no Wikipedia is named |
| The analysis window (default: the last 24 complete months) and the six years of context before it | |
| Each language's verdict on its attention share (views per million views of that Wikipedia): `growing`, `stable`, `declining`, `insufficient_data` | |
| The trust in each verdict (`high`, `medium`, `low`) and its reasons | |
| The recommendation, what decided it, and the next check the skill can run itself | |
| The headline, the verdict, trust and recommendation lines, the charts | The story (2–4 paragraphs) and what it means for the user, in their language |

The verdict reads the attention share, not raw views, so a topic is not called growing only
because its Wikipedia grew. The seasonal rhythm is divided out, bursts and months dominated
by one day are left out, and when the level jumped inside the window (a step beyond the
local trend) the trend is read from the step on: "stabilised after a drop" is a different
answer from "keeps declining". The full method is in
[`references/methodology.md`](wiki-interest/references/methodology.md).

## How conclusions are checked

- **Trust is computed, not asserted.** Each verdict carries: months of the last year on the
  verdict's side of the same month a year earlier, a 90 % bootstrap interval of the slope,
  signal to noise, and the trend of about a hundred control articles of the same Wikipedia
  (so a change of the whole Wikipedia is not read as a change of the topic). Steps are
  checked against the controls and against the article's move log: a rename or a
  Wikipedia-wide jump marks the step as probably technical.
- **Every number in the text is checked.** Before the PDF is written, every number of the
  model's text must match an observation its paragraph cites, within the rounding it is
  written with; a number nobody computed stops the render. The text must also cite every
  caution, explain the code's recommendation without picking another, and avoid wordings a
  cheap model got wrong (views counted as people, a language called a country, "five years
  ago" instead of a period). A rejected text comes back with the reasons; after a second
  rejection the report keeps the code's own text.
- **The chat answer is the checked text.** The code builds the chat answer from the same
  blocks as the PDF, so the user never reads an unchecked version.
- **Meaning is left to a judge.** Whether the story tells each language's direction as its
  verdict does is graded by an LLM judge in the evaluations, not guessed by string rules.

## Follow-ups and repeat queries

- A conversation is a `session`: a follow-up ("over five years", "add German", "raw numbers",
  "which months are strongest", "show the method") changes one field of the same
  `request.json` and runs again. The chat answer of a follow-up says what changed against the
  run before it: each language's verdict before and now.
- Responses are cached in SQLite: closed months forever, the current month for 24 hours,
  Wikidata and MediaWiki lookups for a week. A follow-up on the same topic makes no network
  request; the control articles are kept for 180 days.
- The recommendation names what the skill can check next on its own (neighbouring articles
  through Wikidata, or more language Wikipedias) with the exact `request.json` change, so
  "yes, check them" is one run.
- `run.py --diff <run-a> <run-b>` compares two runs field by field.

## Assumptions and limitations

Every report states them in one line; the ones that matter most:

- Views measure how often an article is opened: interest and attention, not demand, market
  size or willingness to pay. They point at where to look, not at what will sell.
- One main article (with its redirects) stands for the topic. A missing or thin article
  lowers the signal whatever the interest; a Wikipedia without the article is said to have
  none, never "no interest".
- A language Wikipedia is a language, not a country: the Russian Wikipedia is read far
  beyond Russia.
- The API filters crawlers and detected bots; what slips through is caught only in part
  (bursts, plateaus, months dominated by one day).
- Short windows and small Wikipedias are noisy; the trust level says so.
- **The charts show up to three languages.** With four or more, they show the recommended
  one and the two with the largest audience; every language keeps its verdict, trust and
  recommendation lines in the text and the chat answer. Charts that stay legible for more
  languages are open work ([roadmap](wiki-interest/references/roadmap.md)).

## Measured on Claude Haiku 4.5

Unit tests check the code; they do not show whether a cheap model, given only this skill,
answers correctly and honestly. [`wiki-interest/evals/`](wiki-interest/evals/) holds 32
realistic scenarios (the assignment's three requests, questions in English, Russian and
Ukrainian, ambiguous topics, missing articles, requests that name no Wikipedia, follow-ups, a
period before the data exists),
run through headless Claude Code on Haiku 4.5, three times each, and graded by code (every
number in the answer must come from the run) and by an LLM judge (Sonnet) on meaning.

| Run | Version | Pass rate | Judge | Turns | Cost per case |
|---|---|---|---|---|---|
| stage16 | v0.2.0: window, trust, code-made recommendation | 94.9 % | 91.9 % | 11.2 | $0.140 |
| stage17 | views chart by calendar year; the recommendation names its reason | 97.6 % | 93.6 % | 10.0 | $0.131 |
| stage18 | follow-ups compare verdicts; a short list for three languages or more; steps beyond the trend | 96.8 % | 94.8 % | 10.0 | $0.129 |

The runs above used the first 29 scenarios; the summaries behind the numbers are in
[`wiki-interest/evals/results/`](wiki-interest/evals/results/) (`stage16-vs-stage15.md`,
`stage17-vs-stage16.md`, `stage18-vs-stage17.md`). The noise floor for 29 scenarios × 3
repetitions is about ±11 points, so a change is counted as an improvement only above it. How the graders themselves were checked, and how to run the
evaluation, is in [`wiki-interest/evals/README.md`](wiki-interest/evals/README.md).

## How to grow it

[`references/roadmap.md`](wiki-interest/references/roadmap.md) lists the next steps in order
of value and the loop every change goes through (a failing request becomes a scenario, the
graders are checked, the fix goes into code with a test, the new version must beat the noise
floor). In short: topic discovery from the top lists instead of checking a named topic;
studies of hundreds of topics across tens of languages from the Wikimedia dumps instead of
the API; stronger statistics where a decision needs them; geography inside a language;
long-lived research that reruns itself; and the same evaluation on other agents and models.

## Repository layout

| Path | What it is |
|---|---|
| [`wiki-interest/`](wiki-interest/) | The skill: `SKILL.md`, the `wiki_interest` Python package, scripts, references, evaluation scenarios and tests. Self-contained and installable on its own. |
| [`tools/skill-evals/`](tools/skill-evals/) | Development-only harness that runs the skill through a real agent (headless Claude Code on Haiku 4.5; an OpenRouter provider exists but no published run used it), grades the outputs and compares `SKILL.md` versions. Not part of the skill. |
| [`task.md`](task.md) | The original assignment. |

## How AI tools were used, and how their output was checked

Most of the code was written with Claude Code, including parallel sub-agents. Nothing was
accepted on the strength of the model's own report. The checks, in the order they catch
problems:

1. **Contracts first.** Domain models, ports and the JSON schemas were written and reviewed
   before any parallel work. Four agents then built the domain, the API adapters, the
   renderers and the evaluation harness in isolated git worktrees against those frozen
   contracts; each report was read and every branch was merged only with all gates green.
2. **Mechanical gates on every commit:** ruff (including docstring rules), mypy `--strict`,
   import-linter for the layer boundaries, pytest with coverage, and the Agent Skills
   validator. They run in pre-commit and in CI on Ubuntu and Windows.
3. **Independent references for numerical code.** The Mann-Kendall test and Theil-Sen slope
   are implemented without dependencies and checked in tests against `pymannkendall` and
   `scipy` on seeded series; the verdict, the trust and the step detection are tested on
   synthetic series with known answers and on a recorded reference case (veganism in the
   Russian and Czech Wikipedias).
4. **Recorded reality.** Adapter tests replay real Wikimedia, Wikidata and MediaWiki
   responses; a few live smoke tests run on demand.
5. **Running the assignment's own questions on live data** and reading the output as a
   founder would. This caught what tests could not: a Polish search fallback that returned an
   article on oxidative stress for "intermittent fasting", citation identifiers (ISSN, DOI)
   entering topic bundles, a Hogwarts school subject competing with the science of
   astronomy, a headline calling a decline "fastest growth", a steady fall of 40 % a year
   read as a row of steps, and a chart whose bars argued with the recommendation. Each became
   a fix with a regression test.
6. **Checking the graders before trusting them.** `skill-evals oracle` grades an ideal answer
   and an empty one for every scenario; the first must pass everything, the second must fail
   everything that requires work.
7. **Reading agent transcripts and reports, not just scores.** The first Haiku run passed 8
   of 9 checks, but its transcript showed ten turns spent on a denied file write and a
   PowerShell byte-order mark; fixing the skill and the harness brought the same task to 9 of
   9 in six turns. Later, reading the reports showed Haiku translating the English word
   "edition" into the wrong Ukrainian term: the fix was to remove the word from everything
   the model reads, not to add another banned word.
