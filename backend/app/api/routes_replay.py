"""
Synapse - Replay API Routes

The replay engine is the primary way to demonstrate Synapse.
It steps through historical journeys, updating train state
at each tick, and generating real predictions.
"""
import csv
from io import StringIO
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..dependencies import (
    replay_engine, train_state_engine, synapse_forecaster,
    stability_tracker, route_lookup, train_lookup,
)
from ..config import settings

router = APIRouter(tags=["replay"])


class ReplayStartRequest(BaseModel):
    train_no: str
    date: str  # YYYY-MM-DD
    scenario_id: Optional[str] = None


@router.post("/replay/start")
def start_replay(request: ReplayStartRequest):
    """
    Start a replay scenario for a specific train on a specific date.
    Loads the historical delay data and schedule for that journey.
    """
    raw_dir = Path(settings.DATA_RAW_DIR)
    delay_file = raw_dir / "combined_delay.csv"
    schedule_file = raw_dir / "combined_schedule.csv"

    if not delay_file.exists():
        raise HTTPException(500, "Delay data file not found")

    # Find delay records for this train+date using chunked pandas (fast on 38M rows)
    import pandas as pd
    journey_data = []
    for chunk in pd.read_csv(
        delay_file,
        chunksize=500_000,
        dtype={"train_no": str, "station_name": str, "delay": str, "station_no": int, "date": str},
    ):
        chunk["train_no"] = chunk["train_no"].str.strip().str.lstrip("0")
        chunk["date"] = chunk["date"].str.strip()
        match = chunk[(chunk["train_no"] == request.train_no) & (chunk["date"] == request.date)]
        for _, row in match.iterrows():
            delay_val = str(row.get("delay", "")).strip()
            journey_data.append({
                "train_no": request.train_no,
                "date": request.date,
                "station_no": int(row["station_no"]),
                "station_code": str(row.get("station_name", "")).strip(),
                "delay_minutes": int(delay_val) if delay_val and delay_val not in ("", "nan") else None,
            })
        if journey_data:
            break  # Found data, no need to scan more chunks

    if not journey_data:
        raise HTTPException(
            404,
            f"No delay data found for train {request.train_no} on {request.date}. "
            f"Try a different date or train number.",
        )

    # Sort by station_no
    journey_data.sort(key=lambda x: x["station_no"])

    # Find schedule for this train
    schedule_data = []
    route = route_lookup.get(request.train_no, [])
    for stop in route:
        schedule_data.append({
            "station_no": stop["station_no"],
            "station_code": stop["station_name"],
            "arrival_time": str(stop["arrival_time"]) if stop.get("arrival_time") else None,
            "departure_time": str(stop["departure_time"]) if stop.get("departure_time") else None,
            "distance_from_origin_km": stop.get("distance_from_origin", 0),
        })

    # Create and configure replay scenario
    scenario_id = request.scenario_id or f"{request.train_no}_{request.date}"
    scenario = replay_engine.create_scenario(scenario_id, journey_data, schedule_data)

    # Register the train in the state engine
    station_codes = [step["station_code"] for step in journey_data]
    station_nos = [step["station_no"] for step in journey_data]
    train_state_engine.register_train(request.train_no, station_codes, station_nos)

    replay_engine.start_scenario(scenario_id)

    train_info = train_lookup.get(request.train_no, {})
    return {
        "status": "started",
        "scenario_id": scenario_id,
        "train_no": request.train_no,
        "train_name": train_info.get("train_name", "Unknown"),
        "date": request.date,
        "total_stations": len(journey_data),
        "stations": [d["station_code"] for d in journey_data],
    }


@router.post("/replay/tick")
def replay_tick():
    """
    Advance the replay by one station.
    Returns the observation, updates train state, generates prediction.
    """
    scenario = replay_engine.get_active_scenario()
    if scenario is None:
        raise HTTPException(400, "No active replay. POST /api/replay/start first.")

    step = replay_engine.tick()
    if step is None:
        # Replay complete - return evaluation
        evaluation = scenario.get_evaluation()
        return {
            "status": "completed",
            "evaluation": evaluation,
            "message": "Replay journey complete. All stations have been visited.",
        }

    # Update train state engine
    train_state_engine.update_train(
        train_no=step.train_no,
        station_index=step.station_no - 1,  # Convert 1-indexed to 0-indexed
        station_code=step.station_code,
        delay_minutes=step.delay_minutes,
        timestamp=step.timestamp,
        source="REPLAY",
    )

    # Generate predictions for remaining stations
    entry = train_state_engine.get_train(step.train_no)
    predictions = []
    if entry and entry.remaining_stations:
        for rem_station in entry.remaining_stations:
            features = {
                "current_delay_minutes": step.delay_minutes,
                "distance_from_origin_km": step.distance_from_origin_km,
                "previous_station_delay": step.delay_minutes,
                "day_of_week": step.timestamp.weekday() if step.timestamp else 0,
                "scheduled_running_time": 0,
            }
            pred_delay = synapse_forecaster.predict_delay(features)
            q10, q50, q90 = synapse_forecaster.predict_quantiles(features)

            predictions.append({
                "station_code": rem_station,
                "predicted_delay_minutes": round(pred_delay, 1),
                "lower_bound": round(q10, 1),
                "upper_bound": round(q90, 1),
            })

    # Record stability
    if predictions:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        IST = ZoneInfo(settings.TIMEZONE)
        for pred in predictions:
            stability_tracker.record_prediction(
                train_id=step.train_no,
                station_code=pred["station_code"],
                timestamp=step.timestamp or datetime.now(IST),
                eta=step.timestamp + timedelta(minutes=pred["predicted_delay_minutes"]) if step.timestamp else datetime.now(IST),
            )

    return {
        "status": "tick",
        "step": {
            "train_no": step.train_no,
            "station_code": step.station_code,
            "station_no": step.station_no,
            "delay_minutes": step.delay_minutes,
            "is_final": step.is_final_station,
            "timestamp": step.timestamp.isoformat() if step.timestamp else None,
        },
        "predictions": predictions,
        "replay_progress": round(scenario.progress, 2),
    }


@router.get("/replay/state")
def get_replay_state():
    """Get current replay state."""
    scenario = replay_engine.get_active_scenario()
    if scenario is None:
        return {"status": "no_active_replay", "message": "POST /api/replay/start to begin."}
    return scenario.get_state_summary()


@router.get("/evaluation/summary")
def get_evaluation_summary():
    """Get evaluation metrics from the completed replay."""
    scenario = replay_engine.get_active_scenario()
    if scenario is None:
        return {"error": "No active replay scenario"}
    return scenario.get_evaluation()
