"""The model's eight inputs, written ONCE. Training and forecasting both call this file.

The notebook wrote this logic twice (step 5 for training, step 10 for one forecast). Two copies
can drift apart without anyone noticing, so here there is one.

Only the past counts: the inputs for a day read that day's close and earlier closes, never a
later one. Standard library only.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import fmean, stdev

from stocks_service.domain.errors import NotEnoughHistory
from stocks_service.domain.prices import PriceHistory

Features = dict[str, float]

FEATURE_NAMES: tuple[str, ...] = (
    "ret_1d", "ret_lag1", "ret_lag2", "ret_5d", "gap_ma5", "gap_ma20", "vol_10d", "day_of_week",
)
FEATURE_WORDS: dict[str, str] = {
    "ret_1d": "today's move",
    "ret_lag1": "yesterday's move",
    "ret_lag2": "move two days ago",
    "ret_5d": "move over the last week",
    "gap_ma5": "distance from 5-day average",
    "gap_ma20": "distance from 20-day average",
    "vol_10d": "jumpiness, last 10 days",
    "day_of_week": "day of the week",
}
MIN_DAYS = 20  # the 20-day average needs 20 closing prices


@dataclass(frozen=True, slots=True)
class TrainingRow:
    """One day the model can learn from: its inputs, and what really happened next."""

    day: date
    close: float
    next_close: float
    features: Features

    @property
    def target(self) -> float:
        """Tomorrow's move, as a fraction of today's close (0.01 = +1%)."""
        return self.next_close / self.close - 1


def _move(closes: Sequence[float], i: int) -> float:
    return closes[i] / closes[i - 1] - 1


def features_at(days: Sequence[date], closes: Sequence[float], i: int) -> Features:
    """The eight inputs for day number `i`, using closes[0..i] only."""
    if i < MIN_DAYS - 1:
        raise NotEnoughHistory(f"need {MIN_DAYS} trading days, have {i + 1}")
    return {
        "ret_1d": _move(closes, i),
        "ret_lag1": _move(closes, i - 1),
        "ret_lag2": _move(closes, i - 2),
        "ret_5d": closes[i] / closes[i - 5] - 1,
        "gap_ma5": closes[i] / fmean(closes[i - 4:i + 1]) - 1,
        "gap_ma20": closes[i] / fmean(closes[i - 19:i + 1]) - 1,
        "vol_10d": stdev(_move(closes, j) for j in range(i - 9, i + 1)),
        "day_of_week": float((days[i].weekday() + 1) % 7),  # 0 = Sunday ... 4 = Thursday
    }


def latest_features(history: PriceHistory) -> Features:
    """The inputs for the most recent day in the history."""
    return features_at(history.days, history.closes, len(history) - 1)


def training_rows(history: PriceHistory) -> list[TrainingRow]:
    """Every day that has full inputs and a known next day."""
    days, closes = history.days, history.closes
    return [
        TrainingRow(day=days[i], close=closes[i], next_close=closes[i + 1],
                    features=features_at(days, closes, i))
        for i in range(MIN_DAYS - 1, len(closes) - 1)
    ]


def split_by_time(rows: Sequence[TrainingRow],
                  test_start: date) -> tuple[list[TrainingRow], list[TrainingRow]]:
    """Older days to learn from, later days to test on. Never shuffled."""
    train = [row for row in rows if row.day < test_start]
    test = [row for row in rows if row.day >= test_start]
    return train, test
