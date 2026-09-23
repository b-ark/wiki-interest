"""Re-record the contract fixtures from the live Wikimedia APIs.

Run by a maintainer, never by CI (the script refuses when ``CI`` is set and pytest does not
collect it because its name does not start with ``test_``)::

    uv run python tests/contract/record_fixtures.py            # all cases
    uv run python tests/contract/record_fixtures.py wikidata-*  # glob on case names

How it works: each case calls the real adapters through a cache that never hits but records
every URL the client stores (phase 1), then every recorded URL is fetched once more raw so the
fixture keeps the genuine status code and body, including 404 documents (phase 2). Fixtures
are written as ``fixtures/<case>-<YYYY-MM-DD>.json``; older recordings of the same case are
removed so the tests always replay the newest one.
"""

from __future__ import annotations

import fnmatch
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx

from wiki_interest.adapters.clock import SystemClock
from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.mediawiki import MediaWikiApi
from wiki_interest.adapters.wikidata import WikidataApi
from wiki_interest.adapters.wikimedia_rest import WikimediaRestPageviews
from wiki_interest.config import Settings
from wiki_interest.domain.models import Access, Agent, Granularity, WikiProject, Window
from wiki_interest.ports.clock import Clock

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
UK, PL, CS = WikiProject("uk"), WikiProject("pl"), WikiProject("cs")
MONTHLY_2024 = Window(Granularity.MONTHLY, date(2024, 1, 1), date(2024, 12, 1))
MONTHLY_2024_Q1 = Window(Granularity.MONTHLY, date(2024, 1, 1), date(2024, 3, 1))
DAILY_2024_03 = Window(Granularity.DAILY, date(2024, 3, 1), date(2024, 3, 31))
MISSING_QID = "Q99999999"
"""Reported by Wikidata as ``missing`` (never created)."""
IMPOSSIBLE_QID = "Q100000000000"
"""Rejected by Wikidata with ``no-such-entity``, failing the whole batch."""


@dataclass(frozen=True, slots=True)
class Gateways:
    """The three adapters a case may call."""

    pageviews: WikimediaRestPageviews
    wikidata: WikidataApi
    mediawiki: MediaWikiApi


type Case = Callable[[Gateways], object]

CASES: dict[str, Case] = {
    "pageviews-per-article-monthly-uk-astronomy": lambda g: g.pageviews.per_article(
        UK, "Астрономія", MONTHLY_2024, access=Access.ALL, agent=Agent.USER
    ),
    "pageviews-per-article-daily-uk-astronomy": lambda g: g.pageviews.per_article(
        UK, "Астрономія", DAILY_2024_03, access=Access.ALL, agent=Agent.USER
    ),
    "pageviews-aggregate-monthly-uk": lambda g: g.pageviews.aggregate(
        UK, MONTHLY_2024, access=Access.ALL, agent=Agent.USER
    ),
    "pageviews-per-article-404-pl-automated": lambda g: g.pageviews.per_article(
        PL, "Post przerywany", MONTHLY_2024_Q1, access=Access.ALL, agent=Agent.AUTOMATED
    ),
    "wikidata-search-intermittent-fasting-en": lambda g: g.wikidata.search_entities(
        "intermittent fasting", "en", limit=5
    ),
    "wikidata-sitelinks-q1666254": lambda g: g.wikidata.sitelinks(
        ["Q1666254", MISSING_QID, IMPOSSIBLE_QID], [UK, PL, CS]
    ),
    "wikidata-labels-q1666254-uk": lambda g: g.wikidata.labels(["Q1666254", "Q333"], "uk"),
    "wikidata-claims-q333": lambda g: g.wikidata.related_entities("Q333", ["P279", "P361"]),
    "mediawiki-page-info-uk-redirect-and-missing": lambda g: g.mediawiki.page_info(
        UK, ["астрономія", "Astronomy", "Nonexistent page xyz 123"]
    ),
    "mediawiki-redirects-to-uk-astronomy": lambda g: g.mediawiki.redirects_to(UK, "Астрономія"),
    "mediawiki-search-uk-fasting": lambda g: g.mediawiki.search(
        UK, "інтервальне голодування", limit=5
    ),
}


class UrlRecorder:
    """A ``Cache`` that never hits and remembers every URL the client stored, in order."""

    def __init__(self) -> None:
        self.urls: list[str] = []

    def get(self, key: str) -> bytes | None:
        """Always miss so every call reaches the network."""
        del key
        return None

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None) -> None:
        """Record the URL; the body is re-fetched raw later."""
        del value, ttl_seconds
        self.urls.append(key)


def build_gateways(http: HttpJsonClient, clock: Clock) -> Gateways:
    """Wire the three adapters over one client, the same way the composition root will."""
    ttl = http.settings.resolution_ttl_s
    return Gateways(
        pageviews=WikimediaRestPageviews(http, clock),
        wikidata=WikidataApi(http, ttl),
        mediawiki=MediaWikiApi(http, ttl),
    )


def record_case(name: str, case: Case, settings: Settings) -> dict[str, Any]:
    """Run ``case`` live, then fetch every URL it used raw, and return the fixture document."""
    recorder = UrlRecorder()
    with HttpJsonClient(settings, recorder) as http:
        case(build_gateways(http, SystemClock()))
    headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
    exchanges: list[dict[str, Any]] = []
    with httpx.Client(timeout=settings.http_timeout_s, headers=headers) as raw:
        for url in recorder.urls:
            response = raw.get(url)
            exchanges.append({"url": url, "status": response.status_code, "body": response.json()})
    return {
        "case": name,
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "exchanges": exchanges,
    }


def write_fixture(document: dict[str, Any]) -> Path:
    """Write the fixture and delete older recordings of the same case."""
    FIXTURES_DIR.mkdir(exist_ok=True)
    case = document["case"]
    for stale in FIXTURES_DIR.glob(f"{case}-*.json"):
        stale.unlink()
    today = datetime.now(UTC).date().isoformat()
    path = FIXTURES_DIR / f"{case}-{today}.json"
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return path


def main(argv: list[str]) -> int:
    """Record the selected cases (all by default); refuse to run under CI."""
    if os.environ.get("CI"):
        print("record_fixtures.py talks to the live APIs and must not run in CI", file=sys.stderr)
        return 2
    patterns = argv or ["*"]
    selected = {
        name: case
        for name, case in CASES.items()
        if any(fnmatch.fnmatch(name, pattern) for pattern in patterns)
    }
    if not selected:
        print(f"No case matches {patterns}; known: {sorted(CASES)}", file=sys.stderr)
        return 2
    settings = Settings()
    for name, case in selected.items():
        path = write_fixture(record_case(name, case, settings))
        print(f"recorded {path.relative_to(FIXTURES_DIR.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
