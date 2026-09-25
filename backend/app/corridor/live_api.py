import os
import time
import logging
import httpx
from typing import Optional, Dict
from pathlib import Path
from dotenv import load_dotenv
from .data import STATION_CODES

logger = logging.getLogger(__name__)

# Load .env from backend directory
_env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_path)

RAPIDAPI_KEY = os.environ.get('RAPIDAPI_KEY')
RAPIDAPI_HOST = os.environ.get('RAPIDAPI_HOST', 'irctc1.p.rapidapi.com')

_cache: Dict[str, Dict] = {}
CACHE_TTL = 60


class QuotaExceededError(Exception):
    """Raised when the RapidAPI monthly quota is exceeded (HTTP 429)."""
    pass

async def fetch_live_train(train_no: str, start_day: int = 1) -> Optional[dict]:
    now = time.time()
    if train_no in _cache:
        if now - _cache[train_no]["time"] < CACHE_TTL:
            return _cache[train_no]["data"]

    if not RAPIDAPI_KEY:
        logger.warning("RAPIDAPI_KEY not found in environment.")
        return None

    url = f"https://{RAPIDAPI_HOST}/api/v1/liveTrainStatus"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    # Try start_day values: the provided one first, then others (0=today, 1=yesterday, 2=day before)
    days_to_try = [start_day] + [d for d in [0, 1, 2] if d != start_day]

    for day in days_to_try:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers, params={"trainNo": train_no, "startDay": day})

                # Detect quota exceeded before calling raise_for_status
                if response.status_code == 429:
                    raise QuotaExceededError("RapidAPI monthly quota exceeded. Please upgrade your plan at rapidapi.com or wait until next month.")

                response.raise_for_status()
                data = response.json()

                if data.get("status") and data.get("data", {}).get("success"):
                    raw = data["data"]

                    curr_name = raw.get("current_station_name", "").rstrip("~")

                    up_stns = []
                    for stn in raw.get("upcoming_stations", []):
                        stn_copy = stn.copy()
                        stn_copy["station_name"] = stn_copy.get("station_name", "").rstrip("~")
                        up_stns.append(stn_copy)

                    prev_stns = []
                    for stn in raw.get("previous_stations", []):
                        stn_copy = stn.copy()
                        stn_copy["station_name"] = stn_copy.get("station_name", "").rstrip("~")
                        prev_stns.append(stn_copy)

                    result = {
                        "train_no": raw.get("train_number"),
                        "train_name": raw.get("train_name"),
                        "source": raw.get("source"),
                        "destination": raw.get("destination"),
                        "source_stn_name": raw.get("source_stn_name", ""),
                        "dest_stn_name": raw.get("dest_stn_name", ""),
                        "current_station_code": raw.get("current_station_code"),
                        "current_station_name": curr_name,
                        "delay": raw.get("delay"),
                        "distance_from_source": raw.get("distance_from_source"),
                        "total_distance": raw.get("total_distance"),
                        "status_as_of": raw.get("status_as_of"),
                        "upcoming_stations": up_stns,
                        "previous_stations": prev_stns
                    }

                    _cache[train_no] = {"time": now, "data": result}
                    return result

        except QuotaExceededError:
            # Preserve this condition so the route can return a useful 503
            # instead of incorrectly reporting that the train is not running.
            raise
        except Exception as e:
            logger.warning("Error fetching train %s with startDay=%d: %s", train_no, day, e)

    return None
        
def is_corridor_train(train_data: dict) -> bool:
    if not train_data:
        return False
    stations = []
    for s in train_data.get("previous_stations", []):
        stations.append(s.get("station_code"))
    stations.append(train_data.get("current_station_code"))
    for s in train_data.get("upcoming_stations", []):
        stations.append(s.get("station_code"))
        
    return any(s in STATION_CODES for s in stations if s)
