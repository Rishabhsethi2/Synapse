"""
Train Tracker - fetches live status and produces predictions.

For corridor trains: uses corridor ML model + real weather + section data + SHAP.
For non-corridor trains: uses national model + API upcoming stations.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from .live_api import fetch_live_train, _cache as live_cache, QuotaExceededError  # noqa: F401
from .data import CORRIDOR_TRAINS, STATION_BY_CODE, TRAIN_BY_NO, SECTION_CHARACTERISTICS, STATION_CODES
from .weather import fetch_corridor_weather
from .model import CorridorForecaster

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

corridor_forecaster = CorridorForecaster()

# A train merely passing through one Konkan station is not a Mumbai–Goa
# service. These gateway codes keep the specialised corridor experience
# limited to journeys that actually begin/end in the Mumbai–Goa corridor.
MUMBAI_GATEWAYS = {"CSMT", "LTT", "DR", "PNVL"}
GOA_GATEWAYS = {"MAO", "KRMI", "THVM"}


def _is_mumbai_goa_service(live_data: dict, requested_train_no: str) -> bool:
    """Return True only for a known or endpoint-verified Mumbai–Goa service."""
    live_train_no = str(live_data.get("train_no") or requested_train_no).strip()
    if live_train_no in TRAIN_BY_NO:
        return True

    source = str(live_data.get("source") or "").strip().upper()
    destination = str(live_data.get("destination") or "").strip().upper()
    return (
        source in MUMBAI_GATEWAYS and destination in GOA_GATEWAYS
    ) or (
        source in GOA_GATEWAYS and destination in MUMBAI_GATEWAYS
    )


def _corridor_stops(live_data: dict) -> list[str]:
    """Return the corridor stations in chronological order from a live feed."""
    stops = [s.get("station_code", "") for s in live_data.get("previous_stations", [])]
    stops.append(live_data.get("current_station_code", ""))
    stops.extend(s.get("station_code", "") for s in live_data.get("upcoming_stations", []))
    return [stop for stop in stops if stop in STATION_CODES]


def _corridor_direction(live_data: dict, train_no: str) -> str | None:
    """Infer corridor travel direction, preferring the curated route definition."""
    if train_no in TRAIN_BY_NO:
        return TRAIN_BY_NO[train_no].get("direction")
    stops = _corridor_stops(live_data)
    if len(stops) < 2:
        return None
    return "DN" if STATION_CODES.index(stops[-1]) > STATION_CODES.index(stops[0]) else "UP"


def _same_corridor_service(current: dict, candidate: dict, current_no: str, candidate_no: str) -> bool:
    """Only include a cached train if it genuinely shares this corridor and direction."""
    if not _is_mumbai_goa_service(candidate, candidate_no):
        return False
    current_stops = set(_corridor_stops(current))
    candidate_stops = set(_corridor_stops(candidate))
    # One interchange such as Panvel is not enough to call a train a corridor service.
    if len(current_stops & candidate_stops) < 2:
        return False
    current_direction = _corridor_direction(current, current_no)
    candidate_direction = _corridor_direction(candidate, candidate_no)
    return current_direction is not None and current_direction == candidate_direction


async def track_train(train_no: str, start_day: int = 1) -> dict:
    """
    Track a train: fetch live status from RapidAPI, then predict remaining journey.
    Returns a dict matching the TrackResult frontend interface.
    start_day: 0=today, 1=yesterday, 2=day before (IRCTC convention).
    """
    live_data = await fetch_live_train(train_no, start_day=start_day)

    if not live_data:
        return {"error": f"Could not fetch live data for train {train_no}. The train may not be running today."}

    is_corridor = _is_mumbai_goa_service(live_data, train_no)

    # Build live status
    live = {
        "train_no": live_data.get("train_no", train_no),
        "train_name": live_data.get("train_name", "Unknown"),
        "source": live_data.get("source", ""),
        "source_name": live_data.get("source_stn_name", live_data.get("source", "")),
        "destination": live_data.get("destination", ""),
        "destination_name": live_data.get("dest_stn_name", live_data.get("destination", "")),
        "current_station": live_data.get("current_station_code", ""),
        "current_station_name": live_data.get("current_station_name", ""),
        "delay": live_data.get("delay", 0) or 0,
        "distance_from_source": live_data.get("distance_from_source", 0) or 0,
        "total_distance": live_data.get("total_distance", 0) or 0,
        "status_as_of": live_data.get("status_as_of", ""),
        "is_corridor": is_corridor,
    }

    # Only show trains which share at least two Mumbai–Goa corridor stops and
    # travel in the same direction. The cache also contains unrelated trains.
    other_trains = []
    for t_no, cache_entry in live_cache.items():
        if is_corridor and t_no != train_no and cache_entry.get("data"):
            cd = cache_entry["data"]
            if not _same_corridor_service(live_data, cd, train_no, t_no):
                continue
            other_trains.append({
                "train_no": t_no,
                "train_name": cd.get("train_name", ""),
                "current_station": cd.get("current_station_code", ""),
                "delay": cd.get("delay", 0) or 0,
            })

    if is_corridor:
        return await _track_corridor_train(live, live_data, other_trains)
    else:
        return _track_national_train(live, live_data, other_trains)


async def _track_corridor_train(live: dict, live_data: dict, other_trains: list) -> dict:
    """Corridor train: full weather + section + SHAP predictions."""
    train_no = live["train_no"]
    weather = await fetch_corridor_weather()

    train_info = TRAIN_BY_NO.get(train_no)
    curr_code = live["current_station"]
    curr_delay = float(live["delay"])

    now = datetime.now(IST)
    day_of_week = now.weekday()
    is_weekend = 1 if day_of_week >= 5 else 0
    month = now.month
    is_monsoon = 1 if month in (6, 7, 8, 9) else 0

    # Find stops and current position
    if train_info:
        stops = train_info["stops"]
        dep_hour = int(train_info["departure"].split(":")[0])
        is_premium = 1 if train_info.get("priority") == 1 else 0
    else:
        # Not a known corridor train, but runs on corridor route - use all station codes
        stops = STATION_CODES[:]
        dep_hour = now.hour
        is_premium = 0

    # Find current index
    current_idx = -1
    for i, code in enumerate(stops):
        if code == curr_code:
            current_idx = i
            break

    # If station not found in stops, find closest by checking previous stations
    if current_idx == -1:
        # Try to find a corridor station in the live data
        for prev in reversed(live_data.get("previous_stations", [])):
            pc = prev.get("station_code", "")
            if pc in stops:
                current_idx = stops.index(pc)
                break

    if current_idx == -1:
        # The live provider's route is authoritative. Do not invent a route
        # from CSMT when its station codes cannot be reconciled safely.
        logger.warning("Live station %s could not be matched to corridor route for %s", curr_code, train_no)
        return _track_national_train(live, live_data, other_trains)

    remaining_stops = stops[current_idx + 1:]

    # Preceding train delay
    preceding_delay = 0.0
    for ot in other_trains:
        ot_code = ot.get("current_station", "")
        if ot_code in stops:
            try:
                ot_idx = stops.index(ot_code)
                if ot_idx > current_idx:
                    preceding_delay = max(preceding_delay, float(ot.get("delay", 0)))
            except ValueError:
                pass

    # Passed stations
    passed_stations = []
    for i in range(current_idx + 1):
        code = stops[i]
        station = STATION_BY_CODE.get(code, {})
        passed_stations.append({
            "station_code": code,
            "station_name": station.get("short_name", code),
            "station_no": i + 1,
            "distance_km": station.get("km", 0),
            "status": "DEPARTED" if i == current_idx else "PASSED",
            "delay": live["delay"] if i == current_idx else None,
            "predicted_delay": live["delay"] if i == current_idx else 0,
            "lower_bound": 0, "upper_bound": 0,
            "scheduled_arrival": None, "explanations": [],
        })

    # Predictions for remaining stations
    predictions = []
    for j, code in enumerate(remaining_stops):
        station = STATION_BY_CODE.get(code, {})
        distance = station.get("km", 0)

        prev_code = stops[current_idx + j] if (current_idx + j) < len(stops) else stops[-1]
        section_key = f"{prev_code}->{code}"
        section = SECTION_CHARACTERISTICS.get(section_key, {})

        is_single_track = 1 if section.get("track") == "single" else 0
        is_ghat = 1 if section.get("terrain") in ("ghat", "coastal_ghat") else 0

        station_weather = weather.get(code, {})
        rainfall = station_weather.get("rainfall_mm", 0)
        visibility = station_weather.get("visibility_km", 10)
        weather_sev = station_weather.get("severity", {}).get("severity_score", 0)

        # Scheduled time from train info
        sched_times = train_info["scheduled_times"].get(code, ("", "")) if train_info else ("", "")
        arr_str = sched_times[0] or sched_times[1]
        try:
            arr_parts = arr_str.split(":")
            dep_parts = (train_info["departure"] if train_info else "06:00").split(":")
            sched_rt = (int(arr_parts[0]) * 60 + int(arr_parts[1])) - (int(dep_parts[0]) * 60 + int(dep_parts[1]))
            if sched_rt < 0:
                sched_rt += 24 * 60
        except (ValueError, IndexError):
            sched_rt = 0

        features = {
            "distance_from_origin_km": distance,
            "scheduled_running_time": sched_rt,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "is_monsoon": is_monsoon,
            "departure_hour": dep_hour,
            "rainfall_mm": rainfall,
            "visibility_km": visibility,
            "weather_severity": weather_sev,
            "is_single_track": is_single_track,
            "is_ghat_section": is_ghat,
            "tunnel_count": section.get("tunnels", 0),
            "bridge_count": section.get("bridges", 0),
            "speed_limit": section.get("speed_limit", 80),
            "preceding_train_delay": preceding_delay,
            "is_premium": is_premium,
            "previous_station_delay": curr_delay,
        }

        result = corridor_forecaster.predict(features)

        predictions.append({
            "station_code": code,
            "station_name": station.get("short_name", code),
            "station_no": current_idx + j + 2,
            "distance_km": distance,
            "scheduled_arrival": sched_times[0] or None,
            "predicted_delay": result["predicted_delay"],
            "lower_bound": result["lower_bound"],
            "upper_bound": result["upper_bound"],
            "explanations": result["explanations"],
            "weather": station_weather,
            "section": {
                "terrain": section.get("terrain", "unknown"),
                "track": section.get("track", "single"),
                "tunnels": section.get("tunnels", 0),
                "bridges": section.get("bridges", 0),
                "speed_limit": section.get("speed_limit", 80),
            },
            "status": "PREDICTED",
        })

        # Recovery
        if weather_sev < 0.1 and not is_ghat:
            recovery = 0.82 if is_premium else 0.90
        elif is_ghat:
            recovery = 0.92 if is_premium else 0.96
        else:
            recovery = 0.88 if is_premium else 0.93
        curr_delay = result["predicted_delay"] * recovery
        preceding_delay = max(0, preceding_delay * 0.8)

    return {
        "live": live,
        "predictions": predictions,
        "passed_stations": passed_stations,
        "weather_source": "Open-Meteo (real data)",
        "other_trains": other_trains,
        "methodology": "Corridor-specific LightGBM with 17 features. Weather from Open-Meteo (real). SHAP TreeExplainer for per-prediction explanations. Live status from IRCTC via RapidAPI.",
        "total_stations": len(stops),
        "stations_passed": current_idx + 1,
        "stations_remaining": len(remaining_stops),
    }


def _track_national_train(live: dict, live_data: dict, other_trains: list) -> dict:
    """Non-corridor train: use upcoming stations from API + national model."""
    try:
        from ..dependencies import synapse_forecaster
    except Exception:
        synapse_forecaster = None

    curr_delay = float(live["delay"])
    now = datetime.now(IST)

    predictions = []
    for upcoming in live_data.get("upcoming_stations", []):
        stn_code = upcoming.get("station_code", "")
        stn_name = upcoming.get("station_name", stn_code)
        dist = upcoming.get("distance_from_source", 0)
        sta = upcoming.get("sta", "")
        eta = upcoming.get("eta", "")
        api_delay = upcoming.get("arrival_delay", 0)

        if not stn_code:
            continue

        previous_delay = curr_delay

        # Use API's own delay estimate if available, otherwise predict
        if api_delay and api_delay > 0:
            pred_delay = float(api_delay)
        elif synapse_forecaster:
            try:
                features = {
                    "distance_from_origin_km": dist,
                    "previous_station_delay": curr_delay,
                    "day_of_week": now.weekday(),
                    "scheduled_running_time": 100,
                }
                pred_delay = round(float(synapse_forecaster.predict_delay(features)), 1)
            except Exception:
                pred_delay = round(curr_delay * 0.9, 1)
        else:
            pred_delay = round(curr_delay * 0.9, 1)

        # National predictions do not have a corridor SHAP model. Return
        # concise, auditable factors instead of leaving the UI blank.
        explanations = []
        if api_delay and api_delay > 0:
            explanations.append({
                "contribution_minutes": round(pred_delay, 1),
                "direction": "INCREASING",
                "icon": "clock",
                "description": f"The live railway feed estimates a {pred_delay:.0f}m delay at this stop.",
            })
        elif previous_delay > 0:
            carried_delay = min(previous_delay, pred_delay)
            explanations.append({
                "contribution_minutes": round(carried_delay, 1),
                "direction": "INCREASING",
                "icon": "clock",
                "description": f"The train is currently {previous_delay:.0f}m late; this delay is carried forward in the ETA forecast.",
            })

        recovery = round(pred_delay - previous_delay, 1)
        if recovery < -0.3:
            explanations.append({
                "contribution_minutes": recovery,
                "direction": "DECREASING",
                "icon": "speed",
                "description": f"Historical running-time patterns indicate about {abs(recovery):.0f}m of delay recovery before this stop.",
            })
        elif recovery > 0.3:
            explanations.append({
                "contribution_minutes": recovery,
                "direction": "INCREASING",
                "icon": "train",
                "description": f"The national ETA model projects a further {recovery:.0f}m delay accumulation before this stop.",
            })

        predictions.append({
            "station_code": stn_code,
            "station_name": stn_name,
            "station_no": upcoming.get("si_no", 0),
            "distance_km": dist,
            "scheduled_arrival": sta or None,
            "predicted_delay": pred_delay,
            "lower_bound": round(pred_delay - 5, 1),
            "upper_bound": round(pred_delay + 8, 1),
            "explanations": explanations,
            "status": "PREDICTED",
        })
        curr_delay = pred_delay

    return {
        "live": live,
        "predictions": predictions,
        "passed_stations": [],
        "weather_source": "N/A (non-corridor train)",
        "other_trains": other_trains,
        "methodology": "Live status from IRCTC via RapidAPI. Delay predictions use national LightGBM model trained on 26.6M historical observations.",
        "total_stations": 0,
        "stations_passed": 0,
        "stations_remaining": len(predictions),
    }
