"""Adapter: the scikit-learn ridge regression, behind the model ports.

The only file that imports scikit-learn, pandas or joblib. Replacing the model means replacing
this file; nothing in domain/ or service/ changes.
"""
import json
from collections.abc import Sequence
from pathlib import Path

import joblib
import pandas as pd
import sklearn
from sklearn.linear_model import Ridge
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from stocks_service.domain.features import FEATURE_NAMES, Features, TrainingRow
from stocks_service.domain.forecast import Explanation


def _frame(many: Sequence[Features]) -> pd.DataFrame:
    """Inputs as a table whose columns are always in the model's order."""
    return pd.DataFrame([[features[name] for name in FEATURE_NAMES] for features in many],
                        columns=list(FEATURE_NAMES))


class RidgeForecastModel:
    """A weighted sum of the eight inputs: scale each input, multiply by its weight, add up."""

    def __init__(self, pipeline: Pipeline, model_version: str, ticker: str) -> None:
        self._pipeline = pipeline
        self.model_version = model_version
        self.ticker = ticker

    @property
    def pipeline(self) -> Pipeline:
        return self._pipeline

    def predict_move(self, features: Features) -> float:
        return float(self._pipeline.predict(_frame([features]))[0])

    def explain(self, features: Features) -> Explanation:
        scaler, ridge = self._pipeline[0], self._pipeline[-1]
        values = _frame([features]).to_numpy()[0]
        scaled = (values - scaler.mean_) / scaler.scale_  # each input against an average day
        pushes = ridge.coef_ * scaled                     # weight x how unusual today is
        return Explanation(start_move=float(ridge.intercept_),
                           pushes={name: float(push) for name, push in zip(FEATURE_NAMES, pushes)})

    def describe(self) -> dict[str, object]:
        return {"model_kind": "ridge regression on scaled inputs",
                "ridge_alpha": self._pipeline[-1].alpha,
                "sklearn_version": sklearn.__version__}


class RidgeTrainer:
    """Chooses how strongly the model is held back (alpha) inside the training years only,
    always learning on earlier days and checking on later ones."""

    def __init__(self, alphas: Sequence[float], model_version: str, ticker: str) -> None:
        self._alphas = list(alphas)
        self._model_version = model_version
        self._ticker = ticker

    def fit(self, rows: Sequence[TrainingRow]) -> RidgeForecastModel:
        search = GridSearchCV(
            make_pipeline(StandardScaler(), Ridge()),
            param_grid={"ridge__alpha": self._alphas},
            cv=TimeSeriesSplit(n_splits=5),
            scoring="neg_mean_absolute_error",
        )
        search.fit(_frame([row.features for row in rows]), [row.target for row in rows])
        return RidgeForecastModel(search.best_estimator_, self._model_version, self._ticker)


class JoblibModelStore:
    """Two files, as the notebook leaves them: the model, and a small facts file about it."""

    def __init__(self, model_path: Path, meta_path: Path) -> None:
        self._model_path = model_path
        self._meta_path = meta_path

    def save(self, model: RidgeForecastModel, facts: dict[str, object]) -> None:
        self._model_path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model.pipeline, self._model_path)
        self._meta_path.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")

    def facts(self) -> dict[str, object]:
        return json.loads(self._meta_path.read_text(encoding="utf-8"))

    def load(self) -> RidgeForecastModel:
        facts = self.facts()
        # A pickle: load it only from a path we control, with the versions that wrote it.
        pipeline = joblib.load(self._model_path)
        return RidgeForecastModel(pipeline, str(facts["model_version"]), str(facts["ticker"]))
