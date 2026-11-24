"""Prices, the forecast's rules, the error measures, the market clock and the data checks."""
from datetime import date, datetime, timedelta

import pytest

from conftest import LAST_DAY, RIYADH, make_history, random_walk
from stocks_service.domain.data_checks import price_problems
from stocks_service.domain.features import FEATURE_NAMES, TrainingRow
from stocks_service.domain.forecast import DISCLAIMER, Explanation, Reason, evaluate, make_forecast
from stocks_service.domain.market import latest_complete_day
from stocks_service.domain.prices import PriceHistory, PricePoint

pytestmark = pytest.mark.unit


# ---------- prices ----------

@pytest.mark.parametrize("close", [0.0, -1.0, float("nan"), float("inf")])
def test_a_price_must_be_a_positive_number(close):
    with pytest.raises(ValueError, match="positive price"):
        PricePoint(LAST_DAY, close)


@pytest.mark.parametrize("second_day", [LAST_DAY, LAST_DAY - timedelta(days=1)])
def test_days_must_be_in_order_with_no_repeats(second_day):
    with pytest.raises(ValueError, match="in order"):
        PriceHistory("2222.SR", (PricePoint(LAST_DAY, 10.0), PricePoint(second_day, 10.0)))


def test_up_to_drops_later_days_and_keeps_the_day_itself():
    history = make_history([10.0, 11.0, 12.0])  # Tuesday, Wednesday, Thursday

    assert history.up_to(LAST_DAY - timedelta(days=1)).closes == (10.0, 11.0)
    assert history.up_to(LAST_DAY).closes == (10.0, 11.0, 12.0)


# ---------- the forecast's rules ----------

def _forecast(move=0.002, pushes=None):
    pushes = pushes or {**dict.fromkeys(FEATURE_NAMES, 0.0), "ret_1d": 0.003, "ret_lag2": -0.002}
    features = {**dict.fromkeys(FEATURE_NAMES, 0.0), "ret_1d": 0.0125, "day_of_week": 4.0}
    return make_forecast("2222.SR", LAST_DAY, last_close=25.0, features=features,
                         predicted_move=move,
                         explanation=Explanation(start_move=move - sum(pushes.values()),
                                                 pushes=pushes),
                         model_version="test-1")


def test_the_naive_guess_is_always_todays_close():
    assert _forecast(move=0.05).naive_close == 25.0
    assert _forecast(move=-0.05).naive_close == 25.0


def test_the_move_becomes_a_price_and_a_change_in_halalas():
    forecast = _forecast(move=0.002)

    assert forecast.forecast_close == pytest.approx(25.05)   # 25.00 x 1.002
    assert forecast.change_halalas == pytest.approx(5.0)     # 0.05 SAR = 5 halalas


def test_reasons_add_up_to_the_change_and_the_biggest_comes_first():
    forecast = _forecast()

    total = forecast.start_halalas + sum(reason.push_halalas for reason in forecast.reasons)
    assert total == pytest.approx(forecast.change_halalas)
    sizes = [abs(reason.push_halalas) for reason in forecast.reasons]
    assert sizes == sorted(sizes, reverse=True)
    assert forecast.reasons[0].name == "ret_1d" and forecast.reasons[0].label == "today's move"


def test_every_forecast_carries_the_disclaimer():
    assert _forecast().disclaimer == DISCLAIMER == "A teaching example, not investment advice."


def test_a_reason_reads_as_a_percent_or_a_weekday():
    assert Reason("ret_1d", "today's move", 0.0125, 1.0).value_text == "+1.25%"
    assert Reason("ret_1d", "today's move", -0.003, 1.0).value_text == "-0.30%"
    assert Reason("day_of_week", "day of the week", 4.0, 1.0).value_text == "Thursday"
    assert Reason("day_of_week", "day of the week", 0.0, 1.0).value_text == "Sunday"


# ---------- the error measures ----------

