"""A rule about the market's clock: only FINISHED trading days count.

Before the market has closed, the price source shows the price so far today, not the closing
price. A forecast built on that part-day number would be quietly wrong. So "today" only counts
once its closing price is final. Standard library only.
"""
from datetime import date, datetime, time, timedelta, timezone

RIYADH = timezone(timedelta(hours=3))  # Saudi Arabia has no daylight saving time

# The Saudi Exchange sets the closing price in an auction from 3:00 to 3:10 pm, and trading at
# that price ends at 3:20 pm. We wait until 4:00 pm to give the price source time to catch up.
PRICES_FINAL_AT = time(16, 0)


def latest_complete_day(now: datetime) -> date:
    """The latest calendar day whose closing price can be final at the moment `now`."""
    if now.tzinfo is None:
        raise ValueError("now must say which time zone it is in")
    local = now.astimezone(RIYADH)
    if local.time() >= PRICES_FINAL_AT:
        return local.date()
    return local.date() - timedelta(days=1)
