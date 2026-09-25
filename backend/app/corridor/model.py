"""
Mumbai-Goa Corridor - ML Model Training with SHAP Explainability

Trains a corridor-specific LightGBM with 15+ features (vs 4 for national).
Includes SHAP for per-prediction explanations.
"""
import logging
from ..config import settings
import numpy as np
import pandas as pd
import joblib
from pathlib import Path

logger = logging.getLogger(__name__)

# The configured processed-data directory is stable in both the repository
# layout and the Docker image. Deriving this from __file__ breaks after the
# backend package is copied from /backend into /app.
CORRIDOR_DATA_DIR = Path(settings.DATA_PROCESSED_DIR).parent / "corridor"
CORRIDOR_MODEL_DIR = CORRIDOR_DATA_DIR / "models"

CORRIDOR_FEATURES = [
    "distance_from_origin_km",
    "scheduled_running_time",
    "day_of_week",
    "is_weekend",
    "is_monsoon",
    "departure_hour",
    # Weather
    "rainfall_mm",
    "visibility_km",
    "weather_severity",
    # Section
    "is_single_track",
    "is_ghat_section",
    "tunnel_count",
    "bridge_count",
    "speed_limit",
    # Network
    "preceding_train_delay",
    # Train
    "is_premium",
    # Causal
    "previous_station_delay",
]

FEATURE_DISPLAY_NAMES = {
    "distance_from_origin_km": "Distance from origin",
    "scheduled_running_time": "Scheduled running time",
    "day_of_week": "Day of week",
    "is_weekend": "Weekend",
    "is_monsoon": "Monsoon season",
    "departure_hour": "Departure hour",
    "rainfall_mm": "Rainfall",
    "visibility_km": "Visibility",
    "weather_severity": "Weather severity",
    "is_single_track": "Single-track section",
    "is_ghat_section": "Ghat/mountain section",
    "tunnel_count": "Tunnels in section",
    "bridge_count": "Bridges in section",
    "speed_limit": "Section speed limit",
    "preceding_train_delay": "Train ahead delay",
    "is_premium": "Premium train",
    "previous_station_delay": "Delay at previous station",
}


