import logging
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ..config import settings
from ..models.domain import DataQuality, Prediction, PredictionMode

logger = logging.getLogger(__name__)
IST = ZoneInfo(settings.TIMEZONE)


class SynapseForecaster:
    """
    LightGBM-based forecaster for Synapse.
    Provides point and quantile predictions for train delays.

    Loads 3 models:
      - Point prediction (regression)
      - Q10 quantile (lower bound of 80% PI)
      - Q90 quantile (upper bound of 80% PI)
    """

    # Features the LightGBM model was trained on (from ml/train_model.py)
    TRAINED_FEATURES = [
        "distance_from_origin_km",
        "previous_station_delay",
        "day_of_week",
        "scheduled_running_time",
    ]

    def __init__(self, model_path: str = None, q10_path: str = None, q90_path: str = None):
        self.model_version = settings.MODEL_VERSION
        self.model = None
        self.q10_model = None
        self.q90_model = None

        try:
            import joblib

            if model_path and Path(model_path).exists():
                logger.info("Loading point model from %s", model_path)
                self.model = joblib.load(model_path)

            if q10_path and Path(q10_path).exists():
                logger.info("Loading Q10 model from %s", q10_path)
                self.q10_model = joblib.load(q10_path)

            if q90_path and Path(q90_path).exists():
                logger.info("Loading Q90 model from %s", q90_path)
                self.q90_model = joblib.load(q90_path)

        except Exception as e:
            logger.warning("Could not load model(s), using fallback: %s", e)

    def _make_feature_df(self, features: dict):
        """Build a single-row DataFrame with exactly the trained feature columns."""
        import pandas as pd
        model_features = {k: features.get(k, 0) for k in self.TRAINED_FEATURES}
        return pd.DataFrame([model_features])

    def predict_delay(self, features: dict) -> float:
        """Point prediction of delay in minutes."""
        if self.model:
            df = self._make_feature_df(features)
            return float(self.model.predict(df)[0])

        # Stub prediction when no model is loaded
        base = features.get("current_delay_minutes", 0) or features.get("previous_station_delay", 0)
        return float(base + features.get("preceding_train_delay", 0) * 0.1)

    def predict_quantiles(self, features: dict) -> tuple[float, float, float]:
        """Returns (q10, q50, q90) for uncertainty intervals."""
        point = self.predict_delay(features)

        if self.q10_model and self.q90_model:
            df = self._make_feature_df(features)
            q10 = float(self.q10_model.predict(df)[0])
            q90 = float(self.q90_model.predict(df)[0])
            return (q10, point, q90)

        # Fallback: heuristic spread
        spread = 5.0 + abs(point) * 0.1
        return (point - spread, point, point + spread)

    def predict_full(
        self,
        train_id: str,
        station_code: str,
        station_no: int,
        features: dict,
        scheduled_arrival: datetime,
        data_quality: DataQuality = DataQuality.FULL,
        prediction_mode: PredictionMode = PredictionMode.LIVE,
    ) -> Prediction:
        """Returns a full Prediction domain object."""

        if data_quality == DataQuality.FALLBACK:
            pred_delay = features.get("current_delay_minutes", 0.0)
            q10, q50, q90 = pred_delay, pred_delay, pred_delay
        else:
            pred_delay = self.predict_delay(features)
            q10, q50, q90 = self.predict_quantiles(features)

        predicted_arrival = scheduled_arrival + timedelta(minutes=pred_delay)
        lower = scheduled_arrival + timedelta(minutes=q10)
        upper = scheduled_arrival + timedelta(minutes=q90)

        return Prediction(
            train_id=train_id,
            generated_at=datetime.now(IST),
            model_version=self.model_version,
            station_code=station_code,
            station_no=station_no,
            predicted_arrival=predicted_arrival,
            predicted_delay_minutes=pred_delay,
            lower_bound=lower,
            upper_bound=upper,
            prediction_interval_minutes=q90 - q10,
            data_quality=data_quality,
            prediction_mode=prediction_mode,
        )

    def get_feature_importance(self) -> dict[str, float]:
        """Returns feature importance from the trained model."""
        if self.model and hasattr(self.model, "feature_importances_"):
            names = (
                self.model.feature_name_
                if hasattr(self.model, "feature_name_")
                else self.TRAINED_FEATURES
            )
            return {str(n): int(v) for n, v in zip(names, self.model.feature_importances_)}

        return {
            "distance_from_origin_km": 2163,
            "previous_station_delay": 2041,
            "day_of_week": 333,
            "scheduled_running_time": 2345,
        }

    def get_model_info(self) -> dict:
        """Model metadata for the evaluation API."""
        return {
            "version": self.model_version,
            "point_model_loaded": self.model is not None,
            "q10_model_loaded": self.q10_model is not None,
            "q90_model_loaded": self.q90_model is not None,
            "trained_features": self.TRAINED_FEATURES,
            "feature_importance": self.get_feature_importance(),
        }
