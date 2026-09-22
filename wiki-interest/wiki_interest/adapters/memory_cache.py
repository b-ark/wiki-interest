"""In-memory cache with the same expiry semantics as the SQLite one, for tests and dry runs.

Keeping the two implementations behaviourally identical (miss on absent, miss on expired,
``None`` TTL never expires) is what lets the application be tested without touching disk and
still trust the real cache; the shared contract test in ``tests/unit/adapters`` exercises both.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

__all__ = ["InMemoryCache"]


class InMemoryCache:
    """Dictionary-backed byte cache with per-entry expiry.

    Args:
        clock: Seconds source used for expiry; tests pass a controllable one so TTL behaviour
            is deterministic. Wall-clock seconds, not the date-only ``Clock`` port.
    """

    def __init__(self, *, clock: Callable[[], float] = time.time) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[bytes, float | None]] = {}

    def get(self, key: str) -> bytes | None:
        """Return the cached bytes, or ``None`` when absent or expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if expires_at is not None and expires_at <= self._clock():
                del self._entries[key]
                return None
            return value

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None) -> None:
        """Store ``value`` under ``key``; ``ttl_seconds=None`` never expires."""
        expires_at = None if ttl_seconds is None else self._clock() + ttl_seconds
        with self._lock:
            self._entries[key] = (value, expires_at)

    def __len__(self) -> int:
        return len(self._entries)