def test_evaluate_matches_a_hand_calculation():
    # Three days, each closing at 10.00. The next closes: 11.00, 9.00, 10.00.
    rows = [TrainingRow(LAST_DAY, 10.0, next_close, {}) for next_close in (11.0, 9.0, 10.0)]
    # The model says +5%, +5%, 0%: forecasts 10.50, 10.50, 10.00. Errors 0.50, 1.50, 0.
    metrics = evaluate(rows, [0.05, 0.05, 0.0])

    assert metrics.model_mae_sar == pytest.approx(2.0 / 3)
    assert metrics.naive_mae_sar == pytest.approx(2.0 / 3)   # naive errors: 1, 1, 0
    assert metrics.mae_improvement_vs_naive_pct == pytest.approx(0.0)
    assert metrics.days_that_moved == 2                       # the flat day is not counted
    assert metrics.direction_hit_pct == pytest.approx(50.0)   # right on the rise, wrong on the fall


def test_a_model_worse_than_naive_shows_a_negative_improvement():
    rows = [TrainingRow(LAST_DAY, 10.0, 10.0, {})] * 2 + [TrainingRow(LAST_DAY, 10.0, 10.1, {})]
    assert evaluate(rows, [0.05, 0.05, 0.05]).mae_improvement_vs_naive_pct < 0


def test_evaluate_copes_with_a_period_where_the_price_never_moved():
    rows = [TrainingRow(LAST_DAY, 10.0, 10.0, {})] * 3
    metrics = evaluate(rows, [0.01, 0.01, 0.01])
    assert metrics.days_that_moved == 0 and metrics.direction_hit_pct == 0.0


def test_evaluate_refuses_an_empty_test_period():
    with pytest.raises(ValueError, match="no test days"):
        evaluate([], [])


# ---------- the market clock ----------

@pytest.mark.parametrize(("now", "expected"), [
    (datetime(2026, 11, 24, 10, 0, tzinfo=RIYADH), date(2026, 11, 23)),   # market open
    (datetime(2026, 11, 24, 15, 59, tzinfo=RIYADH), date(2026, 11, 23)),  # one minute early
    (datetime(2026, 11, 24, 16, 0, tzinfo=RIYADH), date(2026, 11, 24)),   # final
    (datetime(2026, 11, 24, 23, 59, tzinfo=RIYADH), date(2026, 11, 24)),
    (datetime(2026, 11, 25, 0, 1, tzinfo=RIYADH), date(2026, 11, 24)),    # just after midnight
])
def test_todays_price_counts_only_from_four_pm_riyadh(now, expected):
    assert latest_complete_day(now) == expected


def test_the_clock_is_read_in_riyadh_time_whatever_zone_it_arrives_in():
    one_pm_utc = datetime(2026, 11, 24, 13, 0, tzinfo=RIYADH).astimezone(tz=None)
    assert latest_complete_day(one_pm_utc) == date(2026, 11, 23)  # 13:00 Riyadh: not final yet


def test_a_time_without_a_zone_is_refused():
    with pytest.raises(ValueError, match="time zone"):
        latest_complete_day(datetime(2026, 11, 24, 18, 0))


# ---------- the data checks ----------

def test_clean_prices_have_no_problems():
    assert price_problems(make_history(random_walk(60)), as_of=LAST_DAY) == []


def test_a_price_from_the_future_is_named():
    problems = price_problems(make_history(random_walk(30)), as_of=LAST_DAY - timedelta(days=1))
    assert any("from the future" in problem for problem in problems)


def test_a_friday_price_is_named():
    friday = date(2026, 10, 30)
    history = PriceHistory("2222.SR", (PricePoint(LAST_DAY, 10.0), PricePoint(friday, 10.0)))
    assert any("Friday" in problem for problem in price_problems(history, as_of=friday))


def test_an_impossible_jump_is_named():
    problems = price_problems(make_history([10.0, 10.1, 13.0]), as_of=LAST_DAY)
    assert any("moved +29% in one day" in problem for problem in problems)


def test_stale_prices_are_named():
    problems = price_problems(make_history(random_walk(30)), as_of=LAST_DAY + timedelta(days=15))
    assert any("15 days old" in problem for problem in problems)


def test_no_prices_at_all_is_a_problem():
    assert price_problems(PriceHistory("2222.SR", ()), as_of=LAST_DAY) == ["no prices at all"]
