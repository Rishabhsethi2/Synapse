"""
Mumbai-Goa Corridor — ML Training Pipeline

Generates corridor training data, trains LightGBM (point + quantile),
and saves models with SHAP-ready output.
"""
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

CORRIDOR_DATA_DIR = Path(__file__).parent.parent / "data" / "corridor"
MODEL_DIR = CORRIDOR_DATA_DIR / "models"

FEATURES = [
    "distance_from_origin_km",
    "scheduled_running_time",
    "day_of_week",
    "is_weekend",
    "is_monsoon",
    "departure_hour",
    "rainfall_mm",
    "visibility_km",
    "weather_severity",
    "is_single_track",
    "is_ghat_section",
    "tunnel_count",
    "bridge_count",
    "speed_limit",
    "preceding_train_delay",
    "is_premium",
    "previous_station_delay",
]

TARGET = "delay_minutes"


def main():
    logger.info("=" * 60)
    logger.info("CORRIDOR ML TRAINING PIPELINE")
    logger.info("=" * 60)

    # Step 1: Generate data
    logger.info("Generating corridor data...")
    from backend.app.corridor.mock_data import generate_corridor_data
    df = generate_corridor_data(n_days=365)

    logger.info("Total rows: %d", len(df))
    logger.info("Features: %s", FEATURES)

    # Step 2: Temporal split
    dates = pd.to_datetime(df["date"])
    train_mask = dates < "2025-03-01"
    val_mask = (dates >= "2025-03-01") & (dates < "2025-05-01")
    test_mask = dates >= "2025-05-01"

    train_df = df[train_mask]
    val_df = df[val_mask]
    test_df = df[test_mask]

    X_train, y_train = train_df[FEATURES], train_df[TARGET]
    X_val, y_val = val_df[FEATURES], val_df[TARGET]
    X_test, y_test = test_df[FEATURES], test_df[TARGET]

    logger.info("Train: %d, Val: %d, Test: %d", len(X_train), len(X_val), len(X_test))

    # Save data splits
    CORRIDOR_DATA_DIR.mkdir(parents=True, exist_ok=True)
    train_df.to_parquet(CORRIDOR_DATA_DIR / "train.parquet", index=False)
    val_df.to_parquet(CORRIDOR_DATA_DIR / "val.parquet", index=False)
    test_df.to_parquet(CORRIDOR_DATA_DIR / "test.parquet", index=False)

    # Step 3: Train point model
    logger.info("\nTraining point model...")
    point_model = lgb.LGBMRegressor(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=8,
        num_leaves=63,
        min_child_samples=50,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.1,
        reg_lambda=0.1,
        random_state=42,
        verbose=-1,
    )
    point_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
    )

    # Step 4: Train quantile models
    logger.info("\nTraining Q10 model...")
    q10_model = lgb.LGBMRegressor(
        objective="quantile",
        alpha=0.10,
        n_estimators=500,
        learning_rate=0.05,
        max_depth=8,
        num_leaves=63,
        random_state=42,
        verbose=-1,
    )
    q10_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
    )

    logger.info("Training Q90 model...")
    q90_model = lgb.LGBMRegressor(
        objective="quantile",
        alpha=0.90,
        n_estimators=500,
        learning_rate=0.05,
        max_depth=8,
        num_leaves=63,
        random_state=42,
        verbose=-1,
    )
    q90_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)],
    )

    # Step 5: Evaluate
    logger.info("\n" + "=" * 60)
    logger.info("EVALUATION ON TEST SET")
    logger.info("=" * 60)

    preds = point_model.predict(X_test)
    q10_preds = q10_model.predict(X_test)
    q90_preds = q90_model.predict(X_test)

    mae = np.mean(np.abs(y_test - preds))
    rmse = np.sqrt(np.mean((y_test - preds) ** 2))
    median_ae = np.median(np.abs(y_test - preds))

    covered = ((y_test.values >= q10_preds) & (y_test.values <= q90_preds)).sum()
    coverage = covered / len(y_test) * 100
    avg_width = np.mean(q90_preds - q10_preds)

    logger.info("  MAE:              %.2f minutes", mae)
    logger.info("  RMSE:             %.2f minutes", rmse)
    logger.info("  Median AE:        %.2f minutes", median_ae)
    logger.info("  80%% PI Coverage:  %.1f%%", coverage)
    logger.info("  Avg PI Width:     %.1f minutes", avg_width)

    # Feature importance
    logger.info("\nFeature Importance:")
    imp = point_model.feature_importances_
    sorted_idx = np.argsort(imp)[::-1]
    for idx in sorted_idx:
        logger.info("  %-28s %d", FEATURES[idx], imp[idx])

    # Step 6: Save models
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(point_model, MODEL_DIR / "corridor_point.joblib")
    joblib.dump(q10_model, MODEL_DIR / "corridor_q10.joblib")
    joblib.dump(q90_model, MODEL_DIR / "corridor_q90.joblib")

    logger.info("\nModels saved to %s", MODEL_DIR)
    logger.info("Training complete!")


if __name__ == "__main__":
    main()
