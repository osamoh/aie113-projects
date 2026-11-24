"""The model's eight inputs. A wrong input is a wrong forecast that still looks fine."""
from datetime import date
from math import sqrt

import pytest

from conftest import make_history, random_walk, trading_days
from stocks_service.domain.errors import NotEnoughHistory
from stocks_service.domain.features import (
    FEATURE_NAMES,
    MIN_DAYS,
    features_at,
    latest_features,
    split_by_time,
    training_rows,
)

pytestmark = pytest.mark.unit

# 21 closing prices chosen so every input can be worked out by hand, and so that the last
# four moves are all DIFFERENT (+10%, +5%, 0%, +10% after a long flat stretch). If two of them
# were equal, reading the wrong day would give the right number by luck.
BY_HAND = [10.0] * 17 + [11.0, 11.55, 11.55, 12.705]

# Which earlier days each input is allowed to look at, counted back from "today" (0).
LOOKS_AT = {
    "ret_1d": {0, 1},
    "ret_lag1": {1, 2},
    "ret_lag2": {2, 3},
    "ret_5d": {0, 5},
    "gap_ma5": set(range(5)),
    "gap_ma20": set(range(20)),
    "vol_10d": set(range(11)),
    "day_of_week": set(),
}


def test_feature_names_are_frozen():
    """The model was trained on exactly these inputs, in this order. Renaming one is skew."""
    assert FEATURE_NAMES == ("ret_1d", "ret_lag1", "ret_lag2", "ret_5d", "gap_ma5", "gap_ma20",
                             "vol_10d", "day_of_week")


def test_each_input_matches_the_hand_calculation():
    features = latest_features(make_history(BY_HAND))  # the last day is a Thursday

    assert features["ret_1d"] == pytest.approx(0.10)             # 12.705 / 11.55 - 1
    assert features["ret_lag1"] == pytest.approx(0.0)            # 11.55 / 11.55 - 1
    assert features["ret_lag2"] == pytest.approx(0.05)           # 11.55 / 11.00 - 1
    assert features["ret_5d"] == pytest.approx(0.2705)           # 12.705 / 10.00 - 1
    assert features["gap_ma5"] == pytest.approx(12.705 / (56.805 / 5) - 1)     # 5-day average
    assert features["gap_ma20"] == pytest.approx(12.705 / (206.805 / 20) - 1)  # 20-day average
    # The last ten moves: seven of 0%, one of +5%, two of +10%. Average 2.5%, sample spread:
    assert features["vol_10d"] == pytest.approx(sqrt((8 * 0.025**2 + 2 * 0.075**2) / 9))
    assert features["day_of_week"] == 4.0                        # Thursday


@pytest.mark.parametrize("name", FEATURE_NAMES)
def test_each_input_looks_at_exactly_the_days_it_should(name):
    """Nudge one earlier day's price at a time: the input must change for the days it is
    meant to read, and for no other day. This catches every "off by one day" mistake."""
    closes, days, today = random_walk(60), trading_days(60), 59
    original = features_at(days, closes, today)[name]

    for days_back in range(26):
        nudged = list(closes)
        nudged[today - days_back] *= 1.01
        changed = features_at(days, nudged, today)[name] != original
        assert changed == (days_back in LOOKS_AT[name]), (
            f"{name} {'changed' if changed else 'did not change'} "
            f"when the price {days_back} days back was nudged")


@pytest.mark.parametrize(("day", "expected"), [
    (date(2026, 10, 25), 0.0), (date(2026, 10, 26), 1.0), (date(2026, 10, 27), 2.0),
    (date(2026, 10, 28), 3.0), (date(2026, 10, 29), 4.0),
])
def test_day_of_week_counts_from_sunday(day, expected):
    assert latest_features(make_history(BY_HAND, last=day))["day_of_week"] == expected


def test_nineteen_days_are_not_enough_but_twenty_are():
    with pytest.raises(NotEnoughHistory):
        latest_features(make_history([10.0] * (MIN_DAYS - 1)))
    assert set(latest_features(make_history([10.0] * MIN_DAYS))) == set(FEATURE_NAMES)


@pytest.mark.parametrize("position", [19, 25, 40, 58])
def test_only_the_past_counts(position):
    """A day's inputs must be the same whether or not later days exist."""
    closes = random_walk(60)
    days = trading_days(60)

    with_later_days = features_at(days, closes, position)
    without_later_days = features_at(days[:position + 1], closes[:position + 1], position)

    assert with_later_days == without_later_days


def test_training_rows_pair_each_day_with_the_next_close():
    closes = random_walk(30)
    rows = training_rows(make_history(closes))

    assert len(rows) == 30 - MIN_DAYS  # the first 19 days lack history; the last has no "next"
    assert rows[0].close == closes[19] and rows[0].next_close == closes[20]
    assert rows[-1].next_close == closes[-1]
    assert rows[0].target == pytest.approx(closes[20] / closes[19] - 1)


def test_split_by_time_never_puts_a_later_day_in_training():
    rows = training_rows(make_history(random_walk(60)))
    test_start = rows[25].day

    train, test = split_by_time(rows, test_start)

    assert len(train) + len(test) == len(rows)
    assert all(row.day < test_start for row in train)
    assert all(row.day >= test_start for row in test)
