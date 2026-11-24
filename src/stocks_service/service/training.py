"""The use case: train the model on the older years and test it honestly on the last year."""
from dataclasses import dataclass
from datetime import date, datetime

from stocks_service.domain.features import (
    FEATURE_NAMES,
    TrainingRow,
    split_by_time,
    training_rows,
)
from stocks_service.domain.forecast import Metrics, evaluate
from stocks_service.domain.prices import PriceHistory
from stocks_service.service.interfaces import ForecastModel, ModelStore, ModelTrainer, PriceSource


@dataclass(frozen=True, slots=True)
class TrainingReport:
    train: list[TrainingRow]
    test: list[TrainingRow]
    metrics: Metrics  # measured on the test rows only


class TrainingService:
    def __init__(self, prices: PriceSource, trainer: ModelTrainer, store: ModelStore) -> None:
        self._prices = prices
        self._trainer = trainer
        self._store = store

    def train(self, ticker: str, start: date, end: date, test_start: date,
              created_at: datetime) -> tuple[ForecastModel, TrainingReport]:
        """Download, train, test, and save the model with its facts file."""
        history = self._prices.history(ticker, start=start, end=end)
        model, report = self.train_from(history, test_start)
        self._store.save(model, facts_for(model, report, created_at))
        return model, report

    def train_from(self, history: PriceHistory,
                   test_start: date) -> tuple[ForecastModel, TrainingReport]:
        """Train and test on prices we already hold. Nothing is downloaded or saved."""
        train, test = split_by_time(training_rows(history), test_start)
        model = self._trainer.fit(train)  # the model never sees the test rows
        predicted = [model.predict_move(row.features) for row in test]
        return model, TrainingReport(train=train, test=test, metrics=evaluate(test, predicted))


def facts_for(model: ForecastModel, report: TrainingReport,
              created_at: datetime) -> dict[str, object]:
    """The facts file a service needs next to the model (same content as the notebook's)."""
    m = report.metrics
    return {
        "model_version": model.model_version,
        "ticker": model.ticker,
        "target": "next trading day's closing price in SAR, "
                  "predicted as a move from today's close",
        "features": list(FEATURE_NAMES),
        **model.describe(),
        "train": _span(report.train),
        "test": _span(report.test),
        "metrics_test": {
            "model": {"mae_sar": round(m.model_mae_sar, 4), "rmse_sar": round(m.model_rmse_sar, 4),
                      "mape_pct": round(m.model_mape_pct, 4),
                      "direction_hit_pct": round(m.direction_hit_pct, 2)},
            "naive_baseline": {"mae_sar": round(m.naive_mae_sar, 4),
                               "rmse_sar": round(m.naive_rmse_sar, 4),
                               "mape_pct": round(m.naive_mape_pct, 4)},
            "mae_improvement_vs_naive_pct": round(m.mae_improvement_vs_naive_pct, 2),
        },
        "created_at": created_at.isoformat(timespec="seconds"),
    }


def _span(rows: list[TrainingRow]) -> dict[str, object]:
    return {"start": rows[0].day.isoformat(), "end": rows[-1].day.isoformat(), "rows": len(rows)}
