"""Entry point (web). The composition root of the service: the one place concrete classes meet.

    uvicorn stocks_service.api.app:create_app --factory
"""
import logging
import re
import time
import uuid
from collections.abc import Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from stocks_service.adapters.cached_prices import CachedPriceSource
from stocks_service.adapters.ridge_model import JoblibModelStore
from stocks_service.adapters.yahoo_prices import YahooPriceSource
from stocks_service.api.log_masking import install_secret_masking
from stocks_service.api.routes import router
from stocks_service.config import Settings
from stocks_service.domain.errors import NotEnoughHistory, PriceSourceUnavailable, UnknownTicker
from stocks_service.domain.features import FEATURE_NAMES
from stocks_service.domain.forecast import DISCLAIMER
from stocks_service.service.forecasting import ForecastService

log = logging.getLogger("stocks_service")
SAFE_TRACE_ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """The model loads HERE, once, when the service starts: visible, timed, failable."""
    settings = Settings.load()
    logging.basicConfig(level=settings.log_level)
    install_secret_masking([settings.api_key.get_secret_value()] if settings.api_key else [])
    if settings.api_key is None:
        log.warning("no API key configured: POST /v1/forecast is open to anyone who can reach it")
    else:
        log.info("API key protection: on")  # never the key itself
    app.state.settings = settings
    app.state.started_at = datetime.now(UTC)

    t0 = time.perf_counter()
    store = JoblibModelStore(settings.model_path, settings.meta_path)
    try:
        model = store.load()
        app.state.model_facts = store.facts()
    except FileNotFoundError as missing:  # fail fast, with a message a person can act on
        raise RuntimeError(f"No trained model at {missing.filename}. "
                           "Run: python -m stocks_service.cli train") from missing
    model.predict_move(dict.fromkeys(FEATURE_NAMES, 0.0))  # pay the first-call cost now
    prices = CachedPriceSource(YahooPriceSource(), keep_seconds=settings.price_cache_minutes * 60)
    app.state.forecaster = ForecastService(prices, model, settings.lookback_days)
    log.info("model loaded: version=%s ticker=%s seconds=%.3f",
             model.model_version, model.ticker, time.perf_counter() - t0)
    yield
    log.info("shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(title="Stocks Forecast Service", version="1.0.0", lifespan=lifespan,
                  description=DISCLAIMER + " Every forecast is shown next to the naive guess "
                                           '"tomorrow = today".')
    app.include_router(router, prefix="/v1")

    @app.middleware("http")
    async def trace_and_time(request: Request, call_next):
        # A caller may send its own trace id, but only a harmless-looking one is accepted:
        # it ends up in our logs and in the response.
        sent = request.headers.get("X-Trace-Id", "")
        trace_id = sent if SAFE_TRACE_ID.fullmatch(sent) else uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id
        t0 = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Trace-Id"] = trace_id
        response.headers["X-Response-Time-Ms"] = str(
            round((time.perf_counter() - t0) * 1000, 1))
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        # Field names and problems only: never echo the offending values back.
        details = [
            {"field": "body", "problem": "The body is not valid JSON"}
            if err["type"] == "json_invalid" else
            {"field": ".".join(str(part) for part in err["loc"][1:]) or "body",
             "problem": err["msg"]}
            for err in exc.errors()
        ]
        return _error(request, 422, "INVALID_REQUEST", "Request body failed validation",
                      details=details)

    @app.exception_handler(UnknownTicker)
    async def unknown_ticker(request: Request, exc: UnknownTicker):
        ticker = request.app.state.settings.ticker
        return _error(request, 404, "UNKNOWN_TICKER",
                      f"This model only knows {ticker}. It was never trained on another share.")

    @app.exception_handler(PriceSourceUnavailable)
    async def prices_unavailable(request: Request, exc: PriceSourceUnavailable):
        log.warning("price source unavailable trace_id=%s: %s", _trace_id(request), exc)
        return _error(request, 503, "PRICE_SOURCE_UNAVAILABLE",
                      "The price source sent no prices. Try again in a minute.",
                      headers={"Retry-After": "60"})

    @app.exception_handler(NotEnoughHistory)
    async def not_enough_prices(request: Request, exc: NotEnoughHistory):
        log.warning("not enough prices trace_id=%s: %s", _trace_id(request), exc)
        return _error(request, 503, "NOT_ENOUGH_PRICES",
                      "The price source sent too few trading days to build a forecast.",
                      headers={"Retry-After": "60"})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = {401: "UNAUTHORIZED", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED",
                503: "MODEL_UNAVAILABLE"}.get(exc.status_code, "HTTP_ERROR")
        return _error(request, exc.status_code, code, str(exc.detail), headers=exc.headers)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        # Never leak internals to callers; always give them a trace id to quote.
        log.error("unhandled exception trace_id=%s", _trace_id(request), exc_info=exc)
        return _error(request, 500, "INTERNAL_ERROR",
                      "Unexpected error; contact support with trace_id")

    return app


def _trace_id(request: Request) -> str:
    return getattr(request.state, "trace_id", "unknown")


def _error(request: Request, status: int, code: str, message: str,
           headers: Mapping[str, str] | None = None, **extra: object) -> JSONResponse:
    """One error shape for every failure: {"error": {code, message, trace_id}}."""
    trace_id = _trace_id(request)
    body = {"code": code, "message": message, "trace_id": trace_id, **extra}
    # The trace id is set here as well as in the middleware: after an unexpected crash the
    # middleware never gets the response back, and the caller still needs the id to quote.
    return JSONResponse(status_code=status, content={"error": body},
                        headers={**(headers or {}), "X-Trace-Id": trace_id})
