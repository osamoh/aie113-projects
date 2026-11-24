"""Golden tests: the same inputs still give the notebook's answers.

tests/golden/notebook_answers.json was saved in Stage 1 by running the notebook's own cells,
before any code was moved. If one of these tests fails, the model or the code around it has
changed its answers, whatever else still "works".
"""
import subprocess
import sys
from datetime import date

import pytest

from conftest import REPO
from stocks_service.adapters.ridge_model import RidgeTrainer
from stocks_service.adapters.yahoo_prices import YahooPriceSource
from stocks_service.config import Settings
from stocks_service.domain.forecast import make_forecast
from stocks_service.service.training import TrainingService

SAVED_DAYS = ["2024-05-21", "2025-11-02", "2026-03-15", "2026-08-03", "2026-10-29"]
MAX_WORSE_THAN_NAIVE_PCT = 5.0  # the agreed quality bar (today the model is 1.2% worse)


@pytest.mark.golden
def test_the_golden_file_has_the_five_days_we_expect(golden):
    assert [day["as_of"] for day in golden["days"]] == SAVED_DAYS


@pytest.mark.golden
@pytest.mark.parametrize("position", range(len(SAVED_DAYS)), ids=SAVED_DAYS)
def test_the_committed_model_gives_the_notebooks_forecast(real_model, golden, position):
    """No internet needed: the notebook's saved inputs go in, its saved forecast must come out."""
    day = golden["days"][position]

    forecast = make_forecast(
        ticker=golden["ticker"], as_of=date.fromisoformat(day["as_of"]),
        last_close=day["last_close"], features=day["inputs"],
        predicted_move=real_model.predict_move(day["inputs"]),
        explanation=real_model.explain(day["inputs"]),
        model_version=real_model.model_version)

    assert forecast.predicted_move == pytest.approx(day["predicted_move"], abs=1e-9)
    assert forecast.forecast_close == pytest.approx(day["forecast_close"], abs=1e-9)
    assert forecast.naive_close == day["naive_close"]
    assert forecast.start_halalas == pytest.approx(day["start_halalas"], abs=1e-9)
    for reason in forecast.reasons:
        assert reason.push_halalas == pytest.approx(day["push_halalas"][reason.name], abs=1e-9)


@pytest.mark.golden
def test_the_models_facts_file_reports_the_notebooks_numbers(model_store, golden):
    facts, saved = model_store.facts(), golden["metrics_test"]

    assert facts["model_version"] == golden["model_version"]
    assert facts["ridge_alpha"] == golden["ridge_alpha"]
    assert (facts["train"]["rows"], facts["test"]["rows"]) == (
        golden["rows"]["train"], golden["rows"]["test"])
    assert facts["metrics_test"]["model"]["mae_sar"] == round(saved["model_mae_sar"], 4)
    assert facts["metrics_test"]["naive_baseline"]["mae_sar"] == round(saved["naive_mae_sar"], 4)
    assert facts["metrics_test"]["mae_improvement_vs_naive_pct"] == round(
        saved["mae_improvement_vs_naive_pct"], 2)


@pytest.mark.golden
@pytest.mark.network
def test_download_retrain_and_compare_with_the_notebook():
    """The full Stage 1 check: real prices, retrained model, every saved number compared."""
    result = subprocess.run([sys.executable, "scripts/check_golden.py"], cwd=REPO,
                            capture_output=True, text=True, timeout=300, check=False)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
    assert "5/5 days match the notebook's answers" in result.stdout


@pytest.mark.golden
@pytest.mark.network
def test_a_retrained_model_is_not_much_worse_than_the_naive_guess():
    """Catches a model that silently got worse: the bar is "at most 5% worse than naive"."""
    settings = Settings(_env_file=None)
    source = YahooPriceSource()
    history = source.history(settings.ticker, settings.start_date, settings.end_date)
    trainer = RidgeTrainer(settings.alphas, settings.model_version, settings.ticker)

    _, report = TrainingService(source, trainer, store=None).train_from(
        history, settings.test_start)

    worse_by = -report.metrics.mae_improvement_vs_naive_pct
    assert worse_by <= MAX_WORSE_THAN_NAIVE_PCT, (
        f"the model's average error is {worse_by:.1f}% worse than 'tomorrow = today'")
