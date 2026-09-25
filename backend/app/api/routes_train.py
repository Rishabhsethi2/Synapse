"""
Synapse - Train API Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime
from zoneinfo import ZoneInfo

from ..dependencies import (
    get_train_state_engine, get_synapse_forecaster,
    get_attribution_engine, get_stability_tracker,
    station_lookup, train_lookup, route_lookup,
    synapse_forecaster, feature_engine, attribution_engine,
    stability_tracker, train_state_engine,
)
from ..state.train_state import TrainStateEngine
from ..config import settings

router = APIRouter(tags=["trains"])
IST = ZoneInfo(settings.TIMEZONE)


@router.get("/trains")
def list_trains():
    """List all registered trains with their current state."""
    active = train_state_engine.get_all_active_trains()
    result = []
    for entry in active:
        train_info = train_lookup.get(entry.train_no, {})
        result.append({
            "train_id": entry.train_no,
            "train_name": train_info.get("train_name", "Unknown"),
            "type_code": train_info.get("type_code", ""),
            "current_station": entry.current_station_code,
            "current_delay_minutes": entry.current_delay_minutes,
            "journey_progress": round(entry.journey_progress, 2),
            "freshness": entry.freshness_label,
            "has_arrived": entry.has_arrived_destination,
        })

    # If no active trains, return available train list from lookup
    if not result:
        sample = list(train_lookup.items())[:50]
        result = [
            {
                "train_id": no,
                "train_name": info.get("train_name", ""),
                "type_code": info.get("type_code", ""),
                "current_station": "N/A",
                "current_delay_minutes": 0,
                "journey_progress": 0.0,
                "freshness": "NOT_STARTED",
                "has_arrived": False,
            }
            for no, info in sample
        ]

    return {"trains": result, "total": len(result)}


@router.get("/trains/{train_id}/eta")
def get_train_eta(train_id: str):
    """Get ETA predictions for all remaining stations."""
    entry = train_state_engine.get_train(train_id)
    route = route_lookup.get(train_id, [])

    if not route:
        raise HTTPException(404, f"Train {train_id} route not found")

    predictions = []
    for stop in route:
        station_code = stop["station_name"]
        sched_time = stop.get("arrival_time") or stop.get("departure_time")

        # Build simple features for prediction
        features = {
            "current_delay_minutes": entry.current_delay_minutes if entry else 0,
            "distance_from_origin_km": stop.get("distance_from_origin", 0),
            "previous_station_delay": entry.current_delay_minutes if entry else 0,
            "day_of_week": datetime.now(IST).weekday(),
            "scheduled_running_time": 0,
        }

        pred_delay = synapse_forecaster.predict_delay(features)
        q10, q50, q90 = synapse_forecaster.predict_quantiles(features)

        predictions.append({
            "station_code": station_code,
            "station_no": stop["station_no"],
            "scheduled_time": str(sched_time) if sched_time else None,
            "predicted_delay_minutes": round(pred_delay, 1),
            "lower_bound_delay": round(q10, 1),
            "upper_bound_delay": round(q90, 1),
            "distance_from_origin_km": stop.get("distance_from_origin", 0),
        })

    train_info = train_lookup.get(train_id, {})
    return {
        "train_id": train_id,
        "train_name": train_info.get("train_name", "Unknown"),
        "current_delay": entry.current_delay_minutes if entry else 0,
        "model_version": synapse_forecaster.model_version,
        "predictions": predictions,
    }


@router.get("/trains/{train_id}/trajectory")
def get_train_trajectory(train_id: str):
    """Get the delay trajectory (delay at each station) for the train."""
    route = route_lookup.get(train_id, [])
    if not route:
        raise HTTPException(404, f"Train {train_id} route not found")

    trajectory = []
    for stop in route:
        trajectory.append({
            "station_code": stop["station_name"],
            "station_no": stop["station_no"],
            "distance_from_origin_km": stop.get("distance_from_origin", 0),
            "scheduled_arrival": str(stop.get("arrival_time", "")) if stop.get("arrival_time") else None,
            "scheduled_departure": str(stop.get("departure_time", "")) if stop.get("departure_time") else None,
        })

    return {"train_id": train_id, "trajectory": trajectory}


@router.get("/trains/{train_id}/attribution")
def get_train_attribution(train_id: str, station_code: str = ""):
    """Get delay attribution (what factors contribute to delay)."""
    importance = synapse_forecaster.get_feature_importance()
    entry = train_state_engine.get_train(train_id)
    current_delay = entry.current_delay_minutes if entry else 0

    # Scale importances by current delay to get contribution minutes
    contributions = {}
    total_imp = sum(importance.values()) or 1.0
    for feat, imp in importance.items():
        contributions[feat] = round(current_delay * (imp / total_imp), 1)

    attribution = attribution_engine.get_attribution(
        train_id=train_id,
        station_code=station_code or "DESTINATION",
        feature_contributions=contributions,
    )

    return attribution.model_dump()


@router.get("/trains/{train_id}/stability")
def get_train_stability(train_id: str, station_code: str = ""):
    """Get forecast stability for a train's ETA predictions."""
    stability = stability_tracker.get_stability(
        train_id=train_id,
        station_code=station_code or "DESTINATION",
    )
    return stability.model_dump()


