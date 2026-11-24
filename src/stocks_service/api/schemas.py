"""The HTTP contract: the exact shape of a request and of a response.

Anything that does not match the request shape is rejected with a 422 before it reaches the
service. The response shape is also what the /docs page shows.
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from stocks_service.domain.forecast import Forecast


class ForecastRequest(BaseModel):
    # Unknown fields are an error, not noise: a typo like "tiker" must not pass silently.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    ticker: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.]+$",
                        examples=["2222.SR"],
                        description="Yahoo Finance symbol. This model only knows 2222.SR.")


class ReasonOut(BaseModel):
    input: str = Field(examples=["move two days ago"])
    value: str = Field(examples=["+1.87%"])
    push_halalas: float = Field(description="How far this input pushed the forecast, "
                                            "up (+) or down (-).", examples=[-1.2])


class ForecastResponse(BaseModel):
    ticker: str
    as_of: date = Field(description="The day of the latest closing price used.")
    last_close_sar: float
    forecast_close_sar: float = Field(description="The model's guess for the next trading day.")
    naive_close_sar: float = Field(description='The simple guess "tomorrow = today".')
    change_halalas: float = Field(description="Model forecast minus last close.")
    top_reasons: list[ReasonOut]
    model_version: str
    model_vs_naive_pct: float = Field(
        description="On the model's test year: its average error against the naive guess. "
                    "Negative = the model is worse.")
    disclaimer: str
    trace_id: str

    @classmethod
    def from_domain(cls, forecast: Forecast, top: int, model_vs_naive_pct: float,
                    trace_id: str) -> "ForecastResponse":
        return cls(
            ticker=forecast.ticker,
            as_of=forecast.as_of,
            last_close_sar=round(forecast.last_close, 2),
            forecast_close_sar=round(forecast.forecast_close, 3),
            naive_close_sar=round(forecast.naive_close, 2),
            change_halalas=round(forecast.change_halalas, 2),
            top_reasons=[ReasonOut(input=reason.label, value=reason.value_text,
                                   push_halalas=round(reason.push_halalas, 2))
                         for reason in forecast.reasons[:top]],
            model_version=forecast.model_version,
            model_vs_naive_pct=model_vs_naive_pct,
            disclaimer=forecast.disclaimer,
            trace_id=trace_id,
        )


class HealthResponse(BaseModel):
    status: str
    git_sha: str
    started_at: datetime
