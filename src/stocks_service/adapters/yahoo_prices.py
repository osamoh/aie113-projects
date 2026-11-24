"""Adapter: daily prices from Yahoo Finance, behind the PriceSource port.

The only file that knows about Yahoo. A paid, licensed data feed tomorrow means one new file
next to this one; nothing in domain/ or service/ changes.
"""
import time
from datetime import date

import yfinance as yf

from stocks_service.domain.errors import PriceSourceUnavailable
from stocks_service.domain.prices import PriceHistory, PricePoint


class YahooPriceSource:
    def __init__(self, retry_wait_seconds: float = 10.0) -> None:
        self._retry_wait = retry_wait_seconds

    def history(self, ticker: str, start: date, end: date) -> PriceHistory:
        raw = self._download(ticker, start, end)
        raw.index = raw.index.tz_localize(None)  # Yahoo gives Riyadh time; we only need the date
        # Zero volume with a flat price = a day Yahoo recorded no trading. Drop it, as the
        # notebook does. We keep only the closing price.
        kept = raw.loc[raw["Volume"] > 0, "Close"].dropna()
        return PriceHistory(ticker, tuple(
            PricePoint(day=stamp.date(), close=float(close)) for stamp, close in kept.items()))

    def _download(self, ticker: str, start: date, end: date):
        problem = "no rows came back"
        for attempt in (1, 2):  # Yahoo sometimes refuses a request: try twice
            try:
                raw = yf.Ticker(ticker).history(start=start.isoformat(), end=end.isoformat(),
                                                auto_adjust=False)
                if len(raw) > 0:
                    return raw
            except Exception as error:  # noqa: BLE001 - yfinance raises many kinds
                problem = f"{type(error).__name__}: {error}"
            if attempt == 1:
                time.sleep(self._retry_wait)
        raise PriceSourceUnavailable(
            f"Yahoo Finance sent no prices for {ticker} ({start} to {end}): {problem}")
