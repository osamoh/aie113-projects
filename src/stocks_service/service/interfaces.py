"""Ports: what the service needs from the outside world, stated as shapes (protocols).

The service depends on these shapes, never on Yahoo, scikit-learn or files. Swap the price
source or the model and only an adapter changes; nothing in service/ or domain/ does.
"""
from collections.abc import Sequence
from datetime import date
from typing import Protocol

from stocks_service.domain.features import Features, TrainingRow
from stocks_service.domain.forecast import Explanation
from stocks_service.domain.prices import PriceHistory


class PriceSource(Protocol):
    def history(self, ticker: str, start: date, end: date) -> PriceHistory:
        """Closing prices from `start` up to, not including, `end`. Days with no trading
        are left out. Raises PriceSourceUnavailable when nothing comes back."""
        ...


class ForecastModel(Protocol):
    model_version: str
    ticker: str  # the one share this model was trained on

    def predict_move(self, features: Features) -> float:
        """Tomorrow's move as a fraction of today's close (0.01 = +1%)."""
        ...

    def explain(self, features: Features) -> Explanation:
        """The same answer, split into a starting point and one push per input."""
        ...

    def describe(self) -> dict[str, object]:
        """Facts about this kind of model, for the facts file."""
        ...


class ModelTrainer(Protocol):
    def fit(self, rows: Sequence[TrainingRow]) -> ForecastModel:
        """Learn from the training rows and return a model."""
        ...


class ModelStore(Protocol):
    def save(self, model: ForecastModel, facts: dict[str, object]) -> None: ...

    def load(self) -> ForecastModel: ...

    def facts(self) -> dict[str, object]: ...
