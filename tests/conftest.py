"""Shared helpers for every test: made-up prices, a stand-in model, a stand-in price source.

Fast tests must not download anything or depend on today's market. So prices are invented here
(always the same ones: the random generator has a fixed seed), and the model and the price
source can be replaced by stand-ins that return exactly what a test tells them to.
"""
import contextlib
import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stocks_service.adapters.ridge_model import JoblibModelStore
from stocks_service.api.app import create_app
from stocks_service.api.routes import get_forecaster, get_now
from stocks_service.domain.features import FEATURE_NAMES, Features
from stocks_service.domain.forecast import Explanation
from stocks_service.domain.prices import PriceHistory, PricePoint
from stocks_service.service.forecasting import ForecastService

TICKER = "2222.SR"
REPO = Path(__file__).resolve().parents[1]
RIYADH = timezone(timedelta(hours=3))
LAST_DAY = date(2026, 10, 29)                                # a Thursday
AFTER_CLOSE = datetime(2026, 10, 29, 18, 0, tzinfo=RIYADH)   # that day's price is final
TRADING_WEEKDAYS = {6, 0, 1, 2, 3}                           # Sunday to Thursday


def trading_days(count: int, last: date = LAST_DAY) -> list[date]:
    """`count` trading days (Sunday to Thursday) ending on `last`, oldest first."""
    days: list[date] = []
    day = last
    while len(days) < count:
        if day.weekday() in TRADING_WEEKDAYS:
            days.append(day)
        day -= timedelta(days=1)
    return days[::-1]


def make_history(closes: list[float], last: date = LAST_DAY, ticker: str = TICKER) -> PriceHistory:
    """A price history from a plain list of closing prices, ending on `last`."""
    days = trading_days(len(closes), last)
    return PriceHistory(ticker, tuple(PricePoint(d, c) for d, c in zip(days, closes)))


def random_walk(count: int, seed: int = 113, start: float = 27.0,
                typical_move: float = 0.01) -> list[float]:
    """Invented closing prices that wander like a real share. Same seed, same prices."""
    rng = random.Random(seed)
    closes = [start]
    for _ in range(count - 1):
        closes.append(round(closes[-1] * (1 + rng.gauss(0, typical_move)), 2))
    return closes


class FakeModel:
    """Stand-in model: always predicts the same move, with reasons we choose."""

    model_version = "fake-1"
    ticker = TICKER

    def __init__(self, move: float = 0.001, pushes: dict[str, float] | None = None) -> None:
        self.move = move
        # By default three inputs push, so "top reasons" has something to sort.
        self.pushes = pushes or {**dict.fromkeys(FEATURE_NAMES, 0.0),
                                 "ret_1d": 0.0004, "ret_lag2": -0.0007, "gap_ma5": 0.0010}

    def predict_move(self, features: Features) -> float:
        return self.move

    def explain(self, features: Features) -> Explanation:
        return Explanation(start_move=self.move - sum(self.pushes.values()), pushes=self.pushes)

    def describe(self) -> dict[str, object]:
        return {"model_kind": "stand-in for tests"}


class FakePriceSource:
    """Stand-in price source: returns the history it was given, or fails on purpose."""

    def __init__(self, history: PriceHistory | None = None,
                 error: Exception | None = None) -> None:
        self._history = history
        self._error = error
        self.calls: list[tuple[str, date, date]] = []

    def history(self, ticker: str, start: date, end: date) -> PriceHistory:
        self.calls.append((ticker, start, end))
        if self._error is not None:
            raise self._error
        assert self._history is not None
        return self._history


@pytest.fixture
def history() -> PriceHistory:
    """Sixty invented trading days ending on Thursday 29 October 2026."""
    return make_history(random_walk(60))


@pytest.fixture
def client_factory(history):
    """The API with a stand-in model, stand-in prices and a fixed clock put in from outside."""
    stack = contextlib.ExitStack()

    def _make(model=None, source=None, now: datetime = AFTER_CLOSE) -> TestClient:
        app = create_app()
        client = stack.enter_context(TestClient(app, raise_server_exceptions=False))
        service = ForecastService(source or FakePriceSource(history), model or FakeModel())
        app.dependency_overrides[get_forecaster] = lambda: service
        app.dependency_overrides[get_now] = lambda: now
        return client

    yield _make
    stack.close()


@pytest.fixture(scope="session")
def model_store() -> JoblibModelStore:
    return JoblibModelStore(REPO / "models" / "model.joblib", REPO / "models" / "model_meta.json")


@pytest.fixture(scope="session")
def real_model(model_store):
    """The real, committed model. Loaded once for all the tests that need it."""
    return model_store.load()


@pytest.fixture(scope="session")
def golden() -> dict:
    """The notebook's own answers, saved in Stage 1 before any code was moved."""
    return json.loads((REPO / "tests" / "golden" / "notebook_answers.json").read_text("utf-8"))
