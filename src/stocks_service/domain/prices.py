"""The words of the problem: a closing price on a trading day, and a history of them.

Standard library only. Nothing here knows about Yahoo, files, pandas or the model.
"""
import math
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class PricePoint:
    day: date
    close: float  # closing price in SAR

    def __post_init__(self) -> None:
        if not math.isfinite(self.close) or self.close <= 0:
            raise ValueError(f"close must be a positive price, got {self.close!r} on {self.day}")


@dataclass(frozen=True, slots=True)
class PriceHistory:
    """Closing prices of one share, oldest first, one per trading day."""

    ticker: str
    points: tuple[PricePoint, ...]

    def __post_init__(self) -> None:
        for earlier, later in zip(self.points, self.points[1:]):
            if later.day <= earlier.day:
                raise ValueError(f"days must be in order with no repeats: {later.day}")

    def __len__(self) -> int:
        return len(self.points)

    @property
    def days(self) -> tuple[date, ...]:
        return tuple(point.day for point in self.points)

    @property
    def closes(self) -> tuple[float, ...]:
        return tuple(point.close for point in self.points)

    def up_to(self, day: date) -> "PriceHistory":
        """The same history as it was known on the evening of `day`: later days are dropped."""
        return PriceHistory(self.ticker, tuple(p for p in self.points if p.day <= day))
