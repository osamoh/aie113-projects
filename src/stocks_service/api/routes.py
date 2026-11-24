from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from stocks_service.api.schemas import ForecastRequest, ForecastResponse, HealthResponse
from stocks_service.domain.market import latest_complete_day
from stocks_service.service.forecasting import ForecastService

router = APIRouter()


def get_forecaster(request: Request) -> ForecastService:
    """The seam for tests: they replace this one function to put in a fake model or source."""
    forecaster = getattr(request.app.state, "forecaster", None)
    if forecaster is None:  # start-up is not finished, or it failed
        raise HTTPException(status_code=503, detail="Model not ready",
                            headers={"Retry-After": "5"})
    return forecaster


def get_now() -> datetime:
    """The clock, as a replaceable function, so a test can ask "what if it were 10 am?"."""
    return datetime.now(UTC)


@router.post("/forecast", response_model=ForecastResponse)
def forecast(body: ForecastRequest, request: Request, response: Response,
             forecaster: Annotated[ForecastService, Depends(get_forecaster)],
             now: Annotated[datetime, Depends(get_now)]):
    # Plain `def`: the price download blocks, so FastAPI runs this in a worker thread.
    result = forecaster.forecast(body.ticker.upper(), as_of=latest_complete_day(now))
    response.headers["X-Model-Version"] = result.model_version
    settings, facts = request.app.state.settings, request.app.state.model_facts
    return ForecastResponse.from_domain(
        result, top=settings.top_reasons,
        model_vs_naive_pct=facts["metrics_test"]["mae_improvement_vs_naive_pct"],
        trace_id=request.state.trace_id)


@router.get("/model-info")
def model_info(request: Request):
    """The model's facts file: version, inputs, training dates, test numbers and baseline."""
    facts = getattr(request.app.state, "model_facts", None)
    if facts is None:
        raise HTTPException(status_code=503, detail="Model not ready",
                            headers={"Retry-After": "5"})
    return facts


@router.get("/health", response_model=HealthResponse)
def health(request: Request):
    """Liveness: the process is up. It checks nothing else and downloads nothing."""
    return HealthResponse(status="ok", git_sha=request.app.state.settings.git_sha,
                          started_at=request.app.state.started_at)


@router.get("/ready")
def ready(request: Request):
    """Readiness: safe to receive requests, because the model is loaded.

    It does NOT call the price source: a slow or failing third party must not make the whole
    service look dead. A price-source failure is reported per request instead (503)."""
    if getattr(request.app.state, "forecaster", None) is None:
        raise HTTPException(status_code=503, detail="warming up", headers={"Retry-After": "5"})
    return {"status": "ready", "checked_at": datetime.now(UTC)}
