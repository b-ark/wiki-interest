"""Port: the current date, injected so that defaults and tests are deterministic."""

from __future__ import annotations

from datetime import date
from typing import Protocol

__all__ = ["Clock"]


class Clock(Protocol):
    """Supplies today's date. The default period ("last 24 full months") depends on it."""

    def today(self) -> date:
        """Return the current date in UTC."""
        ...
