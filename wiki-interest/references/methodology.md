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
   When nothing matches at all, the run stops with `topic_not_found` and the agent asks for a
   link to an article (`article_url`).
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
   substitute is measured alone (no related articles), named next to its edition in every table
   and chart (`pl.wikipedia (Post)`), never wins a headline or a ranking unless it is a redirect,
   and lowers reliability (see section 7).
3. **Related articles as context (`bundle: auto`).** Readers of a topic also read its
   neighbours, and the report names them: forward Wikidata relations of the main item and the
   articles linked from the *prose* of the lead section of the main article in each edition
   (links in footnotes, citation templates, infoboxes and image captions are ignored, so ISSN
   or DOI never become "related"). Up to 15 concepts, ordered by relevance (Wikidata relation
   or a lead link in at least half of the editions first). Each is reported with its own mean
   monthly views and growth; **none is added into the topic's numbers**. A weighted sum was
   tried and dropped: which neighbours an edition has differs between editions, so the sum
   compared article sets, not interest, and its weights could not be justified to a reader.
   `bundle: main` shows no context; `bundle: manual` shows only `extra_titles`.
4. **Redirects.** The Pageviews API counts redirect titles separately; the views of redirects
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
| `automated_share` | automated / (automated + user) for the canonical main article, using months observed in both traffic classes; excludes redirects and related articles | main-article bot suspicion |

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

## 5. The answer: size, momentum, the edition, confidence

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
  the result, and any concern the reliability rules raised. The trend test itself is in the
  detailed reliability section of `report.md`, not on the page.

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

### Who writes the text

The states above (size, momentum, the edition, robustness, outcome, conclusion) and every
number are the code's. The sentences in the report are the agent's: `run.py` writes them
into `facts.json` with each number's metric, window and display form, and the agent writes
`narrative.json` in the user's language. `render.py --narrative` accepts the text only when:

- every number in it is one of the facts (within the rounding it was written with), and a
  percentage in the robustness text of an edition is one of that edition's;
- every sentence with a number names its metric with the term the agent declared;
- the headline is one sentence without numbers, and every measured edition has its
  robustness text, naming the edition;
- every caveat of `facts.caveats` is declared, and an edition it concerns is named in the
  chat answer;
- the descriptive blocks never call views demand, and no block uses statistical jargon or
  "1 in N" (word lists for en, uk, ru, pl, cs, de; other languages skip this check).

A rejected text comes back with the reasons; after the second rejection the report keeps
the code's own text, the template the agent started from.

## 6. Further findings

Beyond the answer the report names what happened, with dates and sizes. Every detector is
conservative and says nothing rather than invent a pattern; thresholds are the defaults of
`FindingsSettings` and `InsightSettings`.

| Finding | How it is found | Stated when |
|---|---|---|
| Level shift | the best two-level split of log values (at least 6 months each side) | levels differ by >= 25 %, the difference is >= 4 standard errors, and the step fits the series clearly better than a straight line (so a steady trend is never dated as an event) |
| Burst | a day is at least 2.5x the median of the 45 days on either side, 5 robust deviations and 50 views above it; burst days at most 2 days apart form one episode | the episode holds >= 0.5 % of the period's views; the largest one per edition is named with its dates, peak and share |
| Recent change | the last 3 months against the same 3 months a year earlier (seasons cancel out), next to the edition's own change | all six months observed and the change is >= 10 % |
| Season | observations divided by a Theil-Sen exponential trend, averaged per calendar month and scaled to a mean of 1 | always computed; mentioned when the calendar explains >= 30 % of the variation and the peak and trough months differ by >= 25 %. With less than five years of history (each month observed only a few times) it is stated as "signs of seasonality, a longer history is needed"; it gets its own chart only from five years and >= 50 % explained, or when the user asked about timing (`report.seasonality: "show"`) |
| No article / other subject | an edition without an article, or measured through a broader or mentioning substitute | always, first, so a gap is never read as zero interest |

The same statement for several editions becomes one line; at most five findings are kept,
strongest first (the PDF shows two, `report.md` all of them).

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
| `automated` | automated share < 30 % | above | - |
| `volume` | >= 300 views/month | below | - |

Aggregation: any fail -> **low**; two or more warns -> **medium**; otherwise **high**. A low
verdict does not mean the numbers are wrong; it means a decision should not rest on them alone.

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

## 9. Limitations to state in every report

- The analysis measures reading of one main article and its redirects: a proxy for interest
  in the topic, not market size or willingness to pay.
- Editions differ in coverage and editor activity; a missing or thin article depresses the
  signal regardless of audience interest.
- Bot filtering upstream is imperfect; the `automated` and `spikes` checks catch only part of it.
- Related articles are context with their own numbers, never added into the topic's.
- Short windows and small editions are noisy; the verdict reflects that.
