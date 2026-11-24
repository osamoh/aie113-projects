"""The API from the outside, the way a client app uses it.

The model and the prices are stand-ins and the clock is fixed, so these tests need no internet
and give the same result every run. They protect the contract: shapes, status codes, errors.
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from conftest import LAST_DAY, RIYADH, FakeModel, FakePriceSource, make_history, random_walk
from stocks_service.api.app import create_app
from stocks_service.domain.errors import PriceSourceUnavailable

pytestmark = pytest.mark.integration

GOOD = {"ticker": "2222.SR"}
MARKER = "ZZ-PRIVATE-ZZ"  # stands for something private a caller might send by mistake


def error_of(response) -> dict:
    body = response.json()
    assert set(body) == {"error"}, "every failure uses the one error shape"
    assert {"code", "message", "trace_id"} <= set(body["error"])
    return body["error"]


# ---------- a good request ----------

def test_a_good_request_gets_the_promised_shape(client_factory, history):
    response = client_factory(model=FakeModel(move=0.001)).post("/v1/forecast", json=GOOD)

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"ticker", "as_of", "last_close_sar", "forecast_close_sar",
                         "naive_close_sar", "change_halalas", "top_reasons", "model_version",
                         "model_vs_naive_pct", "disclaimer", "trace_id"}
    last_close = history.closes[-1]
    assert body["ticker"] == "2222.SR"
    assert body["as_of"] == LAST_DAY.isoformat()
    assert body["last_close_sar"] == last_close
    assert body["forecast_close_sar"] == pytest.approx(last_close * 1.001, abs=0.0005)
    assert body["model_version"] == response.headers["X-Model-Version"] == "fake-1"


def test_the_naive_guess_and_the_disclaimer_are_always_in_the_answer(client_factory, history):
    body = client_factory().post("/v1/forecast", json=GOOD).json()

    assert body["naive_close_sar"] == history.closes[-1]
    assert body["disclaimer"] == "A teaching example, not investment advice."
    assert body["model_vs_naive_pct"] < 0, "we say openly that the model is worse than naive"


def test_three_reasons_come_back_biggest_first(client_factory):
    reasons = client_factory().post("/v1/forecast", json=GOOD).json()["top_reasons"]

    assert [reason["input"] for reason in reasons] == [
        "distance from 5-day average", "move two days ago", "today's move"]
    assert all(set(reason) == {"input", "value", "push_halalas"} for reason in reasons)


def test_ticker_case_and_spaces_do_not_matter(client_factory):
    response = client_factory().post("/v1/forecast", json={"ticker": " 2222.sr "})
    assert response.status_code == 200 and response.json()["ticker"] == "2222.SR"


# ---------- bad requests ----------

BAD_BODIES = {
    "empty object": {},
    "typo in the field name": {"tiker": "2222.SR"},
    "number instead of text": {"ticker": 2222},
    "nothing instead of text": {"ticker": None},
    "empty text": {"ticker": ""},
    "only spaces": {"ticker": "   "},
    "too long": {"ticker": "2" * 13},
    "forbidden characters": {"ticker": "22;22"},
    "extra field": {"ticker": "2222.SR", "is_admin": True},
    "a list": ["2222.SR"],
    "plain text": "2222.SR",
}


@pytest.mark.parametrize("body", BAD_BODIES.values(), ids=BAD_BODIES.keys())
def test_every_kind_of_bad_request_is_rejected_the_same_way(client_factory, body):
    source = FakePriceSource(make_history(random_walk(60)))
    response = client_factory(source=source).post("/v1/forecast", json=body)

    assert response.status_code == 422
    error = error_of(response)
    assert error["code"] == "INVALID_REQUEST"
    assert error["details"] and all(set(d) == {"field", "problem"} for d in error["details"])
    assert source.calls == [], "a bad request must never reach the price source"


def test_a_body_that_is_not_json_is_rejected_in_plain_words(client_factory):
    response = client_factory().post("/v1/forecast", content="{ticker: 2222",
                                     headers={"content-type": "application/json"})

    assert response.status_code == 422
    assert error_of(response)["details"] == [
        {"field": "body", "problem": "The body is not valid JSON"}]


@pytest.mark.parametrize("body", [
    {"ticker": MARKER * 3},                       # a value that is too long
    {"ticker": f"22 {MARKER}"},                   # a value with forbidden characters
    {"ticker": "2222.SR", "note": MARKER},        # the value of a field we do not accept
    {"ticker": {"nested": MARKER}},               # the wrong type
])
def test_an_error_never_repeats_the_values_the_caller_sent(client_factory, body):
    response = client_factory().post("/v1/forecast", json=body)

    assert response.status_code == 422
    assert MARKER not in response.text


# ---------- failures that are not the caller's fault ----------

def test_an_unknown_ticker_is_a_clear_404_and_nothing_is_downloaded(client_factory, history):
    source = FakePriceSource(history)
    response = client_factory(source=source).post("/v1/forecast", json={"ticker": "1120.SR"})

    assert response.status_code == 404
    assert error_of(response)["code"] == "UNKNOWN_TICKER"
    assert "1120" not in response.text
    assert source.calls == []


def test_price_source_down_is_a_503_that_says_when_to_retry(client_factory):
    down = FakePriceSource(error=PriceSourceUnavailable(f"upstream said {MARKER}"))
    response = client_factory(source=down).post("/v1/forecast", json=GOOD)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == "60"
    assert error_of(response)["code"] == "PRICE_SOURCE_UNAVAILABLE"
    assert MARKER not in response.text, "the source's own words stay in our log"


def test_too_few_days_is_a_503_not_a_guess(client_factory):
    short = FakePriceSource(make_history(random_walk(5)))
    response = client_factory(source=short).post("/v1/forecast", json=GOOD)

    assert response.status_code == 503
    assert error_of(response)["code"] == "NOT_ENOUGH_PRICES"


def test_an_unexpected_crash_leaks_nothing(client_factory):
    crashing = FakePriceSource(error=RuntimeError(f"database password is {MARKER}"))
    response = client_factory(source=crashing).post("/v1/forecast", json=GOOD)

    assert response.status_code == 500
    error = error_of(response)
    assert error["code"] == "INTERNAL_ERROR"
    assert MARKER not in response.text and "Traceback" not in response.text
    assert error["trace_id"] == response.headers["X-Trace-Id"]


# ---------- only finished days ----------

@pytest.mark.parametrize(("now", "expected_as_of"), [
    (datetime(2026, 10, 29, 15, 59, tzinfo=RIYADH), "2026-10-28"),
    (datetime(2026, 10, 29, 16, 0, tzinfo=RIYADH), "2026-10-29"),
])
def test_todays_price_is_used_only_after_the_market_has_closed(client_factory, now,
                                                                expected_as_of):
    body = client_factory(now=now).post("/v1/forecast", json=GOOD).json()
    assert body["as_of"] == expected_as_of


# ---------- the other addresses ----------

def test_health_ready_and_model_info(client_factory):
    client = client_factory()

    assert client.get("/v1/health").json()["status"] == "ok"
    assert client.get("/v1/ready").json()["status"] == "ready"
    facts = client.get("/v1/model-info").json()
    assert facts["ticker"] == "2222.SR"
    assert "naive_baseline" in facts["metrics_test"], "the baseline is part of the facts"


def test_before_the_model_is_loaded_the_service_says_not_ready():
    client = TestClient(create_app())  # start-up has not run: no model yet

    for response in (client.get("/v1/ready"), client.get("/v1/model-info"),
                     client.post("/v1/forecast", json=GOOD)):
        assert response.status_code == 503
        assert error_of(response)["code"] == "MODEL_UNAVAILABLE"
        assert response.headers["Retry-After"] == "5"


def test_without_a_model_file_the_service_refuses_to_start(monkeypatch, tmp_path):
    """A container that cannot serve must not look alive: it stops, with a clear message."""
    monkeypatch.setenv("STOCKS_MODEL_PATH", str(tmp_path / "missing.joblib"))
    monkeypatch.setenv("STOCKS_META_PATH", str(tmp_path / "missing.json"))

    with pytest.raises(RuntimeError, match="No trained model"), TestClient(create_app()):
        pass


def test_wrong_address_and_wrong_method_use_the_same_error_shape(client_factory):
    client = client_factory()

    assert error_of(client.get("/v1/nope"))["code"] == "NOT_FOUND"
    assert error_of(client.get("/v1/forecast"))["code"] == "METHOD_NOT_ALLOWED"


def test_a_harmless_trace_id_is_kept_and_a_strange_one_is_replaced(client_factory):
    client = client_factory()

    kept = client.get("/v1/health", headers={"X-Trace-Id": "order-12345678"})
    replaced = client.get("/v1/health", headers={"X-Trace-Id": "<script>alert(1)</script>"})

    assert kept.headers["X-Trace-Id"] == "order-12345678"
    assert replaced.headers["X-Trace-Id"].isalnum() and len(replaced.headers["X-Trace-Id"]) == 16


def test_the_docs_page_describes_exactly_our_four_addresses(client_factory):
    client = client_factory()

    assert client.get("/docs").status_code == 200
    assert sorted(client.get("/openapi.json").json()["paths"]) == [
        "/v1/forecast", "/v1/health", "/v1/model-info", "/v1/ready"]
