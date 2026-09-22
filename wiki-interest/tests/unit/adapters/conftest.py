"""Shared fixtures: deterministic settings, a fake seconds clock and a client that never sleeps."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest

from wiki_interest.adapters.http import HttpJsonClient
from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.config import Settings


class FakeSeconds:
    """Controllable wall-clock seconds for cache expiry tests."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def seconds() -> FakeSeconds:
    return FakeSeconds()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(max_retries=2, cache_path=tmp_path / "cache.sqlite", http_timeout_s=5.0)


@pytest.fixture
def cache(seconds: FakeSeconds) -> InMemoryCache:
    return InMemoryCache(clock=seconds)


@pytest.fixture
def sleeps() -> list[float]:
    """Durations the client would have slept between retries."""
    return []


@pytest.fixture
def http(settings: Settings, cache: InMemoryCache, sleeps: list[float]) -> Iterator[HttpJsonClient]:
    with HttpJsonClient(settings, cache, httpx.Client(), sleep=sleeps.append) as client:
        yield client
