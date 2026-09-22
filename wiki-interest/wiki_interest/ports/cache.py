"""Port: byte cache used by HTTP adapters to make repeat and follow-up requests cheap."""

from __future__ import annotations

from typing import Protocol

__all__ = ["Cache"]


class Cache(Protocol):
    """Key-value store for raw upstream responses.

    Keys are opaque strings (adapters use the full request URL). Values are bytes so the cache
    never needs to know about response formats. Expired entries behave as absent.
    """

    def get(self, key: str) -> bytes | None:
        """Return the cached value, or ``None`` when absent or expired."""
        ...

    def set(self, key: str, value: bytes, *, ttl_seconds: int | None) -> None:
        """Store ``value``; ``ttl_seconds=None`` means it never expires."""
        ...
