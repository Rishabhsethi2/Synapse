"""
Mumbai-Goa Corridor - Mock Training Data Generator

Generates realistic delay data with weather, preceding train, and section
features. Data patterns mirror real Konkan Railway behavior:
- Monsoon (Jun-Sep): heavy delays from rain/landslides
- Ghat sections: higher delay variance
- Cascading delays: train ahead late → this train late
- Premium trains (Tejas): less delay
- Night trains: less delay (less traffic)
"""
import logging
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

from ..config import settings
from .data import CORRIDOR_STATIONS, CORRIDOR_TRAINS, SECTION_CHARACTERISTICS, STATION_BY_CODE

logger = logging.getLogger(__name__)

CORRIDOR_DATA_DIR = Path(settings.DATA_PROCESSED_DIR).parent / "corridor"


def generate_corridor_data(n_days: int = 365) -> pd.DataFrame:
    """
    Generate realistic corridor training data.

    Each row = one train at one station on one date.
    Features include weather, preceding train, section characteristics.
    """
    logger.info("Generating corridor training data for %d days...", n_days)
    CORRIDOR_DATA_DIR.mkdir(parents=True, exist_ok=True)

    np.random.seed(42)
    start_date = datetime(2024, 7, 1)
    rows = []

    for day_offset in range(n_days):
        date = start_date + timedelta(days=day_offset)
        day_of_week = date.weekday()
        month = date.month
        is_monsoon = 1 if month in (6, 7, 8, 9) else 0
        is_weekend = 1 if day_of_week >= 5 else 0

        # Generate weather for this day (varies by station)
        daily_rain_base = 0
        if is_monsoon:
            # Monsoon: 40% chance of rain, 15% heavy rain
            r = np.random.random()
            if r < 0.15:
                daily_rain_base = np.random.uniform(30, 80)  # Heavy
            elif r < 0.40:
                daily_rain_base = np.random.uniform(5, 30)   # Moderate
            else:
                daily_rain_base = np.random.uniform(0, 5)    # Light
        else:
            # Non-monsoon: 10% chance of light rain
            if np.random.random() < 0.10:
                daily_rain_base = np.random.uniform(1, 10)

        for train_info in CORRIDOR_TRAINS:
            train_no = train_info["train_no"]
            train_type = train_info["type"]
            priority = train_info["priority"]
            stops = train_info["stops"]

            # Premium trains have less base delay
            type_factor = 0.6 if train_type in ("TEJAS", "SHTBD") else 1.0
            # Night trains have less delay
            dep_hour = int(train_info["departure"].split(":")[0])
            night_factor = 0.7 if dep_hour >= 22 or dep_hour < 5 else 1.0

            # Preceding train delay (simulated)
            preceding_delay = 0
            if np.random.random() < 0.3:
                preceding_delay = np.random.exponential(15) * (1.5 if is_monsoon else 1.0)

            current_delay = 0.0
            for i, station_code in enumerate(stops):
                station = STATION_BY_CODE.get(station_code, {})
                distance = station.get("km", 0)
                section_type = station.get("section_type", "coastal")

                # Rain at this station (varies from base)
                station_rain = max(0, daily_rain_base + np.random.normal(0, 5))
                # Ghat sections get more rain
                if section_type == "ghat":
                    station_rain *= 1.3

                visibility = max(0.5, 10.0 - station_rain * 0.15 + np.random.normal(0, 1))

                # Section characteristics
                if i > 0:
                    section_key = f"{stops[i-1]}->{station_code}"
                    section = SECTION_CHARACTERISTICS.get(section_key, {})
                else:
                    section = {"track": "double", "terrain": "urban", "tunnels": 0, "bridges": 0, "speed_limit": 80, "risk": "low"}

                is_single_track = 1 if section.get("track") == "single" else 0
                is_ghat = 1 if section.get("terrain") in ("ghat", "coastal_ghat") else 0
                tunnel_count = section.get("tunnels", 0)
                bridge_count = section.get("bridges", 0)
                speed_limit = section.get("speed_limit", 80)

                # Weather severity score
                weather_severity = min(1.0, station_rain / 50.0 + (1.0 - visibility / 10.0) * 0.3)

                # Compute delay at this station using realistic model
                # Base delay change from previous station
                if i == 0:
                    # Origin: small random delay
                    delay_change = max(0, np.random.normal(2, 3)) * type_factor
                else:
                    # Delay tends to grow, but can recover
                    base_change = np.random.normal(0.5, 3)

                    # Weather impact
                    weather_impact = 0
                    if station_rain > 30:
                        weather_impact = np.random.uniform(5, 15)
                    elif station_rain > 10:
                        weather_impact = np.random.uniform(2, 7)
                    elif station_rain > 2:
                        weather_impact = np.random.uniform(0, 3)

                    # Ghat section impact
                    ghat_impact = 0
                    if is_ghat:
                        ghat_impact = np.random.uniform(1, 5) * (1 + weather_severity)

                    # Single track impact (crossing delays)
                    single_track_impact = 0
                    if is_single_track and np.random.random() < 0.25:
                        single_track_impact = np.random.uniform(2, 10)

                    # Preceding train impact
                    preceding_impact = 0
                    if preceding_delay > 5 and is_single_track:
                        preceding_impact = preceding_delay * np.random.uniform(0.1, 0.4)

                    # Recovery (trains try to make up time)
                    recovery = 0
                    if current_delay > 10:
                        recovery = -np.random.uniform(1, 4) * (1 if priority == 1 else 0.5)

                    delay_change = (
                        base_change
                        + weather_impact * type_factor
                        + ghat_impact * type_factor
                        + single_track_impact
                        + preceding_impact
                        + recovery
                    ) * night_factor

                current_delay = max(-5, current_delay + delay_change)

                # Scheduled running time from origin
                sched_times = train_info["scheduled_times"].get(station_code, ("", ""))
                arr_str = sched_times[0] or sched_times[1]
                dep_str_origin = train_info["departure"]
                try:
                    arr_parts = arr_str.split(":")
                    dep_parts = dep_str_origin.split(":")
                    sched_rt = (int(arr_parts[0]) * 60 + int(arr_parts[1])) - (int(dep_parts[0]) * 60 + int(dep_parts[1]))
                    if sched_rt < 0:
                        sched_rt += 24 * 60
                except (ValueError, IndexError):
                    sched_rt = 0

                rows.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "train_no": train_no,
                    "train_type": train_type,
                    "station_code": station_code,
                    "station_no": i + 1,
                    "distance_from_origin_km": distance,
                    "scheduled_running_time": sched_rt,
                    "day_of_week": day_of_week,
                    "is_weekend": is_weekend,
                    "is_monsoon": is_monsoon,
                    "month": month,
                    "departure_hour": dep_hour,
                    # Weather
                    "rainfall_mm": round(station_rain, 1),
                    "visibility_km": round(visibility, 1),
                    "weather_severity": round(weather_severity, 3),
                    # Section
                    "is_single_track": is_single_track,
                    "is_ghat_section": is_ghat,
                    "tunnel_count": tunnel_count,
                    "bridge_count": bridge_count,
                    "speed_limit": speed_limit,
                    # Network
                    "preceding_train_delay": round(max(0, preceding_delay), 1),
                    # Train
                    "is_premium": 1 if priority == 1 else 0,
                    # Previous station delay (causal)
                    "previous_station_delay": round(current_delay - delay_change, 1) if i > 0 else 0,
                    # Target
                    "delay_minutes": round(current_delay, 1),
                })

            # Update preceding delay for next train
            preceding_delay = current_delay * np.random.uniform(0.3, 0.7)

    df = pd.DataFrame(rows)
    logger.info("Generated %d rows for corridor training data", len(df))
    return df


def save_corridor_data():
    """Generate and save corridor data to parquet files."""
    df = generate_corridor_data(n_days=365)

    # Temporal split
    dates = pd.to_datetime(df["date"])
    train_mask = dates < "2025-03-01"
    val_mask = (dates >= "2025-03-01") & (dates < "2025-05-01")
    test_mask = dates >= "2025-05-01"

    CORRIDOR_DATA_DIR.mkdir(parents=True, exist_ok=True)

    train_df = df[train_mask]
    val_df = df[val_mask]
    test_df = df[test_mask]

    train_df.to_parquet(CORRIDOR_DATA_DIR / "train.parquet", index=False)
    val_df.to_parquet(CORRIDOR_DATA_DIR / "val.parquet", index=False)
    test_df.to_parquet(CORRIDOR_DATA_DIR / "test.parquet", index=False)

    logger.info(
        "Saved: train=%d, val=%d, test=%d to %s",
        len(train_df), len(val_df), len(test_df), CORRIDOR_DATA_DIR
    )
    return train_df, val_df, test_df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    save_corridor_data()
