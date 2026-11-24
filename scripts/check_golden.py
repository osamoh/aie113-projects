"""Does the reorganised code still give the notebook's answers?

    python scripts/check_golden.py

Downloads the same prices once, trains with the NEW code, then compares with
tests/golden/notebook_answers.json: the test-period numbers, and for each of the five saved
days the inputs, the forecast, the naive guess and every reason. Exit code 1 on any difference.
"""
import json
import sys
from datetime import date
from pathlib import Path

from stocks_service.adapters.ridge_model import RidgeTrainer
from stocks_service.adapters.yahoo_prices import YahooPriceSource
from stocks_service.config import Settings
from stocks_service.service.forecasting import ForecastService
from stocks_service.service.training import TrainingService

GOLDEN = Path(__file__).resolve().parents[1] / "tests" / "golden" / "notebook_answers.json"
TOLERANCE = 1e-9  # the same number up to rounding in the last digits


def differences(label: str, expected: dict, actual: dict) -> list[str]:
    return [f"{label} {key}: notebook {expected[key]!r}, new code {actual[key]!r}"
            for key in expected if abs(expected[key] - actual[key]) > TOLERANCE]


def main() -> None:
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    settings = Settings()
    history = YahooPriceSource().history(settings.ticker, settings.start_date, settings.end_date)

    trainer = RidgeTrainer(settings.alphas, settings.model_version, settings.ticker)
    model, report = TrainingService(YahooPriceSource(), trainer, store=None).train_from(
        history, settings.test_start)
    m = report.metrics

    problems = differences("rows", golden["rows"] | {"ridge_alpha": golden["ridge_alpha"]}, {
        "downloaded": golden["rows"]["downloaded"],  # the new code keeps only traded days
        "kept": len(history), "train": len(report.train), "test": len(report.test),
        "ridge_alpha": model.describe()["ridge_alpha"]})
    problems += differences("test period", golden["metrics_test"], {
        "model_mae_sar": m.model_mae_sar, "naive_mae_sar": m.naive_mae_sar,
        "model_rmse_sar": m.model_rmse_sar, "naive_rmse_sar": m.naive_rmse_sar,
        "model_mape_pct": m.model_mape_pct, "naive_mape_pct": m.naive_mape_pct,
        "direction_hit_pct": m.direction_hit_pct,
        "mae_improvement_vs_naive_pct": m.mae_improvement_vs_naive_pct})
    print(f"Test period: model MAE {m.model_mae_sar:.4f} SAR, naive MAE {m.naive_mae_sar:.4f} SAR "
          f"(notebook: {golden['metrics_test']['model_mae_sar']:.4f} and "
          f"{golden['metrics_test']['naive_mae_sar']:.4f})")

    service = ForecastService(YahooPriceSource(), model)
    matching_days = 0
    for day in golden["days"]:
        result = service.forecast_from(history.up_to(date.fromisoformat(day["as_of"])))
        inputs = {reason.name: reason.value for reason in result.reasons}
        pushes = {reason.name: reason.push_halalas for reason in result.reasons}
        found = differences(day["as_of"], {k: v for k, v in day.items() if isinstance(v, float)}, {
            "last_close": result.last_close, "predicted_move": result.predicted_move,
            "forecast_close": result.forecast_close, "naive_close": result.naive_close,
            "start_halalas": result.start_halalas})
        found += differences(f"{day['as_of']} input", day["inputs"], inputs)
        found += differences(f"{day['as_of']} push", day["push_halalas"], pushes)
        if result.as_of.isoformat() != day["as_of"]:
            found.append(f"{day['as_of']}: new code used prices up to {result.as_of}")
        matching_days += not found
        problems += found
        print(f"  {day['as_of']}: notebook {day['forecast_close']:.6f} SAR, "
              f"new code {result.forecast_close:.6f} SAR  {'DIFFERENT' if found else 'same'}")

    print(f"{matching_days}/{len(golden['days'])} days match the notebook's answers")
    if problems:
        print(f"NOT THE SAME: {len(problems)} numbers differ. First few:")
        for line in problems[:8]:
            print("  " + line)
        sys.exit(1)
    print("Test-period numbers match the notebook's.")


if __name__ == "__main__":
    main()
