"""Entry point (commands). The composition root: the one place concrete classes meet.

    python -m stocks_service.cli train
    python -m stocks_service.cli forecast
    python -m stocks_service.cli forecast --as-of 2026-10-29
"""
import argparse
import calendar
import sys
from datetime import UTC, date, datetime

from stocks_service.adapters.ridge_model import JoblibModelStore, RidgeTrainer
from stocks_service.adapters.yahoo_prices import YahooPriceSource
from stocks_service.config import Settings
from stocks_service.domain.errors import NotEnoughHistory, PriceSourceUnavailable, UnknownTicker
from stocks_service.domain.forecast import Forecast
from stocks_service.domain.market import latest_complete_day
from stocks_service.service.forecasting import ForecastService
from stocks_service.service.training import TrainingService


def train(settings: Settings) -> None:
    store = JoblibModelStore(settings.model_path, settings.meta_path)
    trainer = RidgeTrainer(settings.alphas, settings.model_version, settings.ticker)
    service = TrainingService(YahooPriceSource(), trainer, store)
    model, report = service.train(settings.ticker, settings.start_date, settings.end_date,
                                  settings.test_start, created_at=datetime.now(UTC))
    m = report.metrics
    print(f"Train: {len(report.train)} days, {report.train[0].day} to {report.train[-1].day}")
    print(f"Test:  {len(report.test)} days, {report.test[0].day} to {report.test[-1].day}")
    print(f"Chosen alpha: {model.describe()['ridge_alpha']:g}")
    print(f"Average error (MAE) on the test days: model {m.model_mae_sar:.4f} SAR, "
          f"naive 'tomorrow = today' {m.naive_mae_sar:.4f} SAR")
    print(f"Model vs naive: {m.mae_improvement_vs_naive_pct:+.2f}% "
          "(positive = the model is better)")
    print(f"Direction right on {m.direction_hit_pct:.1f}% of the {m.days_that_moved} test days "
          "when the price moved (a coin flip gets about 50%)")
    print(f"Saved {settings.model_path} and {settings.meta_path}")


def forecast(settings: Settings, ticker: str, as_of: date) -> None:
    store = JoblibModelStore(settings.model_path, settings.meta_path)
    service = ForecastService(YahooPriceSource(), store.load(), settings.lookback_days)
    result = service.forecast(ticker, as_of)
    gap = store.facts()["metrics_test"]["mae_improvement_vs_naive_pct"]
    print(_render(result, gap))


def _render(f: Forecast, improvement_vs_naive_pct: float) -> str:
    day_name = calendar.day_name[f.as_of.weekday()]
    lines = [
        f"{f.ticker}: latest closing price used is from {f.as_of} ({day_name})",
        f"  Last close:      {f.last_close:.2f} SAR",
        (f"  Model forecast:  {f.forecast_close:.3f} SAR for the next trading day "
         f"({f.change_halalas:+.2f} halalas)"),
        f"  Naive forecast:  {f.naive_close:.2f} SAR (tomorrow = today)",
        f"Why: starting point {f.start_halalas:+.2f} halalas, then each input pushes:",
    ]
    lines += [f"  {r.label:<30} {r.value_text:>9}  {r.push_halalas:+.2f} halalas"
              for r in f.reasons]
    lines += [
        (f"Model {f.model_version}. On its test year its average error was "
         f"{improvement_vs_naive_pct:+.2f}% against the naive guess (negative = worse)."),
        f.disclaimer,
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Next-day closing price forecast. "
                                     "A teaching example, not investment advice.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("train", help="download prices, train, test and save the model")
    one = commands.add_parser("forecast", help="forecast the next trading day")
    one.add_argument("--ticker", default=None, help="default: the configured share")
    one.add_argument("--as-of", type=date.fromisoformat, default=None,
                     help="use prices up to this day (YYYY-MM-DD); "
                          "default: the latest finished trading day")
    args = parser.parse_args()

    settings = Settings.load()
    try:
        if args.command == "train":
            train(settings)
        else:
            as_of = args.as_of or latest_complete_day(datetime.now(UTC))
            forecast(settings, args.ticker or settings.ticker, as_of)
    except (UnknownTicker, NotEnoughHistory, PriceSourceUnavailable) as problem:
        sys.exit(f"Cannot do that: {problem}")
    except FileNotFoundError as missing:
        sys.exit(f"No trained model yet ({missing.filename}). "
                 "Run: python -m stocks_service.cli train")


if __name__ == "__main__":
    main()
