# Changelog

What changed in each version, the decisions behind it and what the evaluation on Claude
Haiku 4.5 measured. Pass rates come from `evals/results/`; commit ids are in this repository's
history. Thresholds in force are listed in `references/methodology.md`.

## Unreleased (after 0.2.0)

Changed:

- A follow-up's chat answer compares the verdicts of the two runs, not their numbers: a mean
  share over a longer period next to the old one read as growth.
- With three candidates or more, the recommendation names the next two in the same order;
  "which audiences to research next" expects a list.
- A step is a jump beyond the local trend: the threshold must hold on the visible levels and
  after the median slope of each half is subtracted. A steady fall of 36 % a year no longer
  reads as a row of steps; the reference case and Bitcoin are unchanged.
- When the user asks to add something (the season, topics or Wikipedias), the one-page limit
  is lifted and nothing is dropped; the season chart, which the layout used to drop first,
  now reaches the PDF.
- With no Wikipedia named, the agent asks which to look at and runs nothing; with one or
  more named, it uses exactly those and offers others only after the first report.
- The trend observation names the months of its trend line's levels, as the verdict line does.
- Charts hold up to three languages; with more, the recommended one and the two largest
  audiences. Documented as a limit, not changed.
- Published: v0.2 stage summaries in `evals/results/`, LICENSE, intermediate PDFs removed.

Measured: stage18 (29 scenarios × 3) 96.8 % pass, 94.8 % judge, 10.0 turns, $0.129 a case,
within noise of stage17; stage19b-ask 27/27 with the two new "ask which Wikipedias"
scenarios; stage19c-pages 6/6 on the two-page follow-ups.

## 0.2.0 — 2026-09-26

The verdict reads the analysis window; the history is context. Trust is computed. The
recommendation comes from code. Every number in the model's text is checked.

Added:

- `verdicts[]`: one per language on the attention share over the analysis window
  (`growing | stable | declining | insufficient_data`), read from the last step inside the
  window when at least 15 months follow it.
- `trust` per verdict: months up or down year on year, a 90 % block-bootstrap interval of
  the Theil-Sen slope, signal to noise, a control basket of about a hundred articles of the
  same Wikipedia, steps classified `real | artifact | unknown` against the basket and the
  article's rename log, one-day bursts, volume. `confidence` is `high | medium | low` with
  `reasons[]`.
- `recommendation`: `choice`, `why`, `confidence`, `next_check` (neighbouring articles
  through Wikidata, then more Wikipedias, then a source outside Wikipedia). Named even when
  nothing grows, and said so.
- The headline, verdict, trust and recommendation lines are written by code in en/ru/uk;
  the model writes the story and what it means, citing observations.
- Every number in the model's text must match a cited observation within its rounding;
  a mismatch is a render error, not a warning. Years, dates and unsigned numbers below 10
  are not checked. One term per measure.
- The topic is named as the Wikipedia of the report names its article.
- The views chart reads calendar years over the context; the share chart marks the window
  and draws each language's trend line with its end levels.

Decisions:

1. Hybrid, not templates: code decides and writes the short lines, the model writes prose.
   Fully templated text in three languages was unreadable.
2. Verdict from the segment after the last step inside the window, when 15 months or more
   remain; the step is named in the verdict and in the trust.
3. `stable` is within ±10 % a year of the Theil-Sen slope on the log share with the season
   divided out, so the threshold does not depend on the window's length.
4. "Now" is the last 12 months of the window against the 12 before, not the last calendar
   year; the comparison with the Wikipedia is about views only.
5. History before the window is context: its observations carry the weight `context` and
   start with "in the wider context since …". Bursts and plateaus before the window are not
   reported. The "last three months" highlight is gone.
6. The control basket: the last complete month's top list, a fixed seed, kept 180 days per
   Wikipedia. A control that explains a change lowers the trust and never changes the verdict.
7. No check that the prose contradicts the verdict: too many false rejections; meaning is the
   judge's job in the evaluation.
8. The fallback text of the history stays English. Charts are done only to what the
   assignment requires.
9. "edition" was removed from everything the model reads: Haiku translated it into the wrong
   Ukrainian term, and a banned-words rule barely helped (32 → 28 rejections); the source fix
   removed them.
10. The recommendation prints its reason (same verdict and trust: the larger audience decides).

Measured: stage16 94.9 % pass, 91.9 % judge, 11.2 turns, $0.140 a case; stage17 (calendar-year
views chart, reason in the recommendation, "edition" gone) 97.6 %, 93.6 %, 10.0 turns,
$0.131. The noise floor for 29 × 3 is about ±11 points.

Known gaps at 0.2.0: Ukrainian prose from Haiku still slips (a Latin word inside Cyrillic,
"twice as fast" for 1.5×; the judge catches these); the first basket build takes about two
minutes and 250 requests per Wikipedia.

## 0.1 — 2026-09-22 to 2026-09-26

- 2026-09-22: the package (contracts, adapters, domain statistics checked against
  `pymannkendall` and `scipy`, reliability rules, ranking, charts, PDF, CLI), `SKILL.md`,
  the evaluation harness with providers, graders, runner and report, the scenario suite and
  an oracle that checks the graders.
- 2026-09-23: `SKILL.md` v2 and v3 from the Haiku baseline (the model spent turns on a denied
  file write and a PowerShell byte-order mark); the report became a decision memo with the
  agent's own narrative; seasons over the whole history, monthly anomalies, data quality
  apart; one-page PDF with `method.md` and an optional appendix; the agent writes the report
  once and the chat answer is built from it; features the agent never used were dropped.
- 2026-09-24: a Wikipedia without the article gets broader articles offered, with links; the
  code composes the question and the agent sends it as it is; a follow-up says what changed.
- 2026-09-25 to 26: observations, true statements with their numbers, replace the retelling
  of charts; the level and the long view read calendar years; the attention share and the
  views by calendar year as charts; two Wikipedias are compared in the text and in the
  template; Wikipedia gives a signal, not an investment call; Russian and Ukrainian reports
  carry written interface labels. Harness: a resumed turn costs what it added, a failed
  judge keeps the agent's paid run for a regrade, the oracle works as a perfect agent does.

Measured: `evals/results/base-v1`, `v2-vs-base-v1`, `v3-vs-v2`.
