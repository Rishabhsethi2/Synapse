import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import settings
from ..models.domain import WhatIfScenario

logger = logging.getLogger(__name__)
IST = ZoneInfo(settings.TIMEZONE)

# Default feature template matching the trained LightGBM model's expected features
DEFAULT_FEATURES = {
    "distance_from_origin_km": 500.0,
    "previous_station_delay": 0.0,
    "day_of_week": 3,
    "scheduled_running_time": 120.0,
}


class WhatIfEngine:
    """
    Simulates counterfactual scenarios to see how ETA would change
    under different operational conditions.
    """

    METHODOLOGY = "COUNTERFACTUAL_SIMULATION - NOT A GUARANTEED PREDICTION"

    def run_scenario(
        self,
        train_id: str,
        modifications: dict,
        forecaster,
        feature_engine,
        schedule_arrival: datetime,
    ) -> WhatIfScenario:
        """
        Runs a simulation by modifying features and comparing predictions.
        """
        # 1. Get current features (falls back to defaults if train not tracked)
        if hasattr(feature_engine, "get_current_features"):
            current_features = feature_engine.get_current_features(train_id)
        else:
            current_features = {}

        # Ensure we always have the features the model expects
        for k, v in DEFAULT_FEATURES.items():
            if k not in current_features:
                current_features[k] = v

        # 2. Baseline prediction
        baseline_pred = forecaster.predict_delay(current_features)

        # 3. Apply modifications
        counterfactual_features = current_features.copy()

        # Map user-friendly modification keys to model features
        if "add_delay_minutes" in modifications:
            counterfactual_features["previous_station_delay"] = (
                current_features.get("previous_station_delay", 0)
                + modifications["add_delay_minutes"]
            )
        if "speed_restriction_kmh" in modifications:
            # Slower speed -> more running time
            counterfactual_features["scheduled_running_time"] = (
                current_features.get("scheduled_running_time", 120.0) * 1.5
            )
        # Also apply direct feature overrides
        for k, v in modifications.items():
            if k in DEFAULT_FEATURES:
                counterfactual_features[k] = v

        # 4. Counterfactual prediction
        cf_pred = forecaster.predict_delay(counterfactual_features)

        # 5. Deltas
        delta = cf_pred - baseline_pred

        return WhatIfScenario(
            scenario_id=str(uuid.uuid4()),
            train_id=train_id,
            created_at=datetime.now(IST),
            modifications=modifications,
            baseline_prediction={"predicted_delay_minutes": float(baseline_pred)},
            counterfactual_prediction={"predicted_delay_minutes": float(cf_pred)},
            delta_minutes={"total_change": float(delta)},
            methodology=self.METHODOLOGY,
        )
