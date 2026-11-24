"""Data checks on the REAL price source. These need the internet, so they are slow tests.

The rules themselves (what counts as a problem) are unit-tested without the internet in
tests/unit/test_prices_and_rules.py. Here we point them at what Yahoo actually sends.
"""
from datetime import UTC, datetime, timedelta

import pytest

from stocks_service.adapters.yahoo_prices import YahooPriceSource
from stocks_service.config import Settings
from stocks_service.domain.data_checks import price_problems
from stocks_service.domain.features import MIN_DAYS
from stocks_service.domain.market import latest_complete_day

pytestmark = [pytest.mark.data, pytest.mark.network]


@pytest.fixture(scope="module")
def settings() -> Settings:
    return Settings(_env_file=None)


def test_the_training_prices_have_no_problems(settings):
    history = YahooPriceSource().history(settings.ticker, settings.start_date, settings.end_date)

    assert price_problems(history, as_of=settings.end_date - timedelta(days=1)) == []
    assert len(history) > 1000, "about five years of trading days"
    assert 5 < min(history.closes) and max(history.closes) < 100, "prices in SAR, sensible range"


def test_the_latest_prices_are_fresh_and_enough_for_a_forecast(settings):
    as_of = latest_complete_day(datetime.now(UTC))
    history = YahooPriceSource().history(
        settings.ticker, as_of - timedelta(days=settings.lookback_days),
        as_of + timedelta(days=1)).up_to(as_of)

    assert price_problems(history, as_of=as_of) == []
    assert len(history) >= MIN_DAYS
