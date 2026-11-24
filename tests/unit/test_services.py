"""The two jobs (forecast, train) and the price memory, with stand-ins for every tool."""
from datetime import UTC, datetime, timedelta

import pytest

from conftest import LAST_DAY, FakeModel, FakePriceSource, make_history, random_walk
from stocks_service import cli
from stocks_service.adapters.cached_prices import CachedPriceSource
from stocks_service.domain.errors import NotEnoughHistory, PriceSourceUnavailable, UnknownTicker
from stocks_service.service.forecasting import ForecastService
from stocks_service.service.training import TrainingService, facts_for

pytestmark = pytest.mark.unit


# ---------- forecasting ----------

def test_an_unknown_ticker_is_refused_before_anything_is_downloaded(history):
    source = FakePriceSource(history)

    with pytest.raises(UnknownTicker):
        ForecastService(source, FakeModel()).forecast("1120.SR", as_of=LAST_DAY)

    assert source.calls == []


def test_prices_are_asked_for_only_up_to_the_day_given(history):
    source = FakePriceSource(history)

    ForecastService(source, FakeModel(), lookback_days=90).forecast("2222.SR", as_of=LAST_DAY)

    assert source.calls == [("2222.SR", LAST_DAY - timedelta(days=90),
                             LAST_DAY + timedelta(days=1))]


def test_days_after_the_day_given_are_dropped_even_if_the_source_sends_them():
    """A careless price source must not be able to leak the future into a forecast."""
    closes = random_walk(60)
    with_future = make_history(closes + [99.0, 98.0], last=LAST_DAY + timedelta(days=4))
    honest = make_history(closes)

    leaky = ForecastService(FakePriceSource(with_future), FakeModel()).forecast(
        "2222.SR", as_of=LAST_DAY)
    clean = ForecastService(FakePriceSource(honest), FakeModel()).forecast(
        "2222.SR", as_of=LAST_DAY)

    assert leaky.as_of == LAST_DAY
    assert leaky == clean


def test_too_few_days_is_an_error_not_a_guess():
    source = FakePriceSource(make_history(random_walk(19)))
    with pytest.raises(NotEnoughHistory):
        ForecastService(source, FakeModel()).forecast("2222.SR", as_of=LAST_DAY)


def test_the_forecast_says_which_model_and_which_day_it_used(history):
    result = ForecastService(FakePriceSource(history), FakeModel(move=0.01)).forecast(
        "2222.SR", as_of=LAST_DAY)

    assert result.model_version == "fake-1"
    assert result.as_of == LAST_DAY
    assert result.last_close == history.closes[-1]
    assert result.forecast_close == pytest.approx(history.closes[-1] * 1.01)


def test_the_command_line_also_shows_the_naive_guess_and_the_disclaimer(history):
    forecast = ForecastService(FakePriceSource(history), FakeModel()).forecast_from(history)

    text = cli._render(forecast, improvement_vs_naive_pct=-1.17)

    assert "Naive forecast" in text and "tomorrow = today" in text
    assert "-1.17% against the naive guess" in text
    assert text.endswith("A teaching example, not investment advice.")


# ---------- training ----------

class RecordingTrainer:
    def __init__(self) -> None:
        self.rows_seen = []

    def fit(self, rows):
        self.rows_seen = list(rows)
        return FakeModel(move=0.0)


class RecordingStore:
    def __init__(self) -> None:
        self.saved = None

    def save(self, model, facts) -> None:
        self.saved = (model, facts)


def test_the_model_never_sees_the_test_days_while_learning(history):
    trainer = RecordingTrainer()
    test_start = history.days[45]

    _, report = TrainingService(FakePriceSource(history), trainer, RecordingStore()).train_from(
        history, test_start)

    assert trainer.rows_seen == report.train
    assert all(row.day < test_start for row in trainer.rows_seen)
    assert report.metrics.days == len(report.test) > 0


def test_a_model_that_predicts_no_move_scores_exactly_like_the_naive_guess(history):
    _, report = TrainingService(FakePriceSource(history), RecordingTrainer(),
                                RecordingStore()).train_from(history, history.days[45])

    assert report.metrics.model_mae_sar == pytest.approx(report.metrics.naive_mae_sar)
    assert report.metrics.mae_improvement_vs_naive_pct == pytest.approx(0.0)


def test_the_saved_facts_always_include_the_naive_baseline(history):
    store = RecordingStore()
    service = TrainingService(FakePriceSource(history), RecordingTrainer(), store)

    service.train("2222.SR", history.days[0], LAST_DAY, history.days[45],
                  created_at=datetime(2026, 11, 24, tzinfo=UTC))

    _, facts = store.saved
    assert facts["metrics_test"]["naive_baseline"]["mae_sar"] > 0
    assert "mae_improvement_vs_naive_pct" in facts["metrics_test"]
    assert facts["test"]["start"] == history.days[45].isoformat()
    assert facts == facts_for(*service.train_from(history, history.days[45]),
                              created_at=datetime(2026, 11, 24, tzinfo=UTC))


# ---------- the price memory ----------

class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_the_second_ask_is_answered_from_memory(history):
    source, clock = FakePriceSource(history), Clock()
    cached = CachedPriceSource(source, keep_seconds=900, clock=clock)

    first = cached.history("2222.SR", LAST_DAY - timedelta(days=90), LAST_DAY)
    clock.now += 899
    second = cached.history("2222.SR", LAST_DAY - timedelta(days=90), LAST_DAY)

    assert first is second
    assert len(source.calls) == 1


def test_memory_is_forgotten_after_the_keep_time(history):
    source, clock = FakePriceSource(history), Clock()
    cached = CachedPriceSource(source, keep_seconds=900, clock=clock)

    cached.history("2222.SR", LAST_DAY - timedelta(days=90), LAST_DAY)
    clock.now += 901
    cached.history("2222.SR", LAST_DAY - timedelta(days=90), LAST_DAY)

    assert len(source.calls) == 2


def test_a_different_question_is_not_answered_from_memory(history):
    source = FakePriceSource(history)
    cached = CachedPriceSource(source, keep_seconds=900, clock=Clock())

    cached.history("2222.SR", LAST_DAY - timedelta(days=90), LAST_DAY)
    cached.history("2222.SR", LAST_DAY - timedelta(days=90), LAST_DAY + timedelta(days=1))

    assert len(source.calls) == 2


def test_a_failure_is_never_remembered(history):
    failing = FakePriceSource(error=PriceSourceUnavailable("down"))
    cached = CachedPriceSource(failing, keep_seconds=900, clock=Clock())

    for _ in range(2):
        with pytest.raises(PriceSourceUnavailable):
            cached.history("2222.SR", LAST_DAY - timedelta(days=90), LAST_DAY)

    assert len(failing.calls) == 2  # asked again: the failure was not served from memory