class CorridorForecaster:
    """
    Corridor-specific LightGBM forecaster with SHAP explainability.
    """

    def __init__(self):
        self.model = None
        self.q10_model = None
        self.q90_model = None
        self.explainer = None
        self._load_models()

    def _load_models(self):
        """Load trained models if they exist."""
        CORRIDOR_MODEL_DIR.mkdir(parents=True, exist_ok=True)

        point_path = CORRIDOR_MODEL_DIR / "corridor_point.joblib"
        q10_path = CORRIDOR_MODEL_DIR / "corridor_q10.joblib"
        q90_path = CORRIDOR_MODEL_DIR / "corridor_q90.joblib"

        try:
            if point_path.exists():
                self.model = joblib.load(point_path)
                logger.info("Loaded corridor point model")
            if q10_path.exists():
                self.q10_model = joblib.load(q10_path)
                logger.info("Loaded corridor Q10 model")
            if q90_path.exists():
                self.q90_model = joblib.load(q90_path)
                logger.info("Loaded corridor Q90 model")
        except Exception as e:
            logger.warning("Could not load corridor models: %s", e)

    def predict(self, features: dict) -> dict:
        """
        Predict delay with full explanation.

        Returns:
            {
                "predicted_delay": float,
                "lower_bound": float,
                "upper_bound": float,
                "explanations": [{"feature": ..., "display_name": ..., "value": ..., "contribution": ..., "direction": ...}]
            }
        """
        feature_values = {k: features.get(k, 0) for k in CORRIDOR_FEATURES}
        df = pd.DataFrame([feature_values])

        if self.model is None:
            return self._fallback_predict(features)

        point = float(self.model.predict(df)[0])
        q10 = float(self.q10_model.predict(df)[0]) if self.q10_model else point - 5
        q90 = float(self.q90_model.predict(df)[0]) if self.q90_model else point + 5

        # SHAP explanations
        explanations = self._explain(df)

        return {
            "predicted_delay": round(point, 1),
            "lower_bound": round(q10, 1),
            "upper_bound": round(q90, 1),
            "explanations": explanations,
        }

    def _explain(self, df: pd.DataFrame) -> list[dict]:
        """Generate SHAP-based explanations for a prediction."""
        try:
            if self.explainer is None:
                import shap
                self.explainer = shap.TreeExplainer(self.model)

            shap_values = self.explainer.shap_values(df)

            if isinstance(shap_values, list):
                shap_values = shap_values[0]

            explanations = []
            for i, feat in enumerate(CORRIDOR_FEATURES):
                val = float(df.iloc[0][feat])
                contrib = float(shap_values[0][i]) if len(shap_values.shape) > 1 else float(shap_values[i])

                if abs(contrib) < 0.3:
                    continue  # Skip negligible contributions

                explanations.append({
                    "feature": feat,
                    "display_name": FEATURE_DISPLAY_NAMES.get(feat, feat),
                    "value": val,
                    "contribution_minutes": round(contrib, 1),
                    "direction": "INCREASING" if contrib > 0 else "DECREASING",
                    "icon": self._get_icon(feat, contrib),
                    "description": self._get_description(feat, val, contrib),
                })

            # Sort by absolute contribution
            explanations.sort(key=lambda x: abs(x["contribution_minutes"]), reverse=True)
            return explanations

        except Exception as e:
            logger.warning("SHAP explanation failed: %s", e)
            return self._manual_explanations(df)

    def _manual_explanations(self, df: pd.DataFrame) -> list[dict]:
        """Fallback: use feature importance + values for explanations."""
        if not self.model or not hasattr(self.model, "feature_importances_"):
            return []

        importances = self.model.feature_importances_
        total = sum(importances) or 1
        prediction = float(self.model.predict(df)[0])

        explanations = []
        for i, feat in enumerate(CORRIDOR_FEATURES):
            val = float(df.iloc[0][feat])
            imp_pct = importances[i] / total
            estimated_contrib = prediction * imp_pct

            if abs(estimated_contrib) < 0.3:
                continue

            explanations.append({
                "feature": feat,
                "display_name": FEATURE_DISPLAY_NAMES.get(feat, feat),
                "value": val,
                "contribution_minutes": round(estimated_contrib, 1),
                "direction": "INCREASING" if estimated_contrib > 0 else "DECREASING",
                "icon": self._get_icon(feat, estimated_contrib),
                "description": self._get_description(feat, val, estimated_contrib),
            })

        explanations.sort(key=lambda x: abs(x["contribution_minutes"]), reverse=True)
        return explanations

    def _get_icon(self, feature: str, contribution: float) -> str:
        """Get an emoji icon for the feature."""
        icons = {
            "rainfall_mm": "rain",
            "visibility_km": "fog",
            "weather_severity": "cloud",
            "preceding_train_delay": "train",
            "is_ghat_section": "mountain",
            "is_single_track": "track",
            "tunnel_count": "tunnel",
            "bridge_count": "bridge",
            "previous_station_delay": "clock",
            "is_monsoon": "rain",
            "is_premium": "star",
            "speed_limit": "speed",
        }
        return icons.get(feature, "info")

    def _get_description(self, feature: str, value: float, contribution: float) -> str:
        """Generate human-readable description for the explanation."""
        direction = "adding" if contribution > 0 else "reducing"
        mins = abs(contribution)

        if feature == "rainfall_mm":
            if value > 30:
                return f"Heavy rainfall ({value:.0f}mm/hr) {direction} ~{mins:.1f}m delay"
            elif value > 10:
                return f"Moderate rain ({value:.0f}mm/hr) {direction} ~{mins:.1f}m delay"
            elif value > 0:
                return f"Light rain ({value:.1f}mm/hr) {direction} ~{mins:.1f}m delay"
            return f"No rain - {direction} ~{mins:.1f}m"

        if feature == "preceding_train_delay":
            if value > 0:
                return f"Train ahead is {value:.0f}m late - {direction} ~{mins:.1f}m delay"
            return f"No train delay ahead - {direction} ~{mins:.1f}m"

        if feature == "is_ghat_section":
            if value > 0:
                return f"Ghat mountain section - {direction} ~{mins:.1f}m delay"
            return f"Non-ghat section - {direction} ~{mins:.1f}m"

        if feature == "is_single_track":
            if value > 0:
                return f"Single-track section (crossing delays possible) - {direction} ~{mins:.1f}m"
            return f"Double-track section - {direction} ~{mins:.1f}m"

        if feature == "previous_station_delay":
            return f"Arrived {value:.0f}m late at previous station - {direction} ~{mins:.1f}m"

        if feature == "weather_severity":
            return f"Weather severity score {value:.2f} - {direction} ~{mins:.1f}m"

        if feature == "visibility_km":
            return f"Visibility {value:.1f}km - {direction} ~{mins:.1f}m"

        if feature == "is_monsoon":
            return f"{'Monsoon' if value else 'Non-monsoon'} season - {direction} ~{mins:.1f}m"

        if feature == "tunnel_count":
            return f"{int(value)} tunnels in section - {direction} ~{mins:.1f}m"

        return f"{FEATURE_DISPLAY_NAMES.get(feature, feature)}: {value} - {direction} ~{mins:.1f}m"

    def _fallback_predict(self, features: dict) -> dict:
        """Simple rule-based prediction when no model is loaded."""
        base = features.get("previous_station_delay", 0)
        rain = features.get("rainfall_mm", 0)
        ghat = features.get("is_ghat_section", 0)
        preceding = features.get("preceding_train_delay", 0)

        predicted = base + rain * 0.2 + ghat * 3 + preceding * 0.3
        return {
            "predicted_delay": round(predicted, 1),
            "lower_bound": round(predicted - 5, 1),
            "upper_bound": round(predicted + 8, 1),
            "explanations": [],
        }

    def get_model_info(self) -> dict:
        return {
            "model_loaded": self.model is not None,
            "q10_loaded": self.q10_model is not None,
            "q90_loaded": self.q90_model is not None,
            "features": CORRIDOR_FEATURES,
            "feature_count": len(CORRIDOR_FEATURES),
        }
