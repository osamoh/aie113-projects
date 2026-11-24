"""All configuration in ONE place. Nothing else in the codebase reads the environment.

Every value can be overridden with an environment variable that starts with STOCKS_, for
example STOCKS_END_DATE=2026-12-01. The defaults are the notebook's fixed settings, so
everyone gets the same numbers.
"""
from datetime import date
from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Where Docker and Kubernetes put secrets: one small file per secret, not an environment
# variable (environment variables show up in `docker inspect` and in crash reports).
SECRETS_DIR = Path("/run/secrets")
MIN_API_KEY_LENGTH = 24


class Settings(BaseSettings):
    # extra="ignore": a .env file may hold other programs' variables. Without it, one unknown
    # line stops the service AND the error message prints that line's value, secret or not.
    # hide_input_in_errors: when a value is refused at start-up, the error names the setting
    # but never prints the value, which may be a secret.
    model_config = SettingsConfigDict(env_prefix="STOCKS_", env_file=".env", extra="ignore",
                                      hide_input_in_errors=True)

    ticker: str = "2222.SR"               # Saudi Aramco on Tadawul (Yahoo Finance symbol)
    start_date: date = date(2021, 11, 1)  # about five years of history
    end_date: date = date(2026, 11, 1)    # prices up to the day before this date
    test_start: date = date(2025, 11, 1)  # the last 12 months are kept for the final test
    alphas: tuple[float, ...] = (0.1, 1, 10, 100, 1000, 3000, 10000)
    model_version: str = "stocks-ridge-1.0.0"
    # The model lives in git and inside the image: small files, reviewed like code.
    model_path: Path = Path("models/model.joblib")
    meta_path: Path = Path("models/model_meta.json")
    lookback_days: int = 90               # calendar days of prices fetched for one forecast
    price_cache_minutes: float = 15       # how long downloaded prices are remembered
    top_reasons: int = 3                  # how many reasons the API shows with a forecast
    log_level: str = "INFO"
    git_sha: str = "dev"                  # which version of the code is running

    # The one secret: the key callers must send in the X-API-Key header to get a forecast.
    # Read from the file /run/secrets/stocks_api_key, or from STOCKS_API_KEY. SecretStr means
    # printing the settings shows ********** instead of the value. None = not protected.
    api_key: SecretStr | None = None

    @field_validator("api_key", mode="before")
    @classmethod
    def _empty_means_no_key(cls, value: object) -> object:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("api_key")
    @classmethod
    def _long_enough(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None and len(value.get_secret_value()) < MIN_API_KEY_LENGTH:
            # The message never contains the value itself.
            raise ValueError(f"api_key must be at least {MIN_API_KEY_LENGTH} characters long")
        return value

    @classmethod
    def load(cls) -> "Settings":
        """Settings from the environment, .env and, inside a container, the secret files."""
        return cls(_secrets_dir=SECRETS_DIR if SECRETS_DIR.is_dir() else None)
