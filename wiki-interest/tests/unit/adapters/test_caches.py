"""Both cache implementations must honour the same contract: miss, hit, TTL, expiry, overwrite."""

import sqlite3
import threading
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from wiki_interest.adapters.memory_cache import InMemoryCache
from wiki_interest.adapters.sqlite_cache import SqliteCache
from wiki_interest.ports.cache import Cache

from .conftest import FakeSeconds

CacheFactory = Callable[[], Cache]


@pytest.fixture(params=["memory", "sqlite"])
def cache_factory(
    request: pytest.FixtureRequest, tmp_path: Path, seconds: FakeSeconds
) -> Iterator[CacheFactory]:
    opened: list[SqliteCache] = []

    def make() -> Cache:
        if request.param == "memory":
            return InMemoryCache(clock=seconds)
        cache = SqliteCache(tmp_path / "cache.sqlite", clock=seconds)
        opened.append(cache)
        return cache

    yield make
    for cache in opened:
        cache.close()


class TestContract:
    def test_get_missing_key_returns_none(self, cache_factory: CacheFactory) -> None:
        assert cache_factory().get("nope") is None

    def test_set_then_get_returns_value(self, cache_factory: CacheFactory) -> None:
        cache = cache_factory()
        cache.set("k", b"value", ttl_seconds=60)
        assert cache.get("k") == b"value"

    def test_none_ttl_never_expires(
        self, cache_factory: CacheFactory, seconds: FakeSeconds
    ) -> None:
        cache = cache_factory()
        cache.set("k", b"forever", ttl_seconds=None)
        seconds.advance(10**9)
        assert cache.get("k") == b"forever"

    def test_entry_is_absent_once_ttl_elapsed(
        self, cache_factory: CacheFactory, seconds: FakeSeconds
    ) -> None:
        cache = cache_factory()
        cache.set("k", b"short", ttl_seconds=10)
        seconds.advance(9)
        assert cache.get("k") == b"short"
        seconds.advance(1)
        assert cache.get("k") is None, "expiry is inclusive at exactly ttl seconds"

    def test_set_overwrites_value_and_ttl(
        self, cache_factory: CacheFactory, seconds: FakeSeconds
    ) -> None:
        cache = cache_factory()
        cache.set("k", b"old", ttl_seconds=1)
        cache.set("k", b"new", ttl_seconds=100)
        seconds.advance(50)
        assert cache.get("k") == b"new"

    def test_binary_values_survive_round_trip(self, cache_factory: CacheFactory) -> None:
        cache = cache_factory()
        payload = bytes(range(256))
        cache.set("bin", payload, ttl_seconds=None)
        assert cache.get("bin") == payload

    def test_concurrent_access_from_threads_is_consistent(
        self, cache_factory: CacheFactory
    ) -> None:
        cache = cache_factory()
        errors: list[BaseException] = []

        def worker(index: int) -> None:
            try:
                for i in range(50):
                    key = f"k{index}-{i}"
                    cache.set(key, key.encode(), ttl_seconds=None)
                    assert cache.get(key) == key.encode()
            except BaseException as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors


class TestSqliteSpecifics:
    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "cache.sqlite"
        with SqliteCache(path) as cache:
            cache.set("k", b"v", ttl_seconds=None)
        assert path.is_file()

    def test_values_persist_across_reopen(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.sqlite"
        with SqliteCache(path) as first:
            first.set("k", b"persisted", ttl_seconds=None)
        with SqliteCache(path) as second:
            assert second.get("k") == b"persisted"

    def test_uses_wal_journal_mode(self, tmp_path: Path) -> None:
        path = tmp_path / "cache.sqlite"
        with SqliteCache(path):
            connection = sqlite3.connect(path)
            try:
                assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
            finally:
                connection.close()

    def test_expired_row_is_deleted_lazily(self, tmp_path: Path, seconds: FakeSeconds) -> None:
        path = tmp_path / "cache.sqlite"
        with SqliteCache(path, clock=seconds) as cache:
            cache.set("k", b"v", ttl_seconds=1)
            seconds.advance(2)
            assert cache.get("k") is None
            connection = sqlite3.connect(path)
            try:
                assert connection.execute("SELECT COUNT(*) FROM entries").fetchone()[0] == 0
            finally:
                connection.close()

    def test_closed_cache_refuses_further_use(self, tmp_path: Path) -> None:
        cache = SqliteCache(tmp_path / "cache.sqlite")
        cache.close()
        with pytest.raises(sqlite3.ProgrammingError):
            cache.get("k")


def test_memory_cache_reports_size() -> None:
    cache = InMemoryCache()
    cache.set("a", b"1", ttl_seconds=None)
    cache.set("b", b"2", ttl_seconds=None)
    assert len(cache) == 2
