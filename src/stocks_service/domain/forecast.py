"""What a forecast is, and the rules around it. Standard library only.

Two rules of this project live here so no outer layer can forget them: every forecast carries
the naive guess next to it, and every forecast carries the "not investment advice" note.
"""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from math import sqrt

from stocks_service.domain.features import FEATURE_WORDS, Features, TrainingRow

DISCLAIMER = "A teaching example, not investment advice."
HALALAS_PER_SAR = 100
DAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")


@dataclass(frozen=True, slots=True)
class Explanation:
    """Why the model said what it said, in the model's own unit (a move, 0.01 = +1%).

    The predicted move is exactly `start_move` plus the sum of `pushes`.
    """

    start_move: float
    pushes: dict[str, float]


@dataclass(frozen=True, slots=True)
class Reason:
    name: str           # the input's name, for example "ret_lag2"
    label: str          # the same in plain words, for example "move two days ago"
    value: float        # the input's value on that day
    push_halalas: float  # how far this input pushed the forecast up (+) or down (-)

    @property
    def value_text(self) -> str:
        """The value as a person reads it: a weekday name, or a move in percent."""
        if self.name == "day_of_week":
            return DAY_NAMES[int(self.value)]
        return f"{self.value * 100:+.2f}%"


@dataclass(frozen=True, slots=True)
class Forecast:
    ticker: str
    as_of: date            # the day of the latest closing price used
    last_close: float      # SAR
    forecast_close: float  # the model's guess for the next trading day, SAR
    naive_close: float     # the simple guess "tomorrow = today", SAR
    predicted_move: float  # the model's guess as a move from today's close
    start_halalas: float   # the model's starting point before any input pushes it
    reasons: tuple[Reason, ...]  # one per input, biggest push first
    model_version: str
    disclaimer: str = DISCLAIMER

    @property
    def change_halalas(self) -> float:
        return (self.forecast_close - self.last_close) * HALALAS_PER_SAR


def make_forecast(ticker: str, as_of: date, last_close: float, features: Features,
                  predicted_move: float, explanation: Explanation,
                  model_version: str) -> Forecast:
    """Turn the model's answer (a move) into prices and reasons a person can read."""
    to_halalas = last_close * HALALAS_PER_SAR
    reasons = sorted(
        (Reason(name=name, label=FEATURE_WORDS[name], value=features[name],
                push_halalas=push * to_halalas)
         for name, push in explanation.pushes.items()),
        key=lambda reason: abs(reason.push_halalas), reverse=True,
    )
    return Forecast(
        ticker=ticker, as_of=as_of, last_close=last_close,
        forecast_close=last_close * (1 + predicted_move),
        naive_close=last_close,  # the naive guess: tomorrow's close = today's close
        predicted_move=predicted_move,
        start_halalas=explanation.start_move * to_halalas,
        reasons=tuple(reasons), model_version=model_version,
    )


@dataclass(frozen=True, slots=True)
class Metrics:
    """How far the forecasts landed from the real closes, for the model and the naive guess."""

    days: int
    model_mae_sar: float
    naive_mae_sar: float
    model_rmse_sar: float
    naive_rmse_sar: float
    model_mape_pct: float
    naive_mape_pct: float
    direction_hit_pct: float   # how often the model got up/down right, on days that moved
    days_that_moved: int

    @property
    def mae_improvement_vs_naive_pct(self) -> float:
        """Positive = the model beats "tomorrow = today". Negative = it is worse."""
        return (1 - self.model_mae_sar / self.naive_mae_sar) * 100


def _sign(x: float) -> int:
    return (x > 0) - (x < 0)


def evaluate(rows: Sequence[TrainingRow], predicted_moves: Sequence[float]) -> Metrics:
    """Compare the model with the naive guess on days it never saw while learning."""
    n = len(rows)
    if n == 0:
        raise ValueError("no test days to evaluate on")
    model_errors = [row.next_close - row.close * (1 + move)
                    for row, move in zip(rows, predicted_moves, strict=True)]
    naive_errors = [row.next_close - row.close for row in rows]
    moved = [(row, move) for row, move in zip(rows, predicted_moves) if row.target != 0]
    hits = sum(1 for row, move in moved if _sign(move) == _sign(row.target))
    return Metrics(
        days=n,
        model_mae_sar=sum(abs(e) for e in model_errors) / n,
        naive_mae_sar=sum(abs(e) for e in naive_errors) / n,
        model_rmse_sar=sqrt(sum(e * e for e in model_errors) / n),
        naive_rmse_sar=sqrt(sum(e * e for e in naive_errors) / n),
        model_mape_pct=sum(abs(e) / row.next_close for e, row in zip(model_errors, rows)) / n * 100,
        naive_mape_pct=sum(abs(e) / row.next_close for e, row in zip(naive_errors, rows)) / n * 100,
        direction_hit_pct=hits / len(moved) * 100 if moved else 0.0,
        days_that_moved=len(moved),
    )
