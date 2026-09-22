"""The system clock reports the UTC date."""

from datetime import UTC, datetime, timedelta

from wiki_interest.adapters.clock import SystemClock


def test_today_is_the_utc_date() -> None:
    before = datetime.now(UTC).date()
    today = SystemClock().today()
    after = datetime.now(UTC).date()
    assert before <= today <= after
    assert after - before <= timedelta(days=1)
