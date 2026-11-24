"""Smoke test: does the CONTAINER really start and answer?

Run it against a running container:

    docker compose up --build -d
    pytest -m smoke                       # or: SMOKE_URL=http://host:port pytest -m smoke

It only proves the packed service is alive and behaves like our service. A forecast needs the
price source, which may be down through no fault of ours, so both honest outcomes are accepted:
a forecast, or our own clear "price source unavailable" error. A crash is never accepted.
"""
import os

import httpx
import pytest

pytestmark = pytest.mark.smoke

URL = os.environ.get("SMOKE_URL", "http://localhost:8000")


@pytest.fixture(scope="module")
def service():
    # trust_env=False: talk to the container directly, never through a proxy.
    with httpx.Client(base_url=URL, timeout=30, trust_env=False) as client:
        yield client


def test_the_container_is_ready_and_says_which_code_it_runs(service):
    assert service.get("/v1/ready").json()["status"] == "ready"
    assert service.get("/v1/health").json()["git_sha"]


def test_the_model_inside_is_ours(service):
    facts = service.get("/v1/model-info").json()
    assert facts["ticker"] == "2222.SR"
    assert "naive_baseline" in facts["metrics_test"]


def test_a_bad_request_gets_our_error_shape(service):
    response = service.post("/v1/forecast", json={"tiker": "2222.SR"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_a_forecast_request_gets_an_answer_or_our_own_clear_error(service):
    response = service.post("/v1/forecast", json={"ticker": "2222.SR"})

    if response.status_code == 200:
        body = response.json()
        assert body["naive_close_sar"] == body["last_close_sar"] > 0
        assert body["disclaimer"]
    else:
        assert response.status_code == 503, response.text
        assert response.json()["error"]["code"] in {"PRICE_SOURCE_UNAVAILABLE",
                                                    "NOT_ENOUGH_PRICES"}
