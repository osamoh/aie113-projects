"""How the REAL model behaves, on made-up prices.

The unit tests can all pass while the model itself is wrong. These tests load the committed
model and check promises about its behaviour that should hold whatever the prices are.
"""
import random
from datetime import timedelta

import pytest

from conftest import LAST_DAY, FakePriceSource, make_history, random_walk
from stocks_service.domain.errors import UnknownTicker
from stocks_service.domain.features import latest_features
from stocks_service.service.forecasting import ForecastService

pytestmark = pytest.mark.behaviour


@pytest.fixture(scope="module")
def forecaster(real_model):
    return ForecastService(FakePriceSource(), real_model)


def test_only_the_past_counts(real_model):
    """Invariance: the forecast for a day must not change when the later days change."""
    closes = random_walk(120)
    day_80 = make_history(closes).days[79]
    as_it_really_was = make_history(closes)
    with_a_different_future = make_history(closes[:80] + [c * 3 for c in closes[80:]])
    with_no_future = make_history(closes[:80], last=day_80)

    forecasts = [ForecastService(FakePriceSource(h), real_model).forecast("2222.SR", as_of=day_80)
                 for h in (as_it_really_was, with_a_different_future, with_no_future)]

    assert forecasts[0] == forecasts[1] == forecasts[2]


@pytest.mark.parametrize("typical_move", [0.005, 0.01, 0.02, 0.03])
def test_the_forecast_stays_close_to_todays_price(forecaster, typical_move):
    """Whatever realistic prices we invent, the forecast stays within 3% of today's close."""
    for seed in range(50):
        history = make_history(random_walk(60, seed=seed, typical_move=typical_move))
        result = forecaster.forecast_from(history)
        assert abs(result.forecast_close / result.last_close - 1) < 0.03, (seed, typical_move)
        assert result.forecast_close > 0


def test_a_market_crash_does_not_produce_a_wild_forecast(forecaster):
    closes = random_walk(55) + [26.0, 23.4, 21.1, 19.0, 17.1]  # four days of about -10%
    result = forecaster.forecast_from(make_history(closes))
    assert abs(result.forecast_close / result.last_close - 1) < 0.03


def test_doubling_every_price_doubles_the_forecast(forecaster):
    """The inputs are relative moves, so the scale of the price must not matter."""
    closes = random_walk(60)
    single = forecaster.forecast_from(make_history(closes))
    double = forecaster.forecast_from(make_history([c * 2 for c in closes]))

    assert double.forecast_close == pytest.approx(single.forecast_close * 2, rel=1e-9)
    assert double.predicted_move == pytest.approx(single.predicted_move, abs=1e-12)


def test_a_flat_price_gives_a_forecast_within_about_a_halala(forecaster):
    result = forecaster.forecast_from(make_history([25.0] * 30))
    assert abs(result.change_halalas) < 2.0  # 2 halalas = 0.02 SAR on a 25 SAR share


def test_a_bigger_rise_today_gives_a_higher_forecast(real_model):
    """Direction: the notebook found "today's move" is the strongest input, and pushes up."""
    features = latest_features(make_history(random_walk(60)))

    calm = real_model.predict_move({**features, "ret_1d": 0.00})
    strong_rise = real_model.predict_move({**features, "ret_1d": 0.03})

    assert strong_rise > calm


def test_the_reasons_always_add_up_to_the_forecast(forecaster):
    rng = random.Random(7)
    for _ in range(25):
        history = make_history(random_walk(60, seed=rng.randrange(10_000)))
        result = forecaster.forecast_from(history)
        total = result.start_halalas + sum(reason.push_halalas for reason in result.reasons)
        assert total == pytest.approx(result.change_halalas, abs=1e-9)
        assert len(result.reasons) == 8


def test_the_same_prices_always_give_the_same_forecast(forecaster):
    history = make_history(random_walk(60))
    assert forecaster.forecast_from(history) == forecaster.forecast_from(history)


def test_the_model_refuses_a_share_it_was_never_trained_on(forecaster):
    with pytest.raises(UnknownTicker):
        forecaster.forecast_from(make_history(random_walk(60), ticker="1120.SR"))


def test_weekend_gaps_do_not_confuse_it(forecaster):
    """Trading days skip Friday and Saturday; a history ending on a Sunday must still work."""
    sunday = LAST_DAY - timedelta(days=4)
    result = forecaster.forecast_from(make_history(random_walk(60), last=sunday))
    assert result.as_of == sunday and result.reasons