@router.get("/trains/{train_id}/health")
def get_train_health(train_id: str):
    """Get data health / freshness for a train."""
    entry = train_state_engine.get_train(train_id)
    if entry is None:
        return {
            "train_id": train_id,
            "status": "NOT_TRACKED",
            "message": "Train is not currently being tracked. Start a replay or wait for live data.",
        }

    return {
        "train_id": train_id,
        "current_station": entry.current_station_code,
        "freshness": entry.freshness_label,
        "freshness_seconds": round(entry.data_freshness_seconds, 1),
        "source": entry.source,
        "journey_progress": round(entry.journey_progress, 2),
        "stations_remaining": len(entry.remaining_stations),
    }


# ── Live Prediction (Manual Input) ──────────────────────────────
from pydantic import BaseModel


class LivePredictRequest(BaseModel):
    train_no: str
    last_station: str  # Station code the train last departed from
    delay_minutes: float  # Current delay at that station


def _parse_time_minutes(t) -> float:
    """Convert HH:MM:SS or HH:MM time string to minutes from midnight."""
    try:
        parts = str(t).split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (ValueError, IndexError):
        return 0


@router.post("/predict/live")
def predict_live(req: LivePredictRequest):
    """
    Manual live prediction: given a train number, the last station it
    departed from, and the current delay - predict delay at every
    remaining station using chained LightGBM predictions.

    Each station's predicted delay becomes the 'previous_station_delay'
    for the next station, creating a rolling forecast.
    """
    train_no = req.train_no.strip().lstrip("0")
    last_station = req.last_station.strip().upper()

    route = route_lookup.get(train_no, [])
    if not route:
        raise HTTPException(404, f"Train {train_no} not found in schedule data")

    train_info = train_lookup.get(train_no, {})

    # Find the last station in the route
    last_idx = -1
    for i, stop in enumerate(route):
        if stop["station_name"].strip().upper() == last_station:
            last_idx = i
            break

    if last_idx == -1:
        # Try partial match
        for i, stop in enumerate(route):
            if last_station in stop["station_name"].strip().upper():
                last_idx = i
                break

    if last_idx == -1:
        available = [s["station_name"] for s in route]
        raise HTTPException(
            404,
            f"Station '{req.last_station}' not found in route for train {train_no}. "
            f"Available stations: {available}"
        )

    # Compute origin departure time for scheduled_running_time calculation
    origin_stop = route[0]
    origin_dep_str = origin_stop.get("departure_time") or origin_stop.get("arrival_time")
    origin_dep_min = _parse_time_minutes(origin_dep_str)

    now = datetime.now(IST)
    day_of_week = now.weekday()

    # Build predictions for remaining stations (after last_idx)
    remaining_stops = route[last_idx + 1:]
    if not remaining_stops:
        return {
            "train_no": train_no,
            "train_name": train_info.get("train_name", "Unknown"),
            "last_station": route[last_idx]["station_name"],
            "input_delay_minutes": req.delay_minutes,
            "message": "Train has reached or passed its final station.",
            "predictions": [],
        }

    # Chain predictions: use previous prediction as input for next
    current_delay = req.delay_minutes
    predictions = []

    # Include passed stations
    passed_stations = []
    for i in range(last_idx + 1):
        stop = route[i]
        passed_stations.append({
            "station_code": stop["station_name"],
            "station_no": stop["station_no"],
            "distance_from_origin_km": stop.get("distance_from_origin", 0),
            "scheduled_arrival": str(stop.get("arrival_time", "")) if stop.get("arrival_time") else None,
            "scheduled_departure": str(stop.get("departure_time", "")) if stop.get("departure_time") else None,
            "status": "PASSED" if i < last_idx else "DEPARTED",
            "actual_delay": req.delay_minutes if i == last_idx else None,
        })

    for stop in remaining_stops:
        distance = stop.get("distance_from_origin", 0)
        arr_str = stop.get("arrival_time") or stop.get("departure_time")
        arr_min = _parse_time_minutes(arr_str)

        # Scheduled running time from origin
        sched_rt = arr_min - origin_dep_min
        if sched_rt < 0:
            sched_rt += 24 * 60  # Day crossing

        features = {
            "distance_from_origin_km": distance,
            "previous_station_delay": current_delay,
            "day_of_week": day_of_week,
            "scheduled_running_time": sched_rt,
        }

        pred_delay = synapse_forecaster.predict_delay(features)
        q10, q50, q90 = synapse_forecaster.predict_quantiles(features)

        predictions.append({
            "station_code": stop["station_name"],
            "station_no": stop["station_no"],
            "distance_from_origin_km": distance,
            "scheduled_arrival": str(stop.get("arrival_time", "")) if stop.get("arrival_time") else None,
            "predicted_delay_minutes": round(pred_delay, 1),
            "lower_bound": round(q10, 1),
            "upper_bound": round(q90, 1),
            "status": "PREDICTED",
        })

        # Chain: this prediction becomes the previous_station_delay for next
        current_delay = pred_delay

    # Compute full station name lookups
    last_station_info = station_lookup.get(route[last_idx]["station_name"], {})

    return {
        "train_no": train_no,
        "train_name": train_info.get("train_name", "Unknown"),
        "type_code": train_info.get("type_code", ""),
        "last_station": route[last_idx]["station_name"],
        "last_station_full_name": last_station_info.get("station_full_name", route[last_idx]["station_name"]),
        "input_delay_minutes": req.delay_minutes,
        "day_of_week": day_of_week,
        "prediction_generated_at": now.isoformat(),
        "model_version": synapse_forecaster.model_version,
        "total_stations": len(route),
        "stations_passed": last_idx + 1,
        "stations_remaining": len(remaining_stops),
        "passed_stations": passed_stations,
        "predictions": predictions,
        "methodology": "Chained LightGBM predictions - each station's predicted delay feeds into the next station's features. Model trained on 26.6M real observations.",
    }


@router.get("/stations/search")
def search_stations(q: str = ""):
    """Search stations by code or name for autocomplete."""
    if not q or len(q) < 2:
        return {"stations": []}

    q_upper = q.strip().upper()
    results = []
    for code, info in station_lookup.items():
        full_name = info.get("station_full_name", "")
        if q_upper in code.upper() or q_upper in full_name.upper():
            results.append({
                "code": code,
                "full_name": full_name,
                "zone": info.get("station_zone", ""),
            })
            if len(results) >= 20:
                break

    return {"stations": results}


@router.get("/trains/search")
def search_trains(q: str = ""):
    """Search trains by number or name for autocomplete."""
    if not q or len(q) < 2:
        return {"trains": []}

    q_upper = q.strip().upper()
    results = []
    for no, info in train_lookup.items():
        name = info.get("train_name", "")
        if q_upper in no or q_upper in name.upper():
            results.append({
                "train_no": no,
                "train_name": name,
                "type_code": info.get("type_code", ""),
            })
            if len(results) >= 20:
                break

    return {"trains": results}

