"""All configuration in ONE place. Nothing else in the codebase reads the environment.

Every value can be overridden with an environment variable that starts with STOCKS_, for
example STOCKS_END_DATE=2026-12-01. The defaults are the notebook's fixed settings, so
everyone gets the same numbers.
"""
from datetime import date
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STOCKS_", env_file=".env")

    ticker: str = "2222.SR"               # Saudi Aramco on Tadawul (Yahoo Finance symbol)
    start_date: date = date(2021, 11, 1)  # about five years of history
    end_date: date = date(2026, 11, 1)    # prices up to the day before this date
    test_start: date = date(2025, 11, 1)  # the last 12 months are kept for the final test
    alphas: tuple[float, ...] = (0.1, 1, 10, 100, 1000, 3000, 10000)
    model_version: str = "stocks-ridge-1.0.0"
    model_path: Path = Path("artifacts/model.joblib")
    meta_path: Path = Path("artifacts/model_meta.json")
    lookback_days: int = 90               # calendar days of prices fetched for one forecast
