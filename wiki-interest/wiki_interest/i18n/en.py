"""English message catalog, the only one: other languages come from the agent's translations.

Keys are namespaced (``reliability reason``, ``label``, ``report section``, ``table column``,
``agent summary``, ``chart``) so a missing translation is easy to locate. Templates use
:meth:`str.format` fields; shares are formatted as whole percentages (``{share:.0%}``) and
p-values with three decimals (``{p_value:.3f}``) inside the template so every language can
choose its own presentation without code changes.
"""

from __future__ import annotations

__all__ = ["MESSAGES"]

MESSAGES: dict[str, str] = {
    # -- reliability reasons (produced by the reliability rules) -----------------------------
    "window_length.ok": "{months} months of data: enough for year-over-year comparison",
    "window_length.too_short": "Only {months} months of data: too short for a trend assessment",
    "completeness.ok": "No gaps in the monthly data",
    "completeness.gaps": "{missing_months} months without data ({share:.0%} of the period)",
    "completeness.sparse": (
        "{missing_months} months without data ({share:.0%} of the period): the series is too sparse"
    ),
    "spikes.unavailable": "Daily data is unavailable, so spikes could not be assessed",
    "trend.unavailable": "Too few points for a trend test",
    "resolution.sitelink": "Article found through Wikidata: the mapping is reliable",
    "resolution.search_fallback": (
        'Article found by full-text search ("{title}"): verify that it is the right one'
    ),
    "resolution.manual": "Article titles were provided manually",
    "resolution.not_found": (
        "No article in this edition: absence of an article is not zero interest"
    ),
    "automated.low": "Automated traffic is {share:.0%}: bot influence is small",
    "automated.high": "Automated traffic is {share:.0%}: bots may inflate the numbers",
    "automated.unavailable": "Automated traffic data is unavailable for this edition and period",
    "volume.ok": "About {views_avg:,.0f} views per month: enough for a stable signal",
    "volume.low": "Only about {views_avg:,.0f} views per month: the signal is noisy",
    # -- labels ------------------------------------------------------------------------------
    "level.high": "high",
    "level.medium": "medium",
    "level.low": "low",
    "direction.rising": "rising",
    "direction.falling": "falling",
    "direction.flat": "flat",
    "direction.unknown": "unknown",
    "profile.insufficient_data": "insufficient data",
    "bundle_status.found": "found",
    "bundle_status.found_via_search": "found via search",
    "bundle_status.not_found": "not found",
    "value.na": "n/a",
    # -- question line ---------------------------------------------------------------------
    "question.compare": "Compare interest in {topics} across {projects}",
    "question.rank": "Rank {projects} by interest in {topics}",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Wikipedia interest analysis",
    "report.sources": "Sources",
    "report.period": "Period",
    "report.generated": "Generated",
    "report.version": "Skill version",
    "report.data_through": "Data through",
    "report.ranking_table": "Ranking",
    "report.see_summary": "… the full list is in summary.md",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Topic",
    "col.project": "Edition",
    "col.reliability": "Reliability",
    "col.rank": "#",
    "col.score": "Score",
    "col.profile": "Profile",
    "col.rationale": "Why",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Answer",
    "summary.caveats": "Caveats",
    "summary.refine": "What can be refined",
    "summary.artifacts": "Files",
    "summary.clarification_needed": "Clarification needed",
    "summary.candidates": "Candidates",
    "summary.clarification_hint": (
        "If the conversation makes clear which meaning the user wants, set that candidate's qid "
        "yourself and say which meaning you chose; otherwise ask the user. Then rerun with "
        "topics[].qid."
    ),
    "summary.bundles": "Articles analysed",
    # -- chat answer (composed from the report text) ---------------------------------------
    # Whole first-person sentences: a bare "show which months" came back translated as an
    # order to the user ("покажіть").
    "chat.follow_ups": "What else I can do:",
    "chat.follow_up.seasons": "I can show which months of the year are strongest",
    "chat.follow_up.longer_period": "I can look at a longer period, back to 2015-07",
    "chat.follow_up.add_editions": "I can add more language editions to compare",
    "chat.follow_up.raw_views": "I can compare raw article views instead of the attention share",
    "chat.follow_up.method_page": "I can add a page with the method and the data checks",
    "chat.instant": "instant: the data are already loaded",
    "chat.pdf": "PDF report: {path}",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_views": "views per month",
    "chart.no_data": "No data for this period",
    # -- verdicts (composed by the summary builder) ---------------------------------------
    "verdict.rank.headline": "Most promising audience: {label} ({profile})",
    "verdict.none.headline": (
        "Nothing could be analysed for {topics}: no articles were found in {projects}"
    ),
    "rank.rationale.insufficient": "insufficient data for ranking",
    "note.not_found": "no article in this edition",
    "note.search_fallback": "article found via search",
    # -- limitations and next steps --------------------------------------------------------
    "limitation.coverage": (
        "Editions differ in how well they cover a topic; a missing or thin article depresses "
        "the signal regardless of audience interest."
    ),
    "limitation.language": (
        "A language edition is not a country: its readers live in many countries, and people "
        "of one country read several editions."
    ),
    "limitation.bots": (
        "Upstream bot filtering is imperfect; the automated-traffic and spike checks catch only "
        "part of it."
    ),
    "limitation.missing_titles": "These requested titles do not exist and were skipped: {titles}",
    "limitation.not_found": (
        'No article for {topic} in {projects}: those editions are reported as "no article", '
        "not as zero interest."
    ),
    "limitation.search_fallback": (
        "In {projects} the article was found by full-text search; verify it is the right one."
    ),
    "limitation.absolute": "Raw view counts were compared without normalising by edition size.",
    "next.extend_period": (
        "Extend the period (for example 36 or 60 months) to test whether the trend holds."
    ),
    "next.add_projects": "Add other editions to see whether the pattern is specific to {projects}.",
    "next.absolute": (
        "Compare raw views (normalization: absolute) to see audience size rather than share."
    ),
    "next.per_million": "Compare per-million shares to remove the effect of edition size.",
    "next.pin_title": (
        'To measure {projects} after all, drop its "skip" from topics[].substitutes and pick '
        "one of the pages the run offers for it."
    ),
    "next.research": "Research next: {label} ({profile}).",
    # -- editions without an article: the question and the substitutes ------------------
    "resolution.substitute_redirect": (
        'No article; measured through the redirect "{title}": only visits under this name count, '
        "so the numbers are a lower bound"
    ),
    "resolution.substitute_broader": (
        'No article; measured through the broader article "{title}": the numbers describe a wider '
        "subject, so they are an upper bound"
    ),
    "resolution.substitute_mention": (
        'No article; measured through "{title}", which only mentions the topic: the numbers '
        "describe that article, not the topic"
    ),
    "bundle_status.substitute": "substitute",
    "summary.missing_needed": "Decision needed: no article",
    "summary.apply_choice": "For the agent: value to put into topics[].substitutes",
    "gap.headline": (
        "Nothing has been measured yet: there is no article on the topic in {projects}. Choose "
        "what to measure there first."
    ),
    "gap.question": '{project} has no article on "{topic}".',
    "gap.term": '"{term}"',
    "gap.searched": "Searched for {terms}.",
    "gap.no_terms": (
        "The topic's name in this language is unknown, so no redirects or mentions were searched; "
        "give it as local_terms to search for them."
    ),
    "option.redirect": (
        'The redirect "{title}" leads to the article "{target}"{section}: {views} views/month. '
        "Counts only visits under this exact name, so it is a lower bound."
    ),
    "option.section": ', section "{section}"',
    "option.broader": (
        'The broader article "{title}": {views} views/month. An upper bound: most readers came for '
        "the wider subject."
    ),
    "option.mention": (
        'The article "{title}" mentions the topic: {views} views/month. The topic is a small part '
        "of it."
    ),
    "option.snippet": 'Passage: "…{snippet}…"',
    "option.skip": 'Leave {project} out: the report will say "no article", not zero interest.',
    "substitute.redirect": 'the redirect "{title}"',
    "substitute.broader": 'the broader article "{title}"',
    "substitute.mention": 'the article "{title}", which mentions the topic',
    "note.substitute": "no article; measured through {what}",
    "limitation.substitute": (
        '"{topic}" has no article in {project}; the numbers there come from {what}, as chosen.'
    ),
    "rank.rationale.substitute": (
        "not ranked: measured through another article, not the topic itself"
    ),
    "gap.entity": (
        'The topic is "{label}"{description} ({qid}). Languages with an article on it: {count}, '
        "including {languages}."
    ),
    "gap.entity_description": " — {description}",
    "gap.entity_nowhere": (
        'The topic is "{label}"{description} ({qid}); no Wikipedia edition has an article on it.'
    ),
    "gap.matched_en": (
        "It was found by its English name because the search in the query's language found "
        "nothing; make sure it is the right topic."
    ),
    "gap.no_entity": (
        "The topic was not found in Wikidata, so it is unknown which editions cover it; check the "
        "wording or give query_en."
    ),
    "summary.topic_line": 'Topic: "{label}"{description} ({qid}).',
    "summary.alternatives": "Other meanings of this name: {items}.",
    "summary.candidate_articles": "articles in {projects}",
    "summary.candidate_no_articles": "no article in the requested editions",
    "summary.not_found_needed": "Topic not found",
    "notfound.headline": (
        'Nothing was found for "{query}" on Wikidata or Wikipedia, neither by this wording nor by '
        "its English name."
    ),
    "summary.not_found_hint": (
        "Tell the user so plainly and ask for a link to a Wikipedia article, in any language, "
        "about what they mean. Put it into topics[].article_url in request.json and run again."
    ),
    "summary.which_meaning": 'Which meaning of "{query}"?',
    "summary.topic_only": (
        "Topic check only: the topic was identified and nothing else will run; there is no report, "
        "and that is expected. Tell the user which topic and articles were identified, and stop."
    ),
    # -- report findings, implications and charts --------------------------------------------
    "format.date": "{year}-{month:02d}-{day:02d}",
    "format.month_year": "{year}-{month:02d}",
    "basis.yoy": "last 12 months vs the 12 before",
    "basis.halves": "second half of the period vs the first",
    "basis.slope": "fitted trend per year",
    "basis.mixed": "per edition",
    "finding.unit.per_million": "per million edition views",
    "finding.unit.views": "views/month",
    "chart.season_title": "Months against the usual level",
    "chart.axis_season": "% against the usual level",
    "report.title_topic": "{topic}: interest on Wikipedia",
    "report.sources_names": "Wikimedia Pageviews API, Wikidata, MediaWiki API",
    "month.1": "January",
    "month.short.1": "Jan",
    "month.2": "February",
    "month.short.2": "Feb",
    "month.3": "March",
    "month.short.3": "Mar",
    "month.4": "April",
    "month.short.4": "Apr",
    "month.5": "May",
    "month.short.5": "May",
    "month.6": "June",
    "month.short.6": "Jun",
    "month.7": "July",
    "month.short.7": "Jul",
    "month.8": "August",
    "month.short.8": "Aug",
    "month.9": "September",
    "month.short.9": "Sep",
    "month.10": "October",
    "month.short.10": "Oct",
    "month.11": "November",
    "month.short.11": "Nov",
    "month.12": "December",
    "month.short.12": "Dec",
    "summary.redirects": "+{count} redirects",
    "finding.item.season": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "finding.no_article": (
        "{label}: there is no article on the topic in this edition, so it is reported as “no "
        "data”, not as zero interest."
    ),
    "finding.substitute": (
        "{label}: no article on the topic; the numbers come from {what} and describe a wider "
        "subject, so they are not compared with the other editions."
    ),
    "summary.missing_hint": (
        "Stop here: show these options to the user and ask which one to use for each edition, and "
        "end your answer with that question. Do not choose for the user and do not run again until "
        "they have answered. Then merge the chosen option's value from the block below into "
        "topics[].substitutes in request.json and run again."
    ),
    "answer.conclusion.unknown": "Extend the period before deciding.",
    "answer.conclusion.low_trust": (
        "The data are too weak for a conclusion; treat the numbers as indicative only."
    ),
    "answer.no_article": (
        "No article in {projects}: interest there could not be measured, which is not the same as "
        "no interest."
    ),
    "outcome.unknown": "{label}: the period is too short to judge the trend.",
    "outcome.low_trust": "{label}: the data are too weak for a conclusion.",
    "outcome.substitute": (
        "{label}: another article was measured, so this says little about the topic itself."
    ),
    "outcome.no_article": (
        "{label}: no article, so interest could not be measured (not the same as no interest)."
    ),
    "next_step.confirm": (
        "Next step: confirm the signal with an independent source of demand, for example Google "
        "Trends, search volume or a small ad test. Wikipedia views do not show willingness to pay."
    ),
    "next_step.confirm_for": (
        "Next step: confirm the signal for {label} with an independent source of demand, for "
        "example Google Trends, search volume or a small ad test. Wikipedia views do not show "
        "willingness to pay."
    ),
    "next_step.check_demand": (
        "Next step: before investing, check the existing demand with an independent source, for "
        "example Google Trends, search volume or a small ad test. Wikipedia views do not show "
        "willingness to pay."
    ),
    "next_step.check_demand_for": (
        "Next step: check the existing demand in {label} with an independent source, for example "
        "Google Trends, search volume or a small ad test. Wikipedia views do not show willingness "
        "to pay."
    ),
    "next_step.low_trust": (
        "Next step: extend the period or check the measured article, then confirm the signal with "
        "an independent source of demand, for example Google Trends, search volume or a small ad "
        "test."
    ),
    "evidence.months": "{months} months of data",
    "evidence.months_short": "only {months} months of data",
    "evidence.no_gaps": "no missing months",
    "evidence.gaps": "months missing: {missing_months}",
    "evidence.spikes_high": "bursts are {share} of views",
    "card.no_article": "no article",
    "value.per_million": "{value} per million",
    "report.vs_edition": "Is the topic growing faster or slower than its Wikipedia?",
    "report.vs_edition_basis": "Compared: {basis}",
    "report.decision": "What this means for the decision",
    "summary.decision": "What this means for the decision",
    "finding.item.season_tentative": "{label}: {peak_month} {peak}, {trough_month} {trough}",
    "limitation.scope": (
        "The analysis measures reading of one main article and its redirects: a proxy for interest "
        "in the topic, not market size or willingness to pay."
    ),
    "summary.findings": "Also worth knowing",
    "robustness.unknown": "{label}: robustness cannot be judged: {reason}.",
    "robustness.reason.low_trust": "the data are too weak (see the data line)",
    "robustness.reason.low_volume": "the audience is too small for a three-month comparison",
    "robustness.reason.no_recent": "there is no comparison with the same months a year earlier",
    "robustness.reason.no_trend": "the period is too short for a trend",
    "report.robustness": "How robust is this conclusion?",
    "report.recent_basis": "last {months} months vs the same months a year earlier",
    "report.data_line": "Data: {items}.",
    "report.data_concerns": "{label}: {items}.",
    "evidence.spikes_ok": "bursts do not drive the result",
    "outcome.recent.confirmed": "; recent months confirm it",
    "outcome.recent.mixed": "; recent months do not confirm it yet",
    "outcome.recent.reversing": "; recent months point the other way",
    "metric.article_views": "Article views",
    "metric.edition_views": "Edition traffic",
    "metric.attention_share": "Attention share",
    "metric.attention_share_unit": "article views per 1 million edition views",
    "headline.subject.share_one": "The attention share of {topics}",
    "headline.subject.share_many": "The attention share of {topics}",
    "headline.subject.views_one": "The number of article views on {topics}",
    "headline.subject.views_many": "The number of article views on {topics}",
    "headline.scope.both": "in both editions",
    "headline.scope.all": "in every edition",
    "headline.scope.everywhere": "everywhere",
    "headline.one.growing": "{subject} in {project} is growing{recent}",
    "headline.one.declining": "{subject} in {project} is falling{recent}",
    "headline.one.flat": "{subject} in {project} shows no clear trend{recent}",
    "headline.unknown": "The period is too short to tell where {subject} is heading.",
    "headline.all.growing": "{subject} is growing {scope}, {fastest}",
    "headline.all.declining": "{subject} is falling {scope}, {fastest}",
    "headline.all.flat": "{subject} shows no clear trend {scope}",
    "headline.fastest": "fastest in {label}",
    "headline.fastest_steadier": "faster and more steadily in {label}",
    "headline.mixed": "{subject}: {parts}",
    "headline.part.growing": "growing in {items}",
    "headline.part.declining": "falling in {items}",
    "headline.part.flat": "no clear trend in {items}",
    "headline.part.unknown": "too short a history in {items}",
    "happening.size_share": "{metric} ({unit}), average over the period: {items}.",
    "happening.size_views": "{metric} per month, average over the period: {items}.",
    "happening.change": "{metric}, {basis}: {items}.",
    "happening.pair": "{article} and {edition}",
    "happening.vs_edition": "{article} and {edition}, {basis}: {items}.",
    "kpi.metric": "Metric",
    "kpi.views": "Article views per month (average)",
    "kpi.share": "Attention share, per 1 million edition views (average)",
    "kpi.change": "{metric}, {basis}",
    "kpi.recent": "Do the last {months} months confirm the trend?",
    "robustness.value.confirmed": "yes",
    "robustness.value.mixed": "no, the share is steady",
    "robustness.value.mixed_flat": "no, the share moved",
    "robustness.value.reversing": "no, the direction changed",
    "robustness.value.unknown": "not enough data",
    "summary.topic_auto": "Matched automatically to {qid} by the stated meaning.",
    "spikes.low": (
        "Spike days account for {share:.0%} of views: the trend conclusion does not rest on "
        "individual bursts"
    ),
    "spikes.notable": (
        "Spike days account for {share:.0%} of views: part of the trend may come from news"
    ),
    "spikes.dominant": (
        "Spike days account for {share:.0%} of views: the trend rests on bursts, not on steady "
        "reading"
    ),
    "window_length.short": (
        "Only {months} months of data: the last 12 months cannot be compared with the 12 before"
    ),
    "limitation.short_window": (
        "Only {months} months of data: the last 12 months cannot be compared with the 12 before, "
        "and the trend test is weak."
    ),
    "rank.rationale": (
        "{profile}: attention share {growth} (headline window), {views} article views per month, "
        "reliability {level}"
    ),
    "verdict.rank.headline_declining": (
        "The attention share is falling in every edition; the relatively strongest audience: "
        "{label} ({profile})"
    ),
    "finding.level_shift": (
        "{label}: {metric} has been {change} against its earlier level since {start_month}, for "
        "{months} months now (average {before} → {after} {unit})."
    ),
    "finding.burst": (
        "{label}: burst of article views {start} – {end}, peak on {peak_day} with {peak_views} "
        "views in a day, ×{multiple} the usual {baseline}; the burst holds {share} of the article "
        "views in the period."
    ),
    "finding.burst_day": (
        "{label}: one-day burst of article views on {peak_day}: {peak_views} views, ×{multiple} "
        "the usual {baseline}; {share} of the article views in the period."
    ),
    "finding.season": (
        "{label}: article views by calendar month against the usual level: {peak_month} strongest "
        "({peak}), {trough_month} weakest ({trough})."
    ),
    "finding.group.season": (
        "Article views by calendar month, strongest and weakest month against the usual level: "
        "{items}."
    ),
    "finding.season_tentative": (
        "{label}: signs of seasonality in article views ({peak_month} {peak}, {trough_month} "
        "{trough} against the usual level); a longer history is needed to be sure, as each month "
        "was observed only a few times."
    ),
    "finding.group.season_tentative": (
        "Signs of seasonality in article views in {count} editions ({items}, against the usual "
        "level); a longer history is needed to be sure."
    ),
    "card.size": "Attention share, per 1 million edition views",
    "card.size_absolute": "Article views per month",
    "card.views_note": "article views per month: {items}",
    "card.momentum": "Attention share: change",
    "card.momentum_absolute": "Article views: change",
    "card.robustness": "Do recent months confirm the trend?",
    "edition.gaining": (
        "{label}: article views {article}, edition traffic {edition} → the attention share rises"
    ),
    "edition.losing": (
        "{label}: article views {article}, edition traffic {edition} → the attention share falls"
    ),
    "edition.in_line": (
        "{label}: article views {article}, edition traffic {edition} → the attention share holds"
    ),
    "robustness.confirmed.flat": (
        "{label}: stable. Attention share, {basis}: {change}, no clear trend; in the last {months} "
        "months against the same months a year earlier, article views {article} and edition "
        "traffic {edition}, so the share holds."
    ),
    "robustness.mixed.declining": (
        "{label}: mixed signal. Attention share, {basis}: {change}; but in the last {months} "
        "months against the same months a year earlier, article views {article} and edition "
        "traffic {edition}, so the share held steady. The long-term decline is visible, but it is "
        "unclear whether it continues now."
    ),
    "robustness.mixed.growing": (
        "{label}: mixed signal. Attention share, {basis}: {change}; but in the last {months} "
        "months against the same months a year earlier, article views {article} and edition "
        "traffic {edition}, so the share held steady. The long-term growth is visible, but it is "
        "unclear whether it continues now."
    ),
    "robustness.mixed.flat": (
        "{label}: mixed signal. Attention share, {basis}: {change}, no clear trend; but in the "
        "last {months} months against the same months a year earlier, article views {article} and "
        "edition traffic {edition}, so the share moved."
    ),
    "robustness.reversing.declining": (
        "{label}: possible turn. Attention share, {basis}: {change}; but in the last {months} "
        "months against the same months a year earlier, article views {article} and edition "
        "traffic {edition}, so the share rose. A few more months are needed to confirm it."
    ),
    "robustness.reversing.growing": (
        "{label}: possible turn. Attention share, {basis}: {change}; but in the last {months} "
        "months against the same months a year earlier, article views {article} and edition "
        "traffic {edition}, so the share fell. A few more months are needed to confirm it."
    ),
    "outcome.large_growing": (
        "{label}: higher attention share, and it is growing{recent} → a strong candidate for the "
        "next check."
    ),
    "outcome.large_flat": (
        "{label}: higher attention share, no clear trend{recent} → check whether the visible "
        "interest turns into real demand."
    ),
    "outcome.large_declining": (
        "{label}: higher attention share, but falling over the long run{recent} → check whether "
        "the visible interest turns into real demand."
    ),
    "outcome.small_growing": (
        "{label}: lower attention share, but growing{recent} → an early signal; check that it is "
        "not a low-base effect."
    ),
    "outcome.small_flat": (
        "{label}: lower attention share, no clear trend{recent} → a weaker signal for the next "
        "check."
    ),
    "outcome.small_declining": (
        "{label}: lower attention share, and falling{recent} → a weaker signal for the next check."
    ),
    "outcome.single_growing": (
        "{label}: the attention share is growing{recent} → a signal to confirm with a second "
        "source."
    ),
    "outcome.single_flat": (
        "{label}: the attention share shows no clear trend{recent} → an existing audience without "
        "an upward signal."
    ),
    "outcome.single_declining": (
        "{label}: the attention share is falling{recent} → no upward signal."
    ),
    "answer.conclusion.strong": (
        "{label} combines the highest attention share with growth: the strongest candidate for a "
        "closer look."
    ),
    "answer.conclusion.emerging": (
        "{label} has a lower attention share, but it is growing: an early signal; check that it is "
        "not a low-base effect."
    ),
    "answer.conclusion.no_growth": (
        "The attention share is not growing in any edition; {label} has the highest one, so it is "
        "the better candidate for further research, not a bet on expansion."
    ),
    "answer.conclusion.no_growth_ranked": (
        "The attention share is not growing in any edition; {label} ranks first, so it is the "
        "better candidate for further research, not a bet on expansion."
    ),
    "answer.conclusion.no_growth_split": (
        "The attention share is not growing in any edition; {label} ranks first and {largest} has "
        "the highest attention share: both are candidates for further research, not a bet on "
        "expansion."
    ),
    "answer.conclusion.single_growing": (
        "The attention share is growing: a signal worth confirming with a second source."
    ),
    "answer.conclusion.single_flat": (
        "The attention share shows no clear trend: an existing audience without an upward signal."
    ),
    "answer.conclusion.single_declining": (
        "The attention share is falling: Wikipedia gives no upward signal for this topic."
    ),
    "profile.growth_market": "large audience, attention share growing",
    "profile.early_niche": "small audience, attention share growing",
    "profile.mature_market": "large audience, attention share stable",
    "profile.declining": "attention share shrinking",
    "question.assess": "Assess where the attention share of {topics} is heading in {projects}",
    "trend.significant": (
        "Attention share trend is statistically significant (p = {p_value:.3f}, {direction})"
    ),
    "trend.not_significant": (
        "Attention share trend is not statistically significant (p = {p_value:.3f})"
    ),
    "robustness.confirmed.declining": (
        "{label}: steady decline of the attention share. Attention share, {basis}: {change}; in "
        "the last {months} months against the same months a year earlier, article views {article} "
        "and edition traffic {edition}, so the share keeps falling."
    ),
    "robustness.confirmed.growing": (
        "{label}: steady growth of the attention share. Attention share, {basis}: {change}; in the "
        "last {months} months against the same months a year earlier, article views {article} and "
        "edition traffic {edition}, so the share keeps rising."
    ),
    "chart.index_title": "Article views against edition traffic",
    "chart.index_subtitle": (
        "Index: mean of the first 12 months = 100, 3-month average. The article below its edition: "
        "the topic loses attention share."
    ),
    "chart.axis_index": "index, first 12 months = 100",
    "chart.series_article_months": "article views, month",
    "chart.series_article_smooth": "article views",
    "chart.series_edition_short": "edition traffic",
    "chart.note.event": "{month} ×{multiple}",
    "chart.note.possible_bot": "{month} ×{multiple}, possibly bots",
    "chart.note.edition": "{month} edition ×{multiple}",
    "chart.note.unknown": "{month} ×{multiple}",
    "chart.yoy_title": "{metric}: change against the same months a year earlier",
    "chart.yoy_subtitle": "Each point: the last 3 months against the same 3 months a year earlier.",
    "chart.axis_growth": "change, %",
    "chart.dumbbell_title": "{metric}: before and now",
    "chart.dumbbell_basis.yoy": "Mean of the previous 12 months and of the last 12 months.",
    "chart.dumbbell_basis.halves": "Mean of the first and of the second half of the period.",
    "chart.dumbbell_basis.mixed": "Mean of the earlier and of the later months.",
    "chart.series_before.yoy": "previous 12 months",
    "chart.series_after.yoy": "last 12 months",
    "chart.series_before.halves": "first half",
    "chart.series_after.halves": "second half",
    "chart.series_before.mixed": "before",
    "chart.series_after.mixed": "now",
    "chart.scatter_title": "{metric}: size and change",
    "chart.scatter_subtitle": "Right: a larger share; above the line: growing, below: shrinking.",
    "chart.axis_log": "{unit}, log scale",
    "chart.axis_per_million": "article views per million edition views",
    "chart.season_period": "Computed on {start} – {end}.",
    "report.happening": "What happened",
    "report.footer_share": (
        "Attention share: article views per 1 million views of the whole edition. Change: {basis}; "
        "recent months: {recent}."
    ),
    "report.footer_caveats": (
        "Views show curiosity, not willingness to pay; a language edition is not a country."
    ),
    "report.footer_months": "Months that stand out in the comparison: {items}.",
    "report.footer_month_item": "{label} {note}, change without it {change}",
    "report.footer_method": "How every number was computed: method.md",
}
