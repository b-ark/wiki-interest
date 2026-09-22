# Wikimedia API notes

Facts the adapters rely on, each verified against the live services on the date given.
Read this before changing anything under `wiki_interest/adapters/` or when a run reports
`UpstreamError` / `DataUnavailableError` and you need to know whether the API or the request
is at fault.

## Endpoints used

| Purpose | Endpoint | Adapter |
|---|---|---|
| Article views | `GET https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{project}/{access}/{agent}/{title}/{granularity}/{start}/{end}` | `WikimediaRestPageviews.per_article` |
| Project total views | `GET .../metrics/pageviews/aggregate/{project}/{access}/{agent}/{granularity}/{start}/{end}` | `WikimediaRestPageviews.aggregate` |
| Topic -> entity | `GET https://www.wikidata.org/w/api.php?action=wbsearchentities&search=&language=&uselang=&type=item&limit=` | `WikidataApi.search_entities` |
| Entity -> titles | `...?action=wbgetentities&ids=Q1\|Q2&props=sitelinks&sitefilter=ukwiki\|plwiki` | `WikidataApi.sitelinks` |
| Entity labels | `...?action=wbgetentities&ids=&props=labels&languages=uk\|en` | `WikidataApi.labels` |
| Related entities | `...?action=wbgetclaims&entity=Q333&property=P279` (one call per property) | `WikidataApi.related_entities` |
| Page identity | `GET https://{lang}.wikipedia.org/w/api.php?action=query&titles=&redirects=1&prop=pageprops&ppprop=wikibase_item` | `MediaWikiApi.page_info` |
| Redirects to a page | `...?action=query&titles=&prop=redirects&rdnamespace=0&rdlimit=max` (+ `continue`) | `MediaWikiApi.redirects_to` |
| Lead-section links | `...?action=parse&page=&prop=links&section=0&redirects=1` | `MediaWikiApi.lead_links` |
| Search fallback | `...?action=query&list=search&srsearch=&srnamespace=0&srlimit=` | `MediaWikiApi.search` |

All MediaWiki/Wikidata calls add `format=json`; Wikipedia calls also add `formatversion=2`
(pages as a list, real booleans for `missing`). Everything is a `GET`, so every response is
cacheable and retry-safe.

## Pageviews API (verified 2026-09-22)

- **Project spelling** is `uk.wikipedia` (no `.org`). `access`: `all-access | desktop |
  mobile-app | mobile-web`; `agent`: `all-agents | user | spider | automated`.
- **Title encoding**: spaces -> underscores, then percent-encode with *no* safe characters.
  `AC/DC` -> `AC%2FDC`, `What?` -> `What%3F`, `Астрономія` -> `%D0%90%D1%81...`. Verified that
  all three return data on en/uk wikipedia.
- **Dates**: per-article uses `YYYYMMDD`; aggregate uses `YYYYMMDDHH` and we always send hour
  `00`. For `monthly` granularity the range must cover whole months, so the adapter sends the
  last day of the end month (`20240331`, not `20240301`). Daily end dates are inclusive.
- **Timestamps in responses** are always `YYYYMMDDHH` with `HH = 00`, even for monthly data
  (`"2024010100"` = January 2024). The adapter keeps the first eight characters.
- **Response shape**:
  `{"items":[{"project","article","granularity","timestamp","access","agent","views"}]}`.
  Aggregate items have no `article` key.
- **404 means "no data", not "bad request"** (body: `{"detail":"The date(s) you used are
  valid, but we either do not have data for those date(s), or the project you asked for is not
  loaded yet ..."}`). Seen for: a title that does not exist in that edition
  (`pl.wikipedia/.../Post_przerywany`, any agent); any date before 2015-07-01; aggregate
  `automated` traffic before 2020 (`aggregate/pl.wikipedia/all-access/automated/monthly/
  2019010100/2019033100`). The adapter returns a series of `None` values aligned to the
  window, and the HTTP client caches the 404 like any other answer.
- **Automated agent history**: per-article `agent=automated` returns rows with `views: 0` for
  2016-2019 rather than 404, because the class only started being populated in 2020. Treat
  automated shares before 2020 as unknown, not zero.
- **Partial windows**: if an article was created inside the window the API returns only the
  buckets that have data; the adapter fills the rest with `None` so completeness is honest.
- **History starts 2015-07-01**. Requests with an earlier start raise `DataUnavailableError`
  before any network call.
- **Range length**: a single request may span years at daily granularity; there is no need to
  chunk by month.

## Wikidata (verified 2026-09-22)

