"""The use case: forecast the next trading day's close for one share."""
from datetime import date, timedelta

from stocks_service.domain.errors import UnknownTicker
from stocks_service.domain.features import latest_features
from stocks_service.domain.forecast import Forecast, make_forecast
from stocks_service.domain.prices import PriceHistory
from stocks_service.service.interfaces import ForecastModel, PriceSource


class ForecastService:
    def __init__(self, prices: PriceSource, model: ForecastModel, lookback_days: int = 90) -> None:
        self._prices = prices
        self._model = model
        self._lookback = timedelta(days=lookback_days)  # calendar days fetched before as_of

    def forecast(self, ticker: str, as_of: date) -> Forecast:
        """Fetch the prices known on the evening of `as_of`, then forecast the next day."""
        self._check_ticker(ticker)
        history = self._prices.history(ticker, start=as_of - self._lookback,
                                       end=as_of + timedelta(days=1))
        return self.forecast_from(history)

    def forecast_from(self, history: PriceHistory) -> Forecast:
        """Forecast from prices we already hold. No download, so it is easy to check."""
        self._check_ticker(history.ticker)
        features = latest_features(history)  # raises NotEnoughHistory when too short
        latest = history.points[-1]
        return make_forecast(
            ticker=history.ticker, as_of=latest.day, last_close=latest.close,
            features=features,
            predicted_move=self._model.predict_move(features),
            explanation=self._model.explain(features),
            model_version=self._model.model_version,
        )

    def _check_ticker(self, ticker: str) -> None:
        if ticker != self._model.ticker:
            raise UnknownTicker(
                f"this model only knows {self._model.ticker}; it was never trained on {ticker}")
