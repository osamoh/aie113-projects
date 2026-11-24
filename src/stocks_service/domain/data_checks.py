"""Is a price history what we expect? A list of problems, in plain words.

The model can only be as right as its inputs. These checks do not fix anything: they name
what looks wrong, so a test (or a person) can decide. Standard library only.
"""
from datetime import date

from stocks_service.domain.prices import PriceHistory

MAX_DAILY_MOVE = 0.15  # the largest one-day move in five years of this share is under 6%
MAX_AGE_DAYS = 14      # the longest holiday gap in five years is 11 calendar days
TRADING_WEEKDAYS = {6, 0, 1, 2, 3}  # Sunday to Thursday (Python counts Monday as 0)


def price_problems(history: PriceHistory, as_of: date) -> list[str]:
    """Everything that looks wrong in `history`, as it should be known on `as_of`."""
    if len(history) == 0:
        return ["no prices at all"]
    problems = []
    for point in history.points:
        if point.day > as_of:
            problems.append(f"{point.day} is after {as_of}: a price from the future")
        if point.day.weekday() not in TRADING_WEEKDAYS:
            problems.append(f"{point.day} is a {point.day:%A}: the market is closed")
    for earlier, later in zip(history.points, history.points[1:]):
        move = later.close / earlier.close - 1
        if abs(move) > MAX_DAILY_MOVE:
            problems.append(f"{later.day}: the price moved {move:+.0%} in one day")
    age = (as_of - history.points[-1].day).days
    if age > MAX_AGE_DAYS:
        problems.append(f"the latest price is {age} days old ({history.points[-1].day})")
    return problems
