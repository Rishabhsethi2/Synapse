"""
Synapse - Intelligence API Routes (What-If)
"""
from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime
from zoneinfo import ZoneInfo

from ..dependencies import (
    whatif_engine, synapse_forecaster, feature_engine,
    propagation_estimator, network_state_engine, train_state_engine,
)
from ..config import settings

router = APIRouter(tags=["intelligence"])
IST = ZoneInfo(settings.TIMEZONE)


class WhatIfRequest(BaseModel):
    train_id: str
    modifications: dict


@router.post("/whatif")
def run_whatif_scenario(request: WhatIfRequest):
    """Run a counterfactual what-if simulation."""
    scenario = whatif_engine.run_scenario(
        train_id=request.train_id,
        modifications=request.modifications,
        forecaster=synapse_forecaster,
        feature_engine=feature_engine,
        schedule_arrival=datetime.now(IST),
    )
    return scenario.model_dump()


@router.get("/propagation/{train_id}")
def get_delay_propagation(train_id: str, delay_minutes: float = 30):
    """Estimate downstream delay propagation from a train."""
    entry = train_state_engine.get_train(train_id)

    if entry is None:
        # Use a default section for estimation
        return {
            "train_id": train_id,
            "impacts": [],
            "message": "Train not currently tracked. Start a replay first.",
        }

    # Find the current section
    remaining = entry.remaining_stations
    if remaining:
        section_id = f"{entry.current_station_code}->{remaining[0]}"
    else:
        return {
            "train_id": train_id,
            "impacts": [],
            "message": "Train has completed its journey.",
        }

    impacts = propagation_estimator.estimate_impact(
        source_train_id=train_id,
        source_delay_minutes=delay_minutes,
        section_id=section_id,
        network_state_engine=network_state_engine,
    )

    return {
        "train_id": train_id,
        "source_delay_minutes": delay_minutes,
        "section_id": section_id,
        "impacts": impacts,
        "methodology": propagation_estimator.METHODOLOGY,
    }


@router.get("/model/info")
def get_model_info():
    """Model metadata, feature importance, and loaded state."""
    return synapse_forecaster.get_model_info()


@router.get("/model/evaluate")
def get_model_evaluation():
    """
    Returns pre-computed evaluation metrics from the test set.
    These are the metrics from the ML training pipeline (ml/train_model.py).
    """
    from pathlib import Path
    from ..config import settings

    processed_dir = Path(settings.DATA_PROCESSED_DIR)
    test_file = processed_dir / "test.parquet"

    if not test_file.exists():
        return {
            "error": "Test data not found. Run 'python ml/process_data.py' first.",
            "status": "no_data",
        }

    import pandas as pd
    import numpy as np

    test_df = pd.read_parquet(test_file)
    features = synapse_forecaster.TRAINED_FEATURES
    X_test = test_df[features]
    y_test = test_df["delay_minutes"]

    # Run predictions
    preds = []
    q10_preds = []
    q90_preds = []

    # Batch predict in chunks for performance
    chunk_size = 50_000
    for i in range(0, len(X_test), chunk_size):
        chunk = X_test.iloc[i:i + chunk_size]

        if synapse_forecaster.model:
            preds.extend(synapse_forecaster.model.predict(chunk).tolist())
        if synapse_forecaster.q10_model:
            q10_preds.extend(synapse_forecaster.q10_model.predict(chunk).tolist())
        if synapse_forecaster.q90_model:
            q90_preds.extend(synapse_forecaster.q90_model.predict(chunk).tolist())

    if not preds:
        return {"error": "No model loaded", "status": "no_model"}

    preds = np.array(preds)
    y = y_test.values

    mae = float(np.mean(np.abs(y - preds)))
    rmse = float(np.sqrt(np.mean((y - preds) ** 2)))
    median_ae = float(np.median(np.abs(y - preds)))

    result = {
        "test_samples": len(y_test),
        "mae_minutes": round(mae, 2),
        "rmse_minutes": round(rmse, 2),
        "median_ae_minutes": round(median_ae, 2),
        "model_version": synapse_forecaster.model_version,
        "feature_importance": synapse_forecaster.get_feature_importance(),
    }

    if q10_preds and q90_preds:
        q10 = np.array(q10_preds)
        q90 = np.array(q90_preds)
        covered = ((y >= q10) & (y <= q90)).sum()
        result["pi_coverage_80"] = round(float(covered / len(y) * 100), 1)
        result["avg_interval_width"] = round(float(np.mean(q90 - q10)), 1)

    return result
