"""On-disk cache backed by SQLite, implementing the :class:`~wiki_interest.ports.cache.Cache` port.

A single table keyed by URL is enough: the adapters never enumerate the cache, they only look
up exact keys. SQLite is chosen over a directory of files because one file is easy to ship,
delete and inspect, and WAL mode lets the reading threads of the fetch fan-out proceed while
one thread writes. A single connection guarded by a lock is simpler than a pool and fast
enough: the cache is never the bottleneck, the network is.
"""

from __future__ import annotations

import sqlite3
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Self

__all__ = ["SqliteCache"]

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    key        TEXT PRIMARY KEY,
    value      BLOB NOT NULL,
    expires_at REAL
)
"""


class SqliteCache:
    """Persistent byte cache with per-entry expiry.

    Expired rows are treated as absent and deleted lazily on the next read of the same key;
    there is no background sweep because the cache is small (one row per distinct request).

    Args:
        path: The database file; parent directories are created.
        clock: Seconds source used for expiry (injectable for tests). This is wall-clock
            seconds, not the date-only :class:`~wiki_interest.ports.clock.Clock` port.
    """

    def __init__(self, path: Path, *, clock: Callable[[], float] = time.time) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = threading.Lock()
        # check_same_thread=False: the connection is shared across the fetch threads, and the
        # lock serialises access, which is what SQLite requires.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._lock, self._conn:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(_SCHEMA)

    def get(self, key: str) -> bytes | None:
        """Return the cached bytes, or ``None`` when absent or expired; expired rows are deleted."""
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT value, expires_at FROM entries WHERE key = ?", (key,)
            ).fetchone()
            if row is None:
                return None
            value, expires_at = row
            if expires_at is not None and expires_at <= self._clock():
                self._conn.execute("DELETE FROM entries WHERE key = ?", (key,))
                return None
            return bytes(value)

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None) -> None:
        """Store ``value`` under ``key``; ``ttl_seconds=None`` never expires."""
        expires_at = None if ttl_seconds is None else self._clock() + ttl_seconds
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO entries (key, value, expires_at) VALUES (?, ?, ?)",
                (key, value, expires_at),
            )

    def close(self) -> None:
        """Close the connection; further calls fail loudly."""
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
