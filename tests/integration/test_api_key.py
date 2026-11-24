"""The API with a key: no key or the wrong key gets nothing, the right key gets the forecast,
and the key never comes back out in a response or a log line."""
import logging

import pytest

from conftest import FakePriceSource
from stocks_service.domain.errors import PriceSourceUnavailable

pytestmark = pytest.mark.integration

FAKE_KEY = "practice-only-0123456789abcdefgh"  # made for these tests; real keys never in code
GOOD = {"ticker": "2222.SR"}


@pytest.fixture
def protected(client_factory, monkeypatch):
    """The API started with a key, as it would be inside the container."""
    monkeypatch.setenv("STOCKS_API_KEY", FAKE_KEY)
    return client_factory


def test_with_the_right_key_the_forecast_comes_back(protected):
    response = protected().post("/v1/forecast", json=GOOD, headers={"X-API-Key": FAKE_KEY})
    assert response.status_code == 200
    assert FAKE_KEY not in response.text


@pytest.mark.parametrize("headers", [
    {},                                              # no key at all
    {"X-API-Key": ""},                               # an empty key
    {"X-API-Key": FAKE_KEY[:-1]},                    # one character short
    {"X-API-Key": FAKE_KEY + "x"},                   # one character too many
    {"X-API-Key": FAKE_KEY.upper()},                 # the right letters, wrong case
    {"Authorization": f"Bearer {FAKE_KEY}"},         # the right key in the wrong header
], ids=["missing", "empty", "shorter", "longer", "upper case", "wrong header"])
def test_without_exactly_the_right_key_the_answer_is_401(protected, headers):
    source = FakePriceSource()
    response = protected(source=source).post("/v1/forecast", json=GOOD, headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.headers["WWW-Authenticate"] == "ApiKey"
    assert FAKE_KEY not in response.text
    assert source.calls == [], "nothing is downloaded for a caller without the key"


def test_the_key_is_checked_before_the_request_body(protected):
    """A caller without the key learns nothing, not even what a valid body looks like."""
    response = protected().post("/v1/forecast", json={"tiker": "oops"})
    assert response.status_code == 401


def test_health_ready_and_model_info_need_no_key(protected):
    client = protected()
    for path in ("/v1/health", "/v1/ready", "/v1/model-info"):
        assert client.get(path).status_code == 200, path


def test_without_a_configured_key_the_forecast_is_open(client_factory, monkeypatch):
    monkeypatch.delenv("STOCKS_API_KEY", raising=False)
    assert client_factory().post("/v1/forecast", json=GOOD).status_code == 200


def test_a_key_that_reaches_a_log_line_is_masked(protected, caplog):
    """Even if something upstream repeats the key in an error, the log shows *** instead."""
    leaky = FakePriceSource(error=PriceSourceUnavailable(f"upstream echoed key={FAKE_KEY}"))
    with caplog.at_level(logging.INFO):
        response = protected(source=leaky).post("/v1/forecast", json=GOOD,
                                                headers={"X-API-Key": FAKE_KEY})

    assert response.status_code == 503
    assert "API key protection: on" in caplog.text
    assert "upstream echoed key=***" in caplog.text
    assert FAKE_KEY not in caplog.text


def test_the_docs_page_offers_an_authorize_button_for_the_key(protected):
    schemes = protected().get("/openapi.json").json()["components"]["securitySchemes"]
    assert schemes == {"APIKeyHeader": {"type": "apiKey", "in": "header", "name": "X-API-Key",
                                        "description": schemes["APIKeyHeader"]["description"]}}
