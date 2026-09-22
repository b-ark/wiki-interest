# How the quality of this skill is measured

Unit tests check the code. They do not tell whether a cheap agent model, given only this
skill, answers a founder's question correctly, honestly and in the right language. This
directory holds the evaluation that does: realistic requests, run through a real agent
(Claude Haiku 4.5 in headless Claude Code), graded by code and by an LLM judge. The harness
that executes it lives outside the skill, in [`tools/skill-evals`](../../tools/skill-evals/),
so the skill package stays small.

## What is in here

| File | Purpose |
|---|---|
| `evals.json` | 12 scenarios: the three requests from the assignment, users writing in Ukrainian, Russian, English and Polish, four multi-turn follow-ups (longer period, main article only, raw numbers, more editions), an ambiguous topic that must produce a question, and a period that starts before the data does. |
| `oracle/<scenario>.json` | The requests a perfect agent would send for each turn. Used only to check the graders; never copied into the agent's sandbox. |
| `trigger_evals.json` | 17 short requests, 9 that should activate the skill and 8 near-misses that should not (editing Wikipedia, summarising an article, Google Trends, app analytics). |
| `results/` | Summaries of real runs: `benchmark.md`/`.json` per compared `SKILL.md` version, and the grader sanity check. Full transcripts stay in the harness's `runs/` directory. |

## How an answer is graded

Every scenario is graded on several independent properties rather than one blended score,
so a failure points at its cause.

**By code (deterministic, free, exact):**

- the agent ran `scripts/run.py` and did not query the Wikimedia API by hand;
- a one-page `report.pdf` exists;
- **every number in the answer appears in `summary.json`**, within rounding: this is the
  main defence against a cheap model inventing or miscomputing figures;
- when the analysis flagged reliability problems, the answer relays at least one of the
  reasons;
- the request the agent built matches what the user asked (question type, period, language,
  editions, normalisation, bundle mode);
- the ambiguous topic ends with a question and no report;
- the number of model turns stays within budget.

**By an LLM judge (Claude Sonnet, one call per criterion):** does the answer actually answer
the question, state the trust level with a reason, name the limitations, stay honest about
missing articles and declining interest, and use the user's language. The judge sees the
answer as untrusted data, is told not to reward length, and never learns which skill version
produced it.

## Checking the graders first

A grader that passes everything or fails everything produces confident nonsense. Before any
paid run, `skill-evals oracle` runs the real pipeline on the `oracle/` requests and grades two
synthetic agents per scenario: one that answers with `summary.md` verbatim, and one that does
nothing and says "I don't know". The first must pass every assertion, the second must fail
every assertion that requires work. Current result, 2026-09-22: 100 % and 0 %
([`results/oracle.md`](results/oracle.md)). The check already caught a bad scenario: the
English word "football" is genuinely ambiguous on Wikidata, while the user's Ukrainian
"футбол" is not.

## Comparing versions of `SKILL.md`

Each scenario runs several times per version in a fresh sandbox (a copy of the skill, an
empty workspace, the same warm HTTP cache so network noise does not differ between
versions). The benchmark reports pass rates per assertion and per judge criterion, turns,
tokens, cost and time, and the pairwise difference between versions next to the noise floor
(`1 / sqrt(scenarios x repetitions)`, about ±17 points for 12 scenarios and 3 repetitions).
A change counts as an improvement only when it exceeds that floor. Infrastructure failures
(timeouts, rate limits) are recorded separately and never scored as a wrong answer.

## Running it

```bash
cd tools/skill-evals
uv sync
uv run skill-evals oracle   -s ../../wiki-interest/evals/evals.json -k ../../wiki-interest
uv run skill-evals run      -s ../../wiki-interest/evals/evals.json -k ../../wiki-interest -n base --reps 3 --warm-cache ../../wiki-interest/.cache
uv run skill-evals compare  runs/base runs/<variant> --out ../../wiki-interest/evals/results/<variant>-vs-base
uv run skill-evals trigger  -c ../../wiki-interest/evals/trigger_evals.json -k ../../wiki-interest -n trigger
```

Requirements: `uv` and Claude Code (the harness finds the CLI on PATH or in the VS Code
extension). Runs use the Claude subscription of whoever runs them; no API key is needed.
