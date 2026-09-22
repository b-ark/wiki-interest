"""English message catalog: the reference key set every other catalog must match.

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
    "window_length.short": "Only {months} months of data: year-over-year growth is unavailable",
    "window_length.too_short": "Only {months} months of data: too short for a trend assessment",
    "completeness.ok": "No gaps in the monthly data",
    "completeness.gaps": "{missing_months} months without data ({share:.0%} of the period)",
    "completeness.sparse": (
        "{missing_months} months without data ({share:.0%} of the period): the series is too sparse"
    ),
    "spikes.low": "Spike days account for {share:.0%} of views: growth is not spike-driven",
    "spikes.notable": "Spike days account for {share:.0%} of views: part of the growth may be news",
    "spikes.dominant": "Spike days account for {share:.0%} of views: the growth is spike-driven",
    "spikes.unavailable": "Daily data is unavailable, so spikes could not be assessed",
    "trend.significant": "Trend is statistically significant (p = {p_value:.3f}, {direction})",
    "trend.not_significant": "Trend is not statistically significant (p = {p_value:.3f})",
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
    "bundle.consistent": "The main article and the whole bundle move in the same direction",
    "bundle.diverges": (
        "The main article ({main_direction}) and the bundle ({bundle_direction}) diverge: "
        "the conclusion depends on the bundle composition"
    ),
    # -- labels ------------------------------------------------------------------------------
    "level.high": "high",
    "level.medium": "medium",
    "level.low": "low",
    "status.pass": "pass",
    "status.warn": "warning",
    "status.fail": "fail",
    "status.info": "info",
    "direction.rising": "rising",
    "direction.falling": "falling",
    "direction.flat": "flat",
    "direction.unknown": "unknown",
    "profile.early_niche": "early niche",
    "profile.growth_market": "growth market",
    "profile.mature_market": "mature market",
    "profile.declining": "declining",
    "profile.insufficient_data": "insufficient data",
    "bundle_status.found": "found",
    "bundle_status.found_via_search": "found via search",
    "bundle_status.not_found": "not found",
    "source.sitelink": "Wikidata sitelink",
    "source.wikidata_relation": "Wikidata relation",
    "source.lead_link": "lead section link",
    "source.search_fallback": "search fallback",
    "source.manual": "manual",
    "role.main": "main",
    "role.related": "related",
    "role.manual": "manual",
    "unit.views": "views",
    "unit.per_million": "views per million",
    "value.na": "n/a",
    # -- question line ---------------------------------------------------------------------
    "question.compare": "Compare interest in {topics} across {projects}",
    "question.assess": "Assess whether interest in {topics} is growing in {projects}",
    "question.rank": "Rank {projects} by interest in {topics}",
    # -- report sections -------------------------------------------------------------------
    "report.title_default": "Wikipedia interest analysis",
    "report.question": "Question",
    "report.audience": "Context",
    "report.key_numbers": "Key numbers",
    "report.chart": "Chart",
    "report.charts": "Charts",
    "report.verdict": "Verdict",
    "report.reliability": "How much to trust this",
    "report.limitations": "Assumptions and limitations",
    "report.next_steps": "What can be refined",
    "report.sources": "Sources",
    "report.period": "Period",
    "report.projects": "Editions",
    "report.topics": "Topics",
    "report.generated": "Generated",
    "report.version": "Skill version",
    "report.data_through": "Data through",
    "report.bundle_composition": "Bundle composition",
    "report.comparison_table": "Comparison",
    "report.ranking_table": "Ranking",
    "report.notes": "Notes",
    "report.see_summary": "… the full list is in summary.md",
    "report.no_chart": "No chart was produced for this run",
    # -- table columns ---------------------------------------------------------------------
    "col.topic": "Topic",
    "col.project": "Edition",
    "col.views_avg": "Views/month",
    "col.per_million_avg": "Per million edition views",
    "col.growth_yoy": "Growth YoY",
    "col.growth_halves": "Growth H2/H1",
    "col.trend": "Trend",
    "col.reliability": "Reliability",
    "col.rank": "#",
    "col.score": "Score",
    "col.profile": "Profile",
    "col.article": "Article",
    "col.role": "Role",
    "col.weight": "Weight",
    "col.source": "Source",
    "col.status": "Status",
    "col.rationale": "Why",
    # -- agent summary ---------------------------------------------------------------------
    "summary.answer": "Answer",
    "summary.key_numbers": "Key numbers",
    "summary.trust": "How much to trust this",
    "summary.caveats": "Caveats",
    "summary.refine": "What can be refined",
    "summary.artifacts": "Files",
    "summary.clarification_needed": "Clarification needed",
    "summary.candidates": "Candidates",
    "summary.clarification_hint": (
        "Ask the user which entity they mean, then rerun with that qid in the request"
    ),
    "summary.bundles": "Articles analysed",
    "summary.bundle_count": "articles: {total} (related: {related})",
    # -- charts ----------------------------------------------------------------------------
    "chart.axis_per_million": "views per million edition views",
    "chart.axis_views": "views per month",
    "chart.footnote": "Source: {source} · Period: {period}",
    "chart.growth_title": "Year-over-year growth",
    "chart.trend_title": "Interest over time with trend",
    "chart.compare_title": "Interest by edition",
    "chart.no_data": "No data for this period",
    "chart.score_title": "Ranking score",
    "chart.axis_score": "score (0 = weakest, 1 = strongest in this set)",
    "chart.axis_growth": "growth year over year, %",
    "chart.growth_halves_title": "Growth, second half of the period vs first half",
    # -- verdicts (composed by the summary builder) ---------------------------------------
    "verdict.assess.headline": (
        "Interest in {topic} in {project} is {direction} ({growth} year over year); trust: {level}"
    ),
    "verdict.compare.share": "Highest attention share: {label} ({value} per million edition views)",
    "verdict.compare.share_absolute": "Most views: {label} ({value} views/month)",
    "verdict.compare.growth": "fastest growth: {label} ({growth})",
    "verdict.compare.decline": (
        "interest is not growing in any edition; smallest decline: {label} ({growth})"
    ),
    "verdict.compare.growth_unknown": "growth could not be measured",
    "verdict.rank.headline": "Most promising audience: {label} ({profile}, score {score})",
    "verdict.rank.headline_declining": (
        "Interest is declining in every edition; "
        "the relatively strongest audience: {label} ({profile}, score {score})"
    ),
    "verdict.none.headline": (
        "Nothing could be analysed for {topics}: no articles were found in {projects}"
    ),
    "verdict.bullet.pair": (
        "{label}: {per_million} per million edition views, {views} views/month, growth "
        "{growth}, trust {level}"
    ),
    "verdict.bullet.pair_absolute": "{label}: {views} views/month, growth {growth}, trust {level}",
    "verdict.bullet.not_found": "{label}: no article in this edition",
    "verdict.bullet.seasonality": (
        "{label}: strong seasonality ({strength} of variance): compare the same months "
        "year over year"
    ),
    "verdict.bullet.main_vs_bundle": "{label}: the main article alone is {direction} ({growth})",
    "rank.rationale": "{profile}: growth {growth}, {views} views/month, trust {level}",
    "rank.rationale.insufficient": "insufficient data for ranking",
    "note.not_found": "no article in this edition",
    "note.search_fallback": "article found via search",
    # -- limitations and next steps --------------------------------------------------------
    "limitation.proxy": (
        "Wikipedia readership measures curiosity, not willingness to pay: treat the result as "
        "a signal to verify, not as demand."
    ),
    "limitation.coverage": (
        "Editions differ in how well they cover a topic; a missing or thin article depresses "
        "the signal regardless of audience interest."
    ),
    "limitation.bots": (
        "Upstream bot filtering is imperfect; the automated-traffic and spike checks catch only "
        "part of it."
    ),
    "limitation.bundle": (
        "Numbers depend on which articles were counted; both bundle and main-article results "
        "are reported."
    ),
    "limitation.missing_titles": "These requested titles do not exist and were skipped: {titles}",
    "limitation.not_found": (
        'No article for {topic} in {projects}: those editions are reported as "no article", '
        "not as zero interest."
    ),
    "limitation.search_fallback": (
        "In {projects} the article was found by full-text search; verify it is the right one."
    ),
    "limitation.short_window": (
        "Only {months} months of data: year-over-year growth is unavailable and the trend test "
        "is weak."
    ),
    "limitation.absolute": "Raw view counts were compared without normalising by edition size.",
    "next.extend_period": (
        "Extend the period (for example 36 or 60 months) to test whether the trend holds."
    ),
    "next.add_projects": "Add other editions to see whether the pattern is specific to {projects}.",
    "next.prune_bundle": (
        "Exclude articles that do not belong to the topic (exclude_titles) or pin the list "
        "(bundle: manual)."
    ),
    "next.absolute": (
        "Compare raw views (normalization: absolute) to see audience size rather than share."
    ),
    "next.per_million": "Compare per-million shares to remove the effect of edition size.",
    "next.pin_title": "Provide the exact article title for {projects} via extra_titles.",
    "next.research": "Research next: {label} ({profile}).",
}
