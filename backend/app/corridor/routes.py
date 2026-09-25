"""
Mumbai-Goa Corridor - API Routes

Endpoints for corridor-specific predictions with:
- Real weather from Open-Meteo
- Train-on-track awareness
- SHAP-based explainability per station
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .data import CORRIDOR_STATIONS, CORRIDOR_TRAINS, STATION_BY_CODE, TRAIN_BY_NO, SECTION_CHARACTERISTICS
from .weather import fetch_corridor_weather
from .model import CorridorForecaster
from .tracker import track_train
from .live_api import QuotaExceededError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/corridor", tags=["corridor"])
IST = ZoneInfo("Asia/Kolkata")

# Initialize corridor forecaster (loads models if available)
corridor_forecaster = CorridorForecaster()

# Simulated train positions (in production, this comes from scraping)
_live_trains: dict[str, dict] = {}


class CorridorPredictRequest(BaseModel):
    train_no: str
    current_station: str  # Station code where train was last seen
    current_delay: float  # Delay in minutes at that station


class LiveTrainUpdate(BaseModel):
    train_no: str
    current_station: str
    current_delay: float


@router.get("/stations")
def get_corridor_stations():
    """Get all stations on the Mumbai-Goa corridor."""
    return {"stations": CORRIDOR_STATIONS, "count": len(CORRIDOR_STATIONS)}


@router.get("/trains")
def get_corridor_trains():
    """Get all trains running on this corridor."""
    trains = []
    for t in CORRIDOR_TRAINS:
        live = _live_trains.get(t["train_no"])
        trains.append({
            **t,
            "live_status": live or {"status": "NOT_TRACKED"},
        })
    return {"trains": trains, "count": len(trains)}


@router.get("/weather")
async def get_corridor_weather():
    """Get REAL current weather for all corridor stations."""
    weather = await fetch_corridor_weather()
    return {
        "weather": weather,
        "count": len(weather),
        "source": "Open-Meteo (real data)",
    }

class TrackRequest(BaseModel):
    train_no: str = Field(pattern=r"^\d{5}$")
    start_day: int = Field(default=1, ge=0, le=2)  # IRCTC supports only the last 3 start days

@router.post("/track")
async def track_train_endpoint(req: TrackRequest):
    """
    Track a train using live API data and models.
    Accepts start_day to handle trains that only run on specific days (e.g. 0=today, 1=yesterday).
    """
    try:
        result = await track_train(req.train_no, start_day=req.start_day)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        return result
    except QuotaExceededError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Live API quota exceeded: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("track_train failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/predict")
async def predict_corridor(req: CorridorPredictRequest):
    """
    Main prediction endpoint.

    Given a train number, current station, and current delay:
    1. Fetch real weather for remaining stations
    2. Check other trains on the corridor
    3. Predict delay at each remaining station with SHAP explanations
    """
    train_no = req.train_no.strip()
    current_station = req.current_station.strip().upper()

    # Find train
    train_info = TRAIN_BY_NO.get(train_no)
    if not train_info:
        raise HTTPException(404, f"Train {train_no} not found on Mumbai-Goa corridor. Available: {list(TRAIN_BY_NO.keys())}")

    stops = train_info["stops"]

    # Find current position
    current_idx = -1
    for i, code in enumerate(stops):
        if code == current_station:
            current_idx = i
            break

    if current_idx == -1:
        raise HTTPException(
            404,
            f"Station {current_station} not in route for train {train_no}. "
            f"Stops: {stops}"
        )

    # Fetch real weather
    weather = await fetch_corridor_weather()

    # Get other trains on corridor for preceding train awareness
    preceding_delay = 0.0
    trains_on_track = []
    for tn, live in _live_trains.items():
        if tn != train_no and live.get("current_station"):
            trains_on_track.append(live)
            # Check if this train is ahead on the same direction
            t_info = TRAIN_BY_NO.get(tn, {})
            if t_info.get("direction") == train_info.get("direction"):
                live_station = live.get("current_station", "")
                try:
                    live_idx = stops.index(live_station)
                    if live_idx > current_idx:
                        preceding_delay = max(preceding_delay, live.get("delay", 0))
                except ValueError:
                    pass

    # Update live state for this train
    _live_trains[train_no] = {
        "train_no": train_no,
        "train_name": train_info["name"],
        "current_station": current_station,
        "delay": req.current_delay,
        "direction": train_info.get("direction", "DN"),
        "updated_at": datetime.now(IST).isoformat(),
        "status": "TRACKING",
    }

    now = datetime.now(IST)
    day_of_week = now.weekday()
    is_weekend = 1 if day_of_week >= 5 else 0
    month = now.month
    is_monsoon = 1 if month in (6, 7, 8, 9) else 0
    dep_hour = int(train_info["departure"].split(":")[0])

    # Build predictions for remaining stations
    remaining_stops = stops[current_idx + 1:]
    current_delay = req.current_delay

    # Passed stations
    passed = []
    for i in range(current_idx + 1):
        code = stops[i]
        station = STATION_BY_CODE.get(code, {})
        passed.append({
            "station_code": code,
            "station_name": station.get("short_name", code),
            "station_no": i + 1,
            "distance_km": station.get("km", 0),
            "status": "DEPARTED" if i == current_idx else "PASSED",
            "delay": req.current_delay if i == current_idx else None,
            "weather": weather.get(code),
        })

    # Predicted stations
    predictions = []
    for j, code in enumerate(remaining_stops):
        station = STATION_BY_CODE.get(code, {})
        distance = station.get("km", 0)
        section_type = station.get("section_type", "coastal")

        # Get section characteristics
        prev_code = stops[current_idx + j] if (current_idx + j) < len(stops) else stops[-1]
        section_key = f"{prev_code}->{code}"
        section = SECTION_CHARACTERISTICS.get(section_key, {})

        is_single_track = 1 if section.get("track") == "single" else 0
        is_ghat = 1 if section.get("terrain") in ("ghat", "coastal_ghat") else 0

        # Get real weather at this station
        station_weather = weather.get(code, {})
        rainfall = station_weather.get("rainfall_mm", 0)
        visibility = station_weather.get("visibility_km", 10)
        weather_sev = station_weather.get("severity", {}).get("severity_score", 0)

        # Scheduled running time
        sched_times = train_info["scheduled_times"].get(code, ("", ""))
        arr_str = sched_times[0] or sched_times[1]
        try:
            arr_parts = arr_str.split(":")
            dep_parts = train_info["departure"].split(":")
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
            "is_premium": 1 if train_info.get("priority") == 1 else 0,
            "previous_station_delay": current_delay,
        }

        result = corridor_forecaster.predict(features)

        predictions.append({
            "station_code": code,
            "station_name": station.get("short_name", code),
            "station_full_name": station.get("name", code),
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

        # Chain prediction forward with recovery factor
        # Real trains recover delay by reducing dwell time and adjusting speed
        is_premium_train = train_info.get("priority") == 1
        if weather_sev < 0.1 and not is_ghat:
            # Clear weather, non-ghat: strong recovery
            recovery_rate = 0.82 if is_premium_train else 0.90
        elif is_ghat:
            # Ghat section: mild recovery (can't speed up much)
            recovery_rate = 0.92 if is_premium_train else 0.96
        else:
            # Bad weather on non-ghat: moderate recovery
            recovery_rate = 0.88 if is_premium_train else 0.93
        current_delay = result["predicted_delay"] * recovery_rate
        # Preceding delay reduces as we go further
        preceding_delay = max(0, preceding_delay * 0.8)

    return {
        "train_no": train_no,
        "train_name": train_info["name"],
        "train_type": train_info["type"],
        "direction": train_info.get("direction", "DN"),
        "current_station": current_station,
        "current_station_name": STATION_BY_CODE.get(current_station, {}).get("short_name", current_station),
        "input_delay": req.current_delay,
        "total_stations": len(stops),
        "stations_passed": current_idx + 1,
        "stations_remaining": len(remaining_stops),
        "prediction_time": now.isoformat(),
        "model_info": corridor_forecaster.get_model_info(),
        "weather_source": "Open-Meteo (real data)",
        "trains_on_track": trains_on_track,
        "passed_stations": passed,
        "predictions": predictions,
        "methodology": (
            "Corridor-specific LightGBM with 17 features. "
            "Weather from Open-Meteo (real). "
            "SHAP TreeExplainer for per-prediction explanations. "
            "Chained predictions with delay propagation."
        ),
    }


@router.post("/update-train")
def update_live_train(req: LiveTrainUpdate):
    """Update live position of a train on the corridor (for demo/scraping)."""
    train_info = TRAIN_BY_NO.get(req.train_no)
    name = train_info["name"] if train_info else "Unknown"

    _live_trains[req.train_no] = {
        "train_no": req.train_no,
        "train_name": name,
        "current_station": req.current_station.upper(),
        "delay": req.current_delay,
        "direction": train_info.get("direction", "DN") if train_info else "DN",
        "updated_at": datetime.now(IST).isoformat(),
        "status": "TRACKING",
    }
    return {"status": "updated", "trains_tracked": len(_live_trains)}


@router.get("/live-trains")
def get_live_trains():
    """Get all currently tracked trains on the corridor."""
    return {"trains": list(_live_trains.values()), "count": len(_live_trains)}


@router.get("/sections")
def get_corridor_sections():
    """Get all section characteristics."""
    sections = []
    for key, info in SECTION_CHARACTERISTICS.items():
        fr, to = key.split("->")
        fr_station = STATION_BY_CODE.get(fr, {})
        to_station = STATION_BY_CODE.get(to, {})
        sections.append({
            "section_id": key,
            "from_station": fr,
            "from_name": fr_station.get("short_name", fr),
            "to_station": to,
            "to_name": to_station.get("short_name", to),
            **info,
        })
    return {"sections": sections}
