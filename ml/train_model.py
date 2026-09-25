"""
Synapse — ML Model Training Pipeline

Trains LightGBM models on the processed data from process_data.py.
Produces:
  - Point prediction model (regression)
  - Quantile models (q10, q90) for uncertainty intervals

Usage:
  1. First run: python ml/process_data.py
  2. Then run: python ml/train_model.py
"""
import sys
import io
import logging
import joblib
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.metrics import mean_absolute_error, mean_squared_error
import lightgbm as lgb

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
MODELS_DIR = BASE_DIR / "data" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_COL = "delay_minutes"
FEATURE_COLS = [
    "distance_from_origin_km",
    "previous_station_delay",
    "day_of_week",
    "scheduled_running_time",
]


def load_data(filename: str) -> pd.DataFrame:
    """Load parquet file."""
    filepath = PROCESSED_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(
            f"{filepath} not found. Run 'python ml/process_data.py' first."
        )
    logger.info(f"Loading {filename}...")
    df = pd.read_parquet(filepath)
    logger.info(f"  Shape: {df.shape}")
    return df


def train_and_evaluate():
    logger.info("=" * 60)
    logger.info("SYNAPSE ML TRAINING PIPELINE")
    logger.info("=" * 60)

    # 1. Load data
    train_df = load_data("train.parquet")
    val_df = load_data("val.parquet")
    test_df = load_data("test.parquet")

    X_train, y_train = train_df[FEATURE_COLS], train_df[TARGET_COL]
    X_val, y_val = val_df[FEATURE_COLS], val_df[TARGET_COL]
    X_test, y_test = test_df[FEATURE_COLS], test_df[TARGET_COL]

    logger.info(f"Training set: {len(X_train)} samples")
    logger.info(f"Validation set: {len(X_val)} samples")
    logger.info(f"Test set: {len(X_test)} samples")
    logger.info(f"Features: {FEATURE_COLS}")

    # 2. Train Point Prediction Model
    logger.info("\nTraining Point Prediction Model (LGBMRegressor)...")
    point_model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=500,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=8,
        min_child_samples=100,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbose=-1,
    )
    point_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(50, verbose=True), lgb.log_evaluation(100)],
    )

    # 3. Train Quantile Models (alpha = 0.10, 0.90) for 80% prediction intervals
    logger.info("\nTraining Quantile Model (alpha=0.10)...")
    q10_model = lgb.LGBMRegressor(
        objective="quantile",
        alpha=0.10,
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=8,
        random_state=42,
        verbose=-1,
    )
    q10_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(100)],
    )

    logger.info("Training Quantile Model (alpha=0.90)...")
    q90_model = lgb.LGBMRegressor(
        objective="quantile",
        alpha=0.90,
        n_estimators=300,
        learning_rate=0.05,
        num_leaves=63,
        max_depth=8,
        random_state=42,
        verbose=-1,
    )
    q90_model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(100)],
    )

    # 4. Evaluation on Test Set
    logger.info("\n" + "=" * 60)
    logger.info("EVALUATION ON TEST SET")
    logger.info("=" * 60)

    preds_point = point_model.predict(X_test)
    preds_q10 = q10_model.predict(X_test)
    preds_q90 = q90_model.predict(X_test)

    mae = mean_absolute_error(y_test, preds_point)
    rmse = np.sqrt(mean_squared_error(y_test, preds_point))
    median_ae = np.median(np.abs(y_test - preds_point))

    # Coverage: % of actuals within [q10, q90]
    covered = ((y_test >= preds_q10) & (y_test <= preds_q90)).sum()
    coverage = covered / len(y_test) * 100
    avg_interval_width = np.mean(preds_q90 - preds_q10)

    logger.info(f"  Point Model MAE:   {mae:.2f} minutes")
    logger.info(f"  Point Model RMSE:  {rmse:.2f} minutes")
    logger.info(f"  Median AE:         {median_ae:.2f} minutes")
    logger.info(f"  80% PI Coverage:   {coverage:.1f}%")
    logger.info(f"  Avg Interval Width: {avg_interval_width:.1f} minutes")

    # Feature importance
    logger.info("\nFeature Importance:")
    for feat, imp in sorted(
        zip(FEATURE_COLS, point_model.feature_importances_),
        key=lambda x: x[1],
        reverse=True,
    ):
        logger.info(f"  {feat}: {imp}")

    # 5. Save Models
    point_path = MODELS_DIR / "lgbm_point_v1.0.0.joblib"
    q10_path = MODELS_DIR / "lgbm_q10_v1.0.0.joblib"
    q90_path = MODELS_DIR / "lgbm_q90_v1.0.0.joblib"

    joblib.dump(point_model, point_path)
    joblib.dump(q10_model, q10_path)
    joblib.dump(q90_model, q90_path)

    logger.info(f"\nModels saved to {MODELS_DIR}")
    logger.info("Training pipeline complete!")


if __name__ == "__main__":
    train_and_evaluate()
