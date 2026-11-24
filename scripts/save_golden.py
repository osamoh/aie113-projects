"""Save the notebook's own answers for a few fixed days, BEFORE any code is moved.

    python scripts/save_golden.py

It runs the code cells of tracks/stocks/notebook.ipynb unchanged (download, inputs, training,
evaluation), then repeats the notebook's "score one example" and "why" cells as if today were
each of the days below. The result is tests/golden/notebook_answers.json: the reference that
the reorganised code must reproduce. Needs the notebook's libraries, matplotlib included.
"""
import contextlib
import io
import json
import os
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # the notebook draws charts; we only want its numbers

REPO = Path(__file__).resolve().parents[1]
NOTEBOOK = REPO / "tracks" / "stocks" / "notebook.ipynb"
OUTPUT = REPO / "tests" / "golden" / "notebook_answers.json"

# Five fixed days: different weekdays, inside and outside the training years.
AS_OF_DAYS = ["2024-05-21", "2025-11-02", "2026-03-15", "2026-08-03", "2026-10-29"]

# Notebook cells, by position: 4 settings, 6 download, 8 clean, 10 inputs, 12 split, 14 train,
# 16 evaluate, 18 save the model, 20 score one example, 22 explain it.
PREPARE_CELLS = [4, 6, 8, 10, 12, 14, 16, 18]
SCORE_CELL, WHY_CELL = 20, 22


def main() -> None:
    cells = json.loads(NOTEBOOK.read_text(encoding="utf-8"))["cells"]
    code = {i: "".join(cell["source"]) for i, cell in enumerate(cells)
            if cell["cell_type"] == "code"}
    ns: dict = {}

    with tempfile.TemporaryDirectory() as scratch:
        os.chdir(scratch)  # the notebook writes artifacts/ here, not into the repository
        with contextlib.redirect_stdout(io.StringIO()):
            for i in PREPARE_CELLS:
                exec(code[i], ns)  # noqa: S102 - our own notebook, run on purpose
        all_prices = ns["prices"]

        days = []
        for as_of in AS_OF_DAYS:
            if as_of not in all_prices.index:
                raise SystemExit(f"{as_of} is not a trading day in the downloaded prices")
            ns["prices"] = all_prices.loc[:as_of]  # pretend the later days never happened
            with contextlib.redirect_stdout(io.StringIO()):
                exec(code[SCORE_CELL], ns)  # noqa: S102
                exec(code[WHY_CELL], ns)  # noqa: S102
            days.append({
                "as_of": ns["last_date"].date().isoformat(),
                "last_close": float(ns["last_close"]),
                "inputs": {name: float(ns["example"][name].iloc[0]) for name in ns["FEATURES"]},
                "predicted_move": float(ns["pred_return"]),
                "forecast_close": float(ns["pred_price"]),
                "naive_close": float(ns["last_close"]),
                "start_halalas": float(ns["start"]),
                "push_halalas": {name: float(ns["push"][name]) for name in ns["FEATURES"]},
            })
        os.chdir(REPO)  # leave the scratch folder before it is deleted

    golden = {
        "source": "tracks/stocks/notebook.ipynb, code cells run unchanged by scripts/save_golden.py",
        "ticker": ns["TICKER"],
        "model_version": ns["MODEL_VERSION"],
        "ridge_alpha": ns["search"].best_params_["ridge__alpha"],
        "rows": {"downloaded": len(ns["raw"]), "kept": len(all_prices),
                 "train": len(ns["train"]), "test": len(ns["test"])},
        "metrics_test": {
            "model_mae_sar": float(ns["model_mae"]), "naive_mae_sar": float(ns["naive_mae"]),
            "model_rmse_sar": float(ns["model_rmse"]), "naive_rmse_sar": float(ns["naive_rmse"]),
            "model_mape_pct": float(ns["model_mape"]), "naive_mape_pct": float(ns["naive_mape"]),
            "direction_hit_pct": float(ns["direction_hit"]),
            "mae_improvement_vs_naive_pct": float(ns["improvement"]),
        },
        "days": days,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(golden, indent=2) + "\n", encoding="utf-8")
    print(f"Saved the notebook's answers for {len(days)} days to {OUTPUT.relative_to(REPO)}")
    for day in days:
        print(f"  {day['as_of']}: close {day['last_close']:.2f} -> forecast "
              f"{day['forecast_close']:.3f} SAR (naive {day['naive_close']:.2f})")


if __name__ == "__main__":
    main()
