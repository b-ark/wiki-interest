# Methodology

What the numbers in `summary.json` mean, how they are computed, and how far they can be
trusted. Read this when the user asks "how did you get that", when a reliability verdict needs
explaining, or when choosing between `per_million` and `absolute`.

## 1. From a topic to articles

1. **Entity.** The query is searched on Wikidata in its own language. An exact label match wins;
   otherwise several plausible items mean the pipeline stops with exit code 3 and lists the
   candidates. Guessing here would silently analyse the wrong subject.
2. **Main article per edition.** Wikidata sitelinks give the article title in each requested
   edition. No sitelink -> a full-text search in that edition is tried and the result is marked
   `search_fallback` (lower confidence). Nothing found -> the edition is reported as
   *no article*, never as zero interest: a missing article says something about that
   Wikipedia, not about the audience.
3. **Bundle (`bundle: auto`).** A topic is broader than one page. Related concepts are collected
   at the Wikidata level, so the same concepts are used in every edition and the editions stay
   comparable: forward Wikidata relations of the main item and the articles linked from the
   lead section of the main article in each edition. A concept linked from the lead in at least
   half of the editions, or related on Wikidata, gets weight 0.5; other lead links 0.3; the
   main article 1.0. At most 15 related concepts. The composition is printed in every summary so
   the user can prune it (`exclude_titles`) or pin it (`bundle: manual`).
4. **Redirects.** The Pageviews API counts redirect titles separately; their views are added to
   the target article.

Two series are always analysed and reported: the weighted **bundle** and the **main article**
alone. If they disagree on direction, the reliability check `bundle` warns.

## 2. Data

- Source: Wikimedia Pageviews API, monthly buckets for metrics, daily buckets for spike
  detection, `agent=user` by default (excludes crawlers and detected automated traffic).
- The whole edition's monthly total is fetched too and used for normalisation.
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
| `growth_yoy` | last 12 months / previous 12 months - 1 (needs 24 months, both halves >= 75 % complete) | year-over-year change |
| `growth_halves` | second half of the window / first half - 1 (needs 4 months) | fallback growth for short windows |
| `slope_per_year` | Theil-Sen slope of log(value), expressed as change per year | robust growth rate, immune to a few outliers |
| `trend_p_value` | Mann-Kendall test for a monotonic trend (needs 8 months) | below 0.05: the direction is unlikely to be noise |
| `trend_direction` | rising / falling when significant, else flat | the headline direction |
| `seasonality_strength` | share of variance explained by month-of-year after detrending (needs 24 months) | high values: school year, holidays, weather |
| `spike_share` | share of daily traffic that is excess above the median on spike days (a spike day exceeds median + 5 robust deviations and twice the median) | growth driven by news, not by durable interest |
| `volatility_cv` | coefficient of variation of the detrended series | stability |
| `automated_share` | automated / (automated + user) where the API provides it | bot suspicion |

Growth, slope, trend and volatility are computed on the normalised series when it is
available, so they describe attention share, not raw traffic.

## 5. Reliability verdict

Named rules, each yielding pass / warn / fail (info when not applicable). Thresholds are the
defaults of `ReliabilityThresholds`; the report prints the reason of every rule that is not a
pass.

| Rule | pass | warn | fail |
|---|---|---|---|
| `window_length` | >= 24 months | 12-23 | < 12 |
| `completeness` | >= 95 % of months present | >= 80 % | below |
| `spikes` | spike share < 20 % | 20-40 % | > 40 % |
| `trend` | p < 0.05 | not significant | - |
| `resolution` | main article from a sitelink | found via search | no article |
| `automated` | automated share < 30 % | above | - |
| `volume` | >= 300 views/month | below | - |
| `bundle` | main and bundle agree | disagree | - |

Aggregation: any fail -> **low**; two or more warns -> **medium**; otherwise **high**. A low
verdict does not mean the numbers are wrong; it means a decision should not rest on them alone.

## 6. Comparison and ranking

- `compare`: rows per (topic, edition) with attention share, audience size, growth and the
  verdict; differences are stated in percentage points of growth.
- `rank`: each component is min-max normalised across the candidates (growth from
  `growth_yoy`, falling back to `growth_halves` then `slope_per_year`; volume as log10 of mean
  views; stability as 1 / (1 + volatility); reliability high 1 / medium 0.5 / low 0), combined
  with the user's weights, and halved for a low verdict so the ranking never promotes a signal
  it cannot trust. Profiles: **early niche** (fast growth, small audience), **growth market**
  (fast growth, large audience), **mature market** (flat), **declining**, **insufficient data**.

## 7. Limitations to state in every report

- Wikipedia readership is a proxy for curiosity, not for willingness to pay.
- Editions differ in coverage and editor activity; a missing or thin article depresses the
  signal regardless of audience interest.
- Bot filtering upstream is imperfect; the `automated` and `spikes` checks catch only part of it.
- The bundle composition affects the numbers; both bundle and main-article results are shown.
- Short windows and small editions are noisy; the verdict reflects that.
