"""The tools at the edge (Yahoo, scikit-learn files) and the settings, without the internet."""
import warnings
from datetime import date

import pandas as pd
import pytest
from sklearn.exceptions import InconsistentVersionWarning

from conftest import LAST_DAY, make_history, random_walk
from stocks_service.adapters import ridge_model, yahoo_prices
from stocks_service.adapters.ridge_model import JoblibModelStore, RidgeTrainer
from stocks_service.adapters.yahoo_prices import YahooPriceSource
from stocks_service.config import Settings
from stocks_service.domain.errors import PriceSourceUnavailable
from stocks_service.domain.features import latest_features, training_rows

pytestmark = pytest.mark.unit


# ---------- Yahoo adapter, with a stand-in for the yfinance library ----------

def _yahoo_table(rows: list[tuple[str, float, int]]) -> pd.DataFrame:
    """What yfinance returns: one row per day, times in Riyadh's zone."""
    index = pd.DatetimeIndex([day for day, _, _ in rows], tz="Asia/Riyadh", name="Date")
    return pd.DataFrame({"Close": [close for _, close, _ in rows],
                         "Volume": [volume for _, _, volume in rows]}, index=index)


class FakeYahoo:
    def __init__(self, answers: list) -> None:
        self.answers = answers
        self.asked = 0

    def __call__(self, ticker):  # stands in for yf.Ticker(ticker)
        return self

    def history(self, **_):
        answer = self.answers[min(self.asked, len(self.answers) - 1)]
        self.asked += 1
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_days_with_no_trading_are_dropped(monkeypatch):
    table = _yahoo_table([("2026-10-27", 25.5, 1000), ("2026-10-28", 25.5, 0),
                          ("2026-10-29", 25.9, 2000)])
    monkeypatch.setattr(yahoo_prices.yf, "Ticker", FakeYahoo([table]))

    history = YahooPriceSource().history("2222.SR", date(2026, 10, 1), date(2026, 11, 1))

    assert history.days == (date(2026, 10, 27), date(2026, 10, 29))
    assert history.closes == (25.5, 25.9)
    assert history.ticker == "2222.SR"


def test_one_refusal_is_retried(monkeypatch):
    table = _yahoo_table([("2026-10-29", 25.9, 2000)])
    yahoo = FakeYahoo([RuntimeError("rate limited"), table])
    monkeypatch.setattr(yahoo_prices.yf, "Ticker", yahoo)

    history = YahooPriceSource(retry_wait_seconds=0).history(
        "2222.SR", date(2026, 10, 1), date(2026, 11, 1))

    assert len(history) == 1 and yahoo.asked == 2


def test_nothing_twice_is_a_clear_error(monkeypatch):
    yahoo = FakeYahoo([_yahoo_table([])])
    monkeypatch.setattr(yahoo_prices.yf, "Ticker", yahoo)

    with pytest.raises(PriceSourceUnavailable, match="2222.SR"):
        YahooPriceSource(retry_wait_seconds=0).history(
            "2222.SR", date(2026, 10, 1), date(2026, 11, 1))
    assert yahoo.asked == 2


# ---------- the scikit-learn model and its files ----------

@pytest.fixture(scope="module")
def trained():
    rows = training_rows(make_history(random_walk(200)))
    return RidgeTrainer([1, 100], "test-ridge", "2222.SR").fit(rows)


def test_the_explanation_adds_up_to_the_prediction(trained):
    features = latest_features(make_history(random_walk(60, seed=7)))

    explanation = trained.explain(features)

    total = explanation.start_move + sum(explanation.pushes.values())
    assert total == pytest.approx(trained.predict_move(features), abs=1e-12)


def test_a_saved_model_comes_back_the_same(trained, tmp_path):
    store = JoblibModelStore(tmp_path / "m" / "model.joblib", tmp_path / "m" / "meta.json")
    features = latest_features(make_history(random_walk(60, seed=7)))

    store.save(trained, {"model_version": "test-ridge", "ticker": "2222.SR"})
    loaded = store.load()

    assert loaded.predict_move(features) == trained.predict_move(features)
    assert (loaded.model_version, loaded.ticker) == ("test-ridge", "2222.SR")
    assert store.facts()["ticker"] == "2222.SR"


def test_a_model_from_another_scikit_learn_version_is_refused(trained, tmp_path, monkeypatch):
    store = JoblibModelStore(tmp_path / "model.joblib", tmp_path / "meta.json")
    store.save(trained, {"model_version": "test-ridge", "ticker": "2222.SR"})

    def load_with_warning(path):
        warnings.warn(InconsistentVersionWarning(
            estimator_name="Ridge", current_sklearn_version="1.9.1",
            original_sklearn_version="1.0.0"), stacklevel=1)

    monkeypatch.setattr(ridge_model.joblib, "load", load_with_warning)
    with pytest.raises(InconsistentVersionWarning):
        store.load()


def test_a_missing_model_file_is_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        JoblibModelStore(tmp_path / "nope.joblib", tmp_path / "nope.json").load()


# ---------- settings ----------

def test_defaults_are_the_notebooks_fixed_settings():
    settings = Settings(_env_file=None)

    assert settings.ticker == "2222.SR"
    assert (settings.start_date, settings.end_date) == (date(2021, 11, 1), date(2026, 11, 1))
    assert settings.test_start == date(2025, 11, 1)
    assert settings.model_version == "stocks-ridge-1.0.0"


def test_a_setting_can_be_changed_from_the_environment(monkeypatch):
    monkeypatch.setenv("STOCKS_TOP_REASONS", "5")
    assert Settings(_env_file=None).top_reasons == 5


def test_an_unknown_line_in_env_neither_stops_us_nor_leaks(tmp_path):
    """Stage 3's bug: an unrelated line stopped the service and its value was printed."""
    env_file = tmp_path / ".env"
    env_file.write_text("FAKE_API_KEY=sk-not-a-real-key-123\nSTOCKS_TOP_REASONS=2\n", "utf-8")

    settings = Settings(_env_file=env_file)

    assert settings.top_reasons == 2
    assert "sk-not-a-real-key-123" not in repr(settings)


def test_a_wrong_value_is_refused_at_start_up(monkeypatch):
    monkeypatch.setenv("STOCKS_TOP_REASONS", "many")
    with pytest.raises(ValueError, match="top_reasons"):
        Settings(_env_file=None)


def test_last_day_is_a_thursday():
    assert LAST_DAY.strftime("%A") == "Thursday"  # the other tests rely on it
