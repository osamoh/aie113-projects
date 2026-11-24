"""Adapter: a short memory in front of any price source.

The price source can refuse us when we ask too often (Yahoo did, on our first day). Closing
prices of finished days do not change within minutes, so the same question asked again soon
is answered from memory instead of with a new download.
"""
import threading
import time
from collections.abc import Callable
from datetime import date

from stocks_service.domain.prices import PriceHistory
from stocks_service.service.interfaces import PriceSource


class CachedPriceSource:
    def __init__(self, inner: PriceSource, keep_seconds: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._inner = inner
        self._keep_seconds = keep_seconds
        self._clock = clock
        self._lock = threading.Lock()  # requests run in several threads at once
        self._memory: dict[tuple[str, date, date], tuple[float, PriceHistory]] = {}

    def history(self, ticker: str, start: date, end: date) -> PriceHistory:
        key = (ticker, start, end)
        with self._lock:
            remembered = self._memory.get(key)
            if remembered and remembered[0] > self._clock():
                return remembered[1]
        fresh = self._inner.history(ticker, start, end)  # a failure is never remembered
        with self._lock:
            self._memory = {k: v for k, v in self._memory.items() if v[0] > self._clock()}
            self._memory[key] = (self._clock() + self._keep_seconds, fresh)
        return fresh
