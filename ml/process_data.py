"""
Synapse — Data Processing Pipeline

Processes raw CSV data into ML-ready parquet files with temporal split.
"""
import sys
import io
import logging
import pandas as pd
import numpy as np
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_END = "2025-10-31"
VAL_END = "2025-12-31"


def parse_minutes(s):
    """Convert HH:MM string to total minutes from midnight."""
    try:
        parts = str(s).split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError, TypeError):
        return np.nan


def load_schedule():
    """Load schedule and compute features."""
    logger.info("Loading schedule data...")
    sched = pd.read_csv(RAW_DIR / "combined_schedule.csv")

    # Normalize train_no to string, strip leading zeros
    sched["train_no"] = sched["train_no"].astype(str).str.strip().str.lstrip("0")
    sched["station_name"] = sched["station_name"].astype(str).str.strip()
    sched["distance_from_origin"] = pd.to_numeric(sched["distance_from_origin"], errors="coerce").fillna(0)

    # Parse times to minutes
    sched["arr_min"] = sched["arrival_time"].apply(parse_minutes)
    sched["dep_min"] = sched["departure_time"].apply(parse_minutes)

    # Compute scheduled running time from origin
    logger.info("Computing scheduled running times (vectorized)...")

    # Sort within each train by distance
    sched = sched.sort_values(["train_no", "distance_from_origin"]).reset_index(drop=True)

    # Get origin departure time per train
    origin_time = sched.groupby("train_no").agg(
        origin_dep=("dep_min", "first"),
        origin_arr=("arr_min", "first"),
    ).reset_index()
    origin_time["origin_base"] = origin_time["origin_dep"].fillna(origin_time["origin_arr"]).fillna(0)

    sched = sched.merge(origin_time[["train_no", "origin_base"]], on="train_no", how="left")

    # Use arrival time, fallback to departure time
    sched["station_time"] = sched["arr_min"].fillna(sched["dep_min"])

    # Running time = station_time - origin_base (handle day crossing)
    sched["scheduled_running_time"] = sched["station_time"] - sched["origin_base"]
    sched.loc[sched["scheduled_running_time"] < 0, "scheduled_running_time"] += 24 * 60
    sched["scheduled_running_time"] = sched["scheduled_running_time"].fillna(0)

    # Build lookup dict: (train_no, station_name) -> features
    logger.info("Building schedule lookup...")
    sched_lookup = {}
    for tn, sn, dist, rt, sno in zip(
        sched["train_no"], sched["station_name"],
        sched["distance_from_origin"], sched["scheduled_running_time"],
        sched["station_no"],
    ):
        sched_lookup[(tn, sn)] = {
            "distance_from_origin_km": float(dist),
            "scheduled_running_time": float(rt),
            "station_no": int(sno),
        }

    logger.info(f"Schedule: {len(sched)} rows, {len(sched_lookup)} lookups")
    return sched_lookup


def main():
    logger.info("=" * 60)
    logger.info("SYNAPSE DATA PROCESSING PIPELINE")
    logger.info("=" * 60)

    sched_lookup = load_schedule()

    # Process delay data in chunks
    delay_file = RAW_DIR / "combined_delay.csv"
    logger.info(f"Processing: {delay_file}")

    all_records = []
    chunk_count = 0

    for chunk in pd.read_csv(
        delay_file,
        chunksize=500_000,
        dtype={"train_no": str, "station_name": str, "delay": str, "station_no": "Int64", "date": str},
    ):
        chunk_count += 1

        # Normalize
        chunk["train_no"] = chunk["train_no"].str.strip().str.lstrip("0")
        chunk["station_name"] = chunk["station_name"].str.strip()
        chunk["date"] = chunk["date"].str.strip()

        # Parse delay
        chunk["delay_val"] = pd.to_numeric(chunk["delay"], errors="coerce")
        chunk = chunk.dropna(subset=["delay_val"])

        # Day of week
        chunk["date_parsed"] = pd.to_datetime(chunk["date"], format="%Y-%m-%d", errors="coerce")
        chunk = chunk.dropna(subset=["date_parsed"])
        chunk["day_of_week"] = chunk["date_parsed"].dt.dayofweek

        # Join with schedule
        dists = []
        rts = []
        for tn, sn in zip(chunk["train_no"], chunk["station_name"]):
            info = sched_lookup.get((tn, sn), {})
            dists.append(info.get("distance_from_origin_km", 0))
            rts.append(info.get("scheduled_running_time", 0))

        chunk["distance_from_origin_km"] = dists
        chunk["scheduled_running_time"] = rts

        # Keep needed columns
        records = chunk[["train_no", "date", "station_name", "station_no",
                          "distance_from_origin_km", "scheduled_running_time",
                          "day_of_week", "delay_val"]].copy()
        records = records.rename(columns={"delay_val": "delay_minutes"})

        all_records.append(records)
        logger.info(f"  Chunk {chunk_count}: {len(records)} rows (total: {sum(len(r) for r in all_records)})")

    # Concatenate
    logger.info("Concatenating...")
    df = pd.concat(all_records, ignore_index=True)
    logger.info(f"Total: {len(df)} rows")

    # Add previous_station_delay
    logger.info("Computing previous_station_delay...")
    df = df.sort_values(["train_no", "date", "station_no"]).reset_index(drop=True)
    df["previous_station_delay"] = df.groupby(["train_no", "date"])["delay_minutes"].shift(1).fillna(0)

    # Temporal split
    logger.info(f"Splitting: train <= {TRAIN_END}, val <= {VAL_END}")
    train_df = df[df["date"] <= TRAIN_END]
    val_df = df[(df["date"] > TRAIN_END) & (df["date"] <= VAL_END)]
    test_df = df[df["date"] > VAL_END]

    logger.info(f"Train: {len(train_df)}, Val: {len(val_df)}, Test: {len(test_df)}")

    # Save
    ml_cols = ["distance_from_origin_km", "previous_station_delay", "day_of_week",
               "scheduled_running_time", "delay_minutes"]

    for name, split in [("train", train_df), ("val", val_df), ("test", test_df)]:
        path = PROCESSED_DIR / f"{name}.parquet"
        split[ml_cols].to_parquet(path, index=False)
        logger.info(f"Saved {path} ({len(split)} rows)")

    # Stats
    logger.info("\nFeature Statistics:")
    for col in ml_cols:
        logger.info(f"  {col}: mean={df[col].mean():.2f}, std={df[col].std():.2f}")

    logger.info("Pipeline complete!")


if __name__ == "__main__":
    main()