- `wbsearchentities` returns `search[]` with `id`, `label`, `description` and
  `match: {type: "label" | "alias" | ..., language, text}`. Matching is case-insensitive.
  `exact_label_match` is true when the label (or a `label`-type match text) equals the query
  after casefolding; alias matches never count as exact.
- `wbgetentities` with an id that **was never created** (e.g. `Q99999999`) returns
  `entities: {"Q99999999": {"id": "Q99999999", "missing": ""}}`. With an id **outside the valid
  range** (`Q100000000000`) it fails the whole batch:
  `{"error": {"code": "no-such-entity", "info": "...", "id": "Q100000000000"}}` (HTTP 200).
  The adapter drops the id named in `error.id` and re-issues the batch.
- Sitelink keys are `<lang>wiki` with hyphens replaced by underscores (`zh_yuewiki`);
  `WikiProject.site_id` produces them. `sitefilter` restricts the output; editions without an
  article are simply absent. Verified: `Q1666254` (intermittent fasting) has `ukwiki`,
  `cswiki`, `enwiki`, `dewiki` and **no `plwiki`**.
- `wbgetclaims` returns `{"claims": {"P279": [statement, ...]}}`; when the entity has no such
  property the result is `{"claims": {}}` (not an error). A statement's target is
  `mainsnak.datavalue.value.id`; `snaktype` may be `novalue` or `somevalue` (no target) and
  `rank` may be `deprecated`; the adapter skips all three. Verified: `Q333` has `P279` ->
  `Q14632398` (natural science) among others.
- **Labels are not titles.** Wikidata labels of common nouns are lowercase (`Q333` uk label is
  `астрономія`; the uk.wikipedia title is `Астрономія`). Use sitelinks for titles and labels
  only for display; never compare the two for equality without casefolding.
- Batch limit: 50 ids per `wbgetentities` call for ordinary clients.

## MediaWiki Action API (verified 2026-09-22 on uk.wikipedia.org)

- Errors are HTTP 200 with `{"error": {"code", "info"}}`. Codes handled specially:
  `missingtitle` (parse of a nonexistent page -> empty link list). Anything else is raised as
  `ActionApiError` (non-retryable `UpstreamError`).
- `action=query` with `redirects=1` reports `query.normalized[]` (`астрономія` ->
  `Астрономія`, `Nonexistent_page` -> `Nonexistent page`) and `query.redirects[]`
  (`Astronomy` -> `Астрономія`) as `{from, to}` pairs; the adapter chains them to find each
  requested title's final page. Missing pages appear as `{"ns", "title", "missing": true}`;
  malformed titles as `{"title", "invalid": true}`.
- `prop=pageprops&ppprop=wikibase_item` gives `pageprops.wikibase_item` = `Q333`. Pages with
  no Wikidata item have no `pageprops` key.
- `prop=redirects` pages through `continue.rdcontinue`; the adapter follows `continue` by
  merging it into the next request.
- `action=parse&section=0&prop=links` returns `parse.links[]` with `ns`, `title` and
  `exists: true` for blue links (formatversion 2). Verified: 40 existing ns-0 links in the
  lead of `Астрономія`. Red links have no `exists` key and are dropped.
- Batch limit: 50 titles per `query` call.

## Client policy

- **User-Agent**: `wiki-interest/<version> (https://github.com/b-ark/wiki-interest)`, set via
  `Settings.user_agent`. Wikimedia's policy requires a descriptive agent with a contact; generic
  agents are throttled or blocked.
- **Concurrency**: `Settings.max_concurrency` (default 8) parallel requests, far below the
  ~100 req/s guideline; combined with the cache this keeps repeat runs at zero requests.
- **Retries**: connection errors, timeouts, HTTP 429 and 5xx are retried up to
  `Settings.max_retries` (default 5) times with exponential backoff and jitter (0.5 s base,
  30 s cap); a `Retry-After` header (seconds or HTTP date) is honoured up to 60 s. Other 4xx
  fail at once with `UpstreamError(retryable=False)`. Attempt and retry counts are exposed via
  `HttpJsonClient.stats` for provenance.
- **Cache TTLs** (`Settings`):
  - series whose window ends in the current month: `open_period_ttl_s` (24 h) because those
    months are still being written upstream;
  - series entirely in closed months: `closed_period_ttl_s` (`None` = forever; closed months
    are never restated);
  - Wikidata and MediaWiki lookups: `resolution_ttl_s` (7 days).
  The cache key is the full request URL with query parameters sorted by name.
