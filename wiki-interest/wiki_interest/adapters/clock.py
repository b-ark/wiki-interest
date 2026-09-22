"""System clock adapter: today's date in UTC.

The Pageviews API counts days in UTC, so "today" must be UTC as well or a run started late in
the evening in Kyiv would ask for a day the API has not published yet.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

__all__ = ["SystemClock"]


class SystemClock:
    """Real clock implementing the :class:`~wiki_interest.ports.clock.Clock` port."""

    def today(self) -> date:
        """Return the current UTC date."""
        return datetime.now(UTC).date()
