"""Replay fixture: mounts a case's recorded exchanges on respx and runs the case through them."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.config import Settings

from .record_fixtures import CASES, FIXTURES_DIR, build_gateways

type Replay = Callable[[str], Any]


class FixedClock:
    """Pins "today" so the TTL branch does not depend on when the tests run."""

    def today(self) -> date:
        return date(2026, 9, 22)


def load_fixture(case: str) -> dict[str, Any]:
    """Load the newest recording of ``case``; fail clearly when none was recorded."""
    candidates = sorted(FIXTURES_DIR.glob(f"{case}-*.json"))
    if not candidates:
        pytest.fail(f"No fixture for {case!r}; run tests/contract/record_fixtures.py {case}")
    document: dict[str, Any] = json.loads(Path(candidates[-1]).read_text(encoding="utf-8"))
    return document


@pytest.fixture
def replay(respx_mock: respx.MockRouter) -> Replay:
    """Run a recorded case against respx routes built from its exchanges and return the result."""

    def run(case: str) -> Any:
        document = load_fixture(case)
        for exchange in document["exchanges"]:
            respx_mock.get(url__eq=exchange["url"]).mock(
                return_value=httpx.Response(exchange["status"], json=exchange["body"])
            )
        settings = Settings(max_retries=0)
        with HttpJsonClient(settings, InMemoryCache(), httpx.Client()) as http:
            result = CASES[case](build_gateways(http, FixedClock()))
        assert respx_mock.calls.call_count == len(document["exchanges"]), (
            "the adapter issued a different number of requests than were recorded"
        )
        return result

    return run
