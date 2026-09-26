# Methodology

What the numbers in `summary.json` mean, how they are computed, and how far they can be
trusted. Read this when the user asks "how did you get that", when a reliability verdict needs
explaining, or when choosing between `per_million` and `absolute`.

## 1. From a topic to articles

1. **Entity.** The query is searched on Wikidata in its own language; if that finds nothing,
   the English wording (`query_en`) is searched instead and the same rules apply. A candidate
   whose label or alias equals the query (ignoring case) is an exact match; a single hit or a
   single exact match is taken. Several exact matches are homonyms, and nearly every common
   word has some (a band called "Astronomy"). The meaning comes from the agent, which knows
   the conversation: when it states one (`meaning`, e.g. a chemistry app asking about
   "Mercury"), the pipeline never overrules it with data and returns the candidates (exit
   code 3, `ambiguous_topic`, each with the requested editions that have an article) for the
   agent to pick from or to ask the user. When no meaning is stated, the default is the item
   that covers strictly more requested editions *and* that Wikidata ranks first ("English
   language" resolves to *English*, 5 of 5 editions, not *English studies*, 3); if the two
   signals disagree, the candidates go back to the agent. Because search goes by spelling, any
   pick may still be the wrong meaning (Ukrainian "Меркурій" is the planet; the element is
   "ртуть"), so every summary names the analysed entity with its description and the other
   meanings of the name, and the agent checks it against the conversation.
   When no item is named like the query, a full-text search of Wikipedia (the query's own
   edition, then the requested ones) is a guess, so it is never measured: the items of the
   articles it finds come back as candidates (`ambiguous_topic` with `from_search`), and the
   agent takes one only when the conversation clearly means it, or else asks the user for a
   link. When the search finds no article with an item either, the run stops with
   `topic_not_found` and the agent asks for a link to an article in any language
   (`article_url`).
2. **Main article per edition.** Wikidata sitelinks give the article title in each requested
   edition. No sitelink -> a full-text search in that edition by the item's local label, then by
   the query, marked `search_fallback` (lower confidence). A search hit bound to a *different*
   Wikidata item is rejected (searching Polish Wikipedia for "intermittent fasting" returns an
   article on oxidative stress). Nothing acceptable -> the run stops *before any pageviews are
   fetched* and asks the user what to measure there (exit code 3, `missing_article`), because
   every replacement measures something else and only the user knows which is acceptable:
   - a **redirect** under the topic's local name (often into a section of a wider article):
     only visits under that name, a lower bound;
   - a **broader article** (Wikidata `subclass of` / `part of`): an upper bound, most readers came
     for the wider subject;
   - an article that **mentions** the topic (exact-phrase search by the local name; English
     wording is never searched in another language, where it is almost always a citation):
     the numbers describe that article;
   - **skip**: the edition is reported as *no article*, never as zero interest.
   Each option comes with its mean monthly views over the last 12 months, and the question says
   which Wikidata item the topic is and in how many languages it has an article. A chosen
   substitute is measured alone, named next to its edition in every table
   and chart (`pl.wikipedia (Post)`), never wins a headline or a ranking unless it is a redirect,
   and lowers reliability (see section 7).
3. **Redirects.** The Pageviews API counts redirect titles separately; the views of redirects
   to the main article are added to it (a reader who typed the redirect read the article).

What is measured is therefore one series per (topic, edition): the main article with its
redirects, the same Wikidata item in every edition.

## 2. Data

- Source: Wikimedia Pageviews API, monthly buckets for metrics, daily buckets for spike
  detection, `agent=user` by default (excludes crawlers and detected automated traffic).
- The whole edition's monthly total is fetched too: for normalisation, and to tell a change in
  the topic from a change in the edition (section 5).
- Missing buckets are kept as gaps, never filled; they lower `completeness`.
- Data exists from 2015-07. The current month is partial and excluded from the default period.

## 3. Normalisation

`per_million = article views / edition views * 1,000,000`. Editions differ in size by orders of
magnitude and their total traffic drifts over time (mobile shifts, bot filtering changes,
holidays). Per-million removes both effects and answers "what share of this audience's
attention does the topic get". Absolute views are reported alongside as audience size.

## 4. Metrics (per series)

| Metric | Definition | Reads as |
|---|---|---|
| `views_total`, `views_avg` | sum and mean of observed monthly views | audience size |
| `per_million_avg` | mean of the normalised series | attention share |
| `growth_yoy` | sum of matched months in the last 12 / sum of the same months in the previous 12 - 1 (needs 24 months and at least 9 observed pairs) | year-over-year change |
| `growth_halves` | sum of matched months in the second half / sum in the first half - 1; equal-length halves, central month excluded for odd windows (needs 4 months and >= 75 % observed pairs) | fallback growth for short windows |
| `slope_per_year` | Theil-Sen slope of log(value), expressed as change per year | robust growth rate, immune to a few outliers |
| `trend_p_value` | Mann-Kendall test for a monotonic trend (needs 8 months) | below 0.05: the direction is unlikely to be noise |
| `trend_direction` | rising / falling when significant, else flat | the headline direction |
| `seasonality_strength` | share of variance explained by month-of-year after detrending (needs 24 months) | high values: school year, holidays, weather |
| `spike_share` | share of daily traffic that is excess above the median on spike days (a spike day exceeds median + 5 robust deviations and twice the median) | growth driven by news, not by durable interest |
| `volatility_cv` | coefficient of variation of the detrended series | stability |
| `automated_share` | automated / (automated + user) for the canonical main article, using months observed in both traffic classes; excludes redirects | main-article bot suspicion |

Growth, slope, trend and volatility are computed on the normalised series when it is
available, so they describe attention share, not raw traffic.

Growth compares only pairs with both observations present; a gap excludes that month from
both sums. For year-over-year growth, pairs are the same calendar month in consecutive years.
Fewer than 75 % observed pairs, or a zero base, makes growth unavailable (`null`). This avoids
inventing growth from unequal observation counts, but missing months can still hide changes;
the completeness warning remains relevant. The halves fallback does not adjust for seasonality.

The automated-traffic diagnostic uses the same canonical main title for its user and automated
series, without redirects, which have no automated counterpart. Missing diagnostic data
remains unavailable.

## 5. The analysis window, its verdicts and the trust in them (v0.2)

**Window and context.** The *analysis window* is the period the user named (default: the last
24 complete months). The headline, each language's verdict, the comparison between languages
and the recommendation read it alone. The six years before its end are *context*: the main
chart shows them from their first January, the long view and the steps before the window are
observations weighted `context` and worded "in the wider context since 2021", and the PDF's
header says "Analysis period: 2024-09 – 2026-08 · Context on the charts: from 2021".

**Verdict** (`domain/trust.py`, `window_trend`), per language, on the attention share:

1. The monthly share with the seasonal rhythm divided out (the same profile as the season
   observation); bursts, plateaus and months where one day took over 20 % of the views are
   left out.
2. If a step lies inside the window (six months against six, at least ×1.25) and leaves at
   least 12 months after it, the trend is read from the step on: a level that fell once and
   then held has *stabilised*; one that fell and falls on *keeps declining*.
3. The Theil–Sen slope of the log share over that segment, in % a year. Within ±10 % a year
   the verdict is `stable`, else `growing` or `declining`. Under 12 months in the window or
   under 100 views a month: `insufficient_data`.
4. The reader sees the trend line's level at the segment's start and at the window's end
   ("8.9 → 8.2 per million"), the same numbers the chart writes on the line.

**Trust** (`assess_trust`), per verdict:

| Metric | How | Signal |
|---|---|---|
| `yoy_consistency` | months of the window's last twelve on the verdict's side of the same month a year earlier | ≥ 9 of 12 |
| `slope_pct_per_year`, `ci90` | Theil–Sen; 90 % interval from a moving-block bootstrap (3-month blocks, 1,000 resamples, fixed seed) | the interval leaves out 0 |
| `snr` | the segment's fitted change / standard deviation of its month-to-month log changes | ≥ 2 |
| `control_change` | median trend of the edition's control articles over the same months | ≥ 50 % of the article's, same way: the edition moved, not the topic |
| `breakpoints[]` | every step of the history (×1.35) and the one the verdict starts at; each with the control's change the same month, renames within a month (move log of the title and its redirects), the trends before and after | `artifact` if the control moved ≥ 50 % as much the same way or the article was renamed; `real` otherwise; `unknown` without control data |
| `max_day_share` | the largest one-day share of a month's views in the window | > 20 %: the month is a spike, left out of the slope |
| `segment_slopes` | the trends before and after each step | both within ±10 % a year: "a step, not a trend" |
| `volume_floor` | mean views a month over the window | < 100: `insufficient_data` |

| Verdict | Rule | Confidence |
|---|---|---|
| `growing` / `declining` | three signals: year on year, interval without 0, signal/noise | 3 high, 2 medium, 0–1 low |
| `growing` / `declining` | the control explains the change | low |
| `stable` | the whole interval within ±10 % a year | high |
| `stable` | the interval reaches past ±10 % a year | medium |
| `stable` | fewer than 12 months fitted | low |
| `insufficient_data` | — | low |

`reasons[]` lists the codes and numbers behind the level, most telling first; the trust line
("Trust (cs): medium — down in 12 of 12 months year on year; −30 % a year [−38; −18]; the
change is within the noise (signal/noise 1.9); control articles +5 % a year; no renames.") is
built from them.

**Control basket.** Per edition, about a hundred articles drawn with a fixed seed from the
first 1,000 of the top list of the last complete month when the basket is built (the main
page and other namespaces left out); articles younger than two years and those in the list
for a burst (over 3× their median of the year before) are left out. Stored with its build
date next to the HTTP cache and reused for 180 days. Its median share trend and median change
of level at a month say what the whole edition did. When the basket or the move log cannot be
fetched, the trust goes without them and says so.

**Recommendation** (`application/recommend.py`): `choice` = the candidate with the strongest
verdict (growing > stable > declining), then the higher trust, then the larger audience,
named even when none grows ("if you pick one"); `why` = each candidate's verdict with its
trend line; `confidence` = the chosen verdict's trust; `next_check` = what the skill can run
itself: neighbouring articles through Wikidata (subclass of, different from, part of, has
part, facet of, said to be the same as) with an article in the chosen edition, else further
large editions that have the article; a check outside Wikipedia only when neither is left.

**Names.** An item is named by the title of its article in the report language's Wikipedia
("веганство" for Q181138 in Ukrainian, where Wikidata's label is "веганізм"), lower-cased when
it is a common noun (Wikidata's English label is).

**Numbers.** Before the PDF is written every number of its text (headline, verdict, trust and
recommendation lines, the story, the meaning) is checked against the result's fields within
the rounding it is written with; a number nobody computed stops the render. The views chart
shows three significant digits and computes its percentages from the shown values.

Every threshold lives in `TrustSettings` and can be set with `WIKI_INTEREST_TRUST_<NAME>`;
each run's `method.md` lists the values in force and each verdict's metrics.

## 5b. The earlier answer: size, momentum, the edition, confidence

The fields below (`assessments`, `decision`) are kept for `summary.md` and the evaluation
harness; the headline and the recommendation now come from section 5.

The report leads with an answer built by fixed rules (`AssessmentSettings`), so the same
numbers always give the same words and no reader has to weigh five percentages.

- **Size of interest** is the mean share of attention: views of the article per million views
  of the whole edition. There is no absolute scale (40 per million is a lot for a chess
  opening and little for a pop star), so size is only stated against the other audiences of
  the same report: the largest, a *similar* one (the largest is less than 1.2x it) or a
  *smaller* one. A report about one audience states the number and no size class. Without
  normalisation, monthly views take the place of the share.
- **Momentum** is growing or declining only when the Mann-Kendall test is significant in the
  direction of the headline change (year over year, else halves) and that change is at least
  5 %; otherwise there is *no clear trend*. A significant -2 % is not a decline worth acting on,
  and a -30 % the test cannot confirm is not a trend.
- **Against the edition**: the article's views and the whole edition's views over the same
  months. The topic *gains* share of attention when its share rose by at least 5 %, *loses* it
  when it fell by as much, and *keeps pace* otherwise. A falling article in a falling edition
  can still gain ground; this line says which.
- **Robustness**: do the last months confirm the long-term direction? The share's change in
  the last three months against the same months a year earlier (seasons cancel out; the
  article's change against the edition's) is compared with the long-term momentum. It
  *confirms* the trend when it moves the same way by at least 5 % (or, without a trend, stays
  within 5 %); it is a *mixed signal* when it is flatter than that; a *possible turn* when it
  moves the other way by 5 % or more. It *cannot be judged* when the reliability verdict
  (section 7) is low, the audience has fewer than 300 views a month (three months are noise),
  the period is too short for a trend, or there is no comparison with a year earlier. The
  report states this per audience in words, with the numbers, instead of a trust score.
- **The data** in one line: how many months, whether any are missing, whether bursts drive
  the result, and any concern the reliability rules raised. The trend test itself is in
  `method.md`, not on the page.

Size and momentum give each audience an outcome:

| | growing | no clear trend | declining |
|---|---|---|---|
| **largest or similar** (higher interest) | strong candidate for the next check | check whether the visible interest turns into real demand | check whether the visible interest turns into real demand |
| **smaller** (lower interest) | early signal; check it is not a low-base effect | weaker signal for the next check | weaker signal for the next check |
| **only audience** | growth signal to confirm | existing audience, no growth signal | no growth signal |

Low reliability, an unmeasurable trend, a substitute article or a missing article override the
table. Each outcome line also says whether recent months confirm it. The conclusion names the audience for the next check: the largest growing one (or a
smaller growing one, flagged as early), else the largest one; for a ranking, the ranking's
order decides, and when the ranking's first and the largest differ, both are named. The next
step always points to an independent source of demand (for example Google Trends, search
volume or a small ad test), because page views do not show willingness to pay.

### Observations: what the report text is made of

The report does not retell the charts: the code turns the monthly series into observations,
true statements in plain English with the numbers they quote, and the agent explains the ones
that answer the user's question. The detectors read the attention share (the article's views
per million views of its edition) over up to six years before the period ends, whatever
period the charts show: a trend, a wave, a season or a step needs years to be told apart
from noise. A period the user named is read on its own; the season still on the whole
window. The level and the long view read calendar years: "now" is the last calendar year (a
partial one averaged over the months it has, the last full year if it has fewer than 3), the
long trend reads full calendar years only. A change compares like with like: "now" against
the same months a year earlier (2025 against 2024; January–August 2026 against
January–August 2025, so a partial year's missing season does not read as a fall), the last
3 months against the same months a year earlier.

| Observation | Fires when |
|---|---|
| `size` | always: how often the article is opened in the last calendar year, and in the first full year of the window; a partial year whose months usually run 10 % or more from the topic's yearly level says so |
| `long_term` | at least 3 full calendar years: a steady decline or rise (the last full year below 0.7 or above 1/0.7 of the first, falling or rising in all but one year), a wave (a middle year peaks above the first and the last is below 3/4 of the peak), or a flat range |
| `vs_edition` | 24 months, and every month of "now" and of the same months a year earlier: the change of the article's views, of the edition's, and of the share; a share change beyond ±10 % gained or lost attention, within it moved with the edition; says whether the fall is Wikipedia losing readers or the topic |
| `season` | 3 years: the median over years of each calendar month against the median of the 13 months centred on it (a trend makes no season); a school-year rhythm (a September–November peak above +60 % and a summer below −15 %), another rhythm (spread above 30 points), or none; a timing or an audience only when the peak month was among the two strongest of every year for at least 4 years, otherwise "limited evidence" |
| `spike` | a month more than 3 times what that calendar month usually brings, the next month back |
| `wave`, `unusual` | 3 or more months in a row above 3 times the median of up to 12 months before them (at least 6 known), and the first month after back under that bar: a run to the end of the data is a new level, not a wave, and a steady rise never makes one; flat (at least 9 months, highest below twice the lowest) and abrupt reads as automated traffic (a caution) |
| `step` | the largest change of the mean level between the six months before and after a month, the season removed, above 1.35 times; says whether the edition changed at the same time |
| `recent` | the last 3 months against the same months a year earlier, compared with the year: continues, slower, faster, stopped |
| `editions` | one topic in two editions over "now": where the audience (views a month) is larger ("much" from 3 times, "about as often" under 1.25), whether the gap holds against each Wikipedia's size (attention share), where the views went against a year earlier ("more sharply" beyond 10 points), whether each gained, held or lost its share; the decision gives the trade-off (a larger audience against a growing one) |
| `topics` | several topics of the user's in one edition, against each other |
| `decision:*` | what the above imply for the next check, never an investment call: when to be ready (a peak above +25 % that came every year), which audience (school readers), where to look (two editions), a signal per edition from its views and attention share |
| `headline` | one topic: the answer in one sentence without numbers, over the charts' window |
| `caution:*` | an edition without an article, measured through a substitute, or with data too weak |

Each observation has a weight: `caution` (the text must carry it), `high`, `medium`, `low`,
`context`, `decision`.

### Who writes the text

The observations and every number are the code's. The sentences in the report are the
agent's: `run.py` writes the observations into `facts.json` with the rules and a worked
example, and the agent writes `narrative.json` in the user's language: a story of two to
four paragraphs, the meaning (it explains the code's recommendation) and one line of limits.
The headline, the verdict and trust lines, the recommendation line and the next check are
the code's (section 5). Every paragraph lists the observations it relies on. `render.py --narrative`
accepts the text only when:

- every number in a paragraph is one of the observations it cites (within the rounding it
  was written with), and every cited id exists;
- the story cites at least one caution or high observation, the meaning a decision one, and
  every caution is cited somewhere;
- the meaning cites the recommendation observation and names its choice, and every block
  keeps its length;
- one term per measure: "частка уваги" / "доля внимания" / "attention share", "перегляди",
  "мовний розділ"; a few Ukrainian wordings a cheap model got wrong are rejected with the
  right one ("порівняно з", "перегляди", "інтерес", "в абсолютних");
- no block counts back from today ("five years ago") instead of naming the period, counts
  views as people, or names a country for an edition; the headline and the story never call
  views demand; no block uses statistical jargon or "1 in N" (word lists for en, uk, ru,
  pl, cs, de and the countries of common editions; other languages skip these checks).

- with several editions of a topic (or several topics), the story cites a comparison
  observation (`editions:*`, `topics:*`) and the meaning its trade-off
  (`decision:editions:*`): the text compares the editions instead of telling each apart.

A rejected text comes back with the reasons; after the second rejection the report keeps
the code's own text, in English: the comparison first, then each edition's cautions and one
feature of its own; the trade-off as the meaning; the headline observation as the headline;
the next step names the edition whose views grow, or else the larger audience. An edition
measured through a substitute article gets its own observations and a caution, but is never
compared with the topic. The chat answer is
not written separately: the code lays out the checked blocks, adds the item analysed, a few
next steps and the path to the PDF, so the user reads the same checked text as the PDF.

## 6. Further findings

Beyond the answer the report names what happened, with dates and sizes. Every detector is
conservative and says nothing rather than invent a pattern; thresholds are the defaults of
`FindingsSettings` and `InsightSettings`.

| Finding | How it is found | Stated when |
|---|---|---|
| Level shift | the best two-level split of log values (at least 6 months each side) | levels differ by >= 25 %, the difference is >= 4 standard errors, and the step fits the series clearly better than a straight line (so a steady trend is never dated as an event) |
| Burst | a day is at least 2.5x the median of the 45 days on either side, 5 robust deviations and 50 views above it; burst days at most 2 days apart form one episode | the episode holds >= 0.5 % of the period's views; the largest one per edition is named with its dates, peak and share |
| Recent change | the last 3 months against the same 3 months a year earlier (seasons cancel out), next to the edition's own change | all six months observed and the change is >= 10 % |
| Season | on the article's whole monthly history since 2015-07, whatever the analysed period: observations divided by a Theil-Sen exponential trend, averaged per calendar month and scaled to a mean of 1 | always computed; stated only when solid: at least 5 full calendar years, the calendar explains >= 30 % of the variation, the peak and trough months differ by >= 25 %, and in >= 80 % of the years the peak month is among that year's two strongest months and the trough month among its two weakest. The text names the months it was computed on. Otherwise `facts.json` gives the reason (`short_history`, `weak`, `inconsistent`). It gets its own chart from >= 50 % explained, or when the user asked about timing (`report.seasonality: "show"`; a pattern that is not solid is then shown with its caveat) |
| Month that stands out | each month against the median of the 6 months on either side (which follows a trend); for the article's views, its share and the edition's traffic | at least 1.6x (or 1/1.6x) its surroundings and 2.5 robust standard deviations of all months' deviations, or at least 1.8x whatever the noise. Not a month the article's season explains (with >= 5 years of history), nor one high every year. Its probable cause: `possible_bot` when >= 85 % of the extra views came through one access method (desktop, mobile web, app) while the others stayed below 1.3x, or automated traffic rose 3x; `event` when two methods rose 1.5x or daily views show a burst; `edition` when the edition moved and the article did not; else `unknown`. In the 24 months behind the headline change, the change is also given without that month and the same month a year off |
| No article / other subject | an edition without an article, or measured through a broader or mentioning substitute | always, first, so a gap is never read as zero interest |

The same statement for several editions becomes one line; at most five findings are kept,
strongest first (the PDF shows two, `summary.md` all of them).

## 7. Reliability verdict

Named rules, each yielding pass / warn / fail (info when not applicable). Thresholds are the
defaults of `ReliabilityThresholds`; the report prints the reason of every rule that is not a
pass.

| Rule | pass | warn | fail |
|---|---|---|---|
| `window_length` | >= 24 months | 12-23 | < 12 |
| `completeness` | >= 95 % of months present | >= 80 % | below |
| `spikes` | spike share < 20 % | 20-40 % | > 40 % |
| `trend` | p < 0.05 | not significant | - |
| `resolution` | main article from a sitelink | found via search, or a redirect chosen as substitute | no article, or a broader/mentioning article chosen as substitute |
| `automated` | automated share < 30 % | never: the automated class is already left out of the numbers (`agent=user`); from 30 % a note that some bots may have passed the classifier | - |
| `volume` | >= 300 views/month | below | - |

Aggregation: any fail -> **low**; two or more warns -> **medium**; otherwise **high**. A low
verdict does not mean the numbers are wrong; it means a decision should not rest on them alone.

The data and the conclusion are kept apart. `facts.json` gives **data quality** as the worst
of the data rules alone (every rule above but `trend`: any fail -> low, any warn -> medium),
with the reasons; and the **conclusion** as the 12-month momentum and whether the recent
months confirm it (`confirmed`, `mixed`, `contradicts`, `insufficient`). The trend test's
p-value stays in `summary.json`; the reports never call a trend "statistically significant".

Every threshold of sections 5-7 can be changed without code, with a `WIKI_INTEREST_<NAME>`
environment variable (`WIKI_INTEREST_SEASON_MIN_YEARS=6`, `WIKI_INTEREST_MIN_MOMENTUM=0.1`,
`WIKI_INTEREST_ANOMALY_MIN_MULTIPLE=2`); see `wiki_interest/config.py`.

## 8. Comparison and ranking

- `compare`: rows per (topic, edition) with audience size, attention share per million views
  of the edition, the share change next to the article's and the edition's own view changes,
  the trend and the verdict.
- `rank`: each component is min-max normalised across the candidates (growth from
  `growth_yoy`, falling back to `growth_halves` then `slope_per_year`; volume as log10 of mean
  views; stability as 1 / (1 + volatility); reliability high 1 / medium 0.5 / low 0), combined
  with the user's weights, and halved for a low verdict so the ranking never promotes a signal
  it cannot trust. Profiles: **early niche** (fast growth, small audience), **growth market**
  (fast growth, large audience), **mature market** (flat), **declining**, **insufficient data**.

### Charts

- **Main chart**, every report ("Attention share over time"): the attention share (views
  without normalisation) of up to three audiences on one scale, over the context range. A
  pale line gives each month; the history's calendar years are quiet segments without
  values; the analysis window is shaded and carries each audience's trend line, bold, its
  level written at the start and, with the audience's name, at the end ("ru 8,2"): the
  numbers of the verdict line. Steps are marked always, a probable technical one
  (`artifact`) grey; a one-off burst when the text cites it. The last months are no longer
  shaded (no verdict reads them).
- **Average monthly views**, under it (not when the user asked for raw views): the twelve
  months before the last twelve and the last twelve, each audience's mean monthly views as
  bars on one scale, the values to three significant digits and the change computed from
  them. Under the last span, one row per audience: the window's verdict on its share, ▲
  growing, ≈ stable, ▼ declining.
- The labels of both are built when the report is rendered, in the report's language.
- **Further chart**, four or more audiences: the mean share (log axis) against its headline
  change, one point per audience.
- **Seasons**: the calendar-month profile, when section 6 says it deserves a chart and either
  the user asked about timing (`report.seasonality: "show"`) or the text cites the season
  (`season:*`, `decision:timing:*`, `decision:audience:*`), with the months it was computed
  on.

The PDF holds nothing that does not answer the question: no table of key numbers (the text
and the charts give them), no block on the robustness of the trend and no run caveats in the
footer (both in `summary.md` and `method.md`; the text carries the cautions that change the
answer). The footer defines the attention share and the windows, says that views show
interest, not willingness to pay, and that a language is not a country.

The palette is Okabe-Ito, readable with the common colour-vision deficiencies.

## 9. Limitations to state in every report

- The analysis measures reading of one main article and its redirects: a proxy for interest
  in the topic, not market size or willingness to pay.
- Editions differ in coverage and editor activity; a missing or thin article depresses the
  signal regardless of audience interest.
- Bot filtering upstream is imperfect; the `automated` and `spikes` checks catch only part of it.
- Short windows and small editions are noisy; the verdict reflects that.
