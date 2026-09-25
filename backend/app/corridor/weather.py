"""
Mumbai-Goa Corridor - Real Weather Service (Open-Meteo)

Fetches real weather data for corridor stations using Open-Meteo API.
No API key needed. Free. Real data.
"""
import logging
import httpx
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from .data import CORRIDOR_STATIONS, STATION_BY_CODE

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# Cache weather data to avoid repeated API calls
_weather_cache: dict[str, dict] = {}
_cache_timestamp: Optional[datetime] = None
CACHE_TTL_SECONDS = 600  # Refresh every 10 minutes


def _weather_code_to_condition(code: int) -> str:
    """Convert WMO weather code to human-readable condition."""
    if code == 0:
        return "Clear"
    elif code in (1, 2, 3):
        return "Partly Cloudy" if code <= 2 else "Overcast"
    elif code in (45, 48):
        return "Fog"
    elif code in (51, 53, 55):
        return "Drizzle"
    elif code in (61, 63):
        return "Rain"
    elif code == 65:
        return "Heavy Rain"
    elif code in (71, 73, 75):
        return "Snow"
    elif code in (80, 81, 82):
        return "Rain Showers" if code <= 81 else "Heavy Showers"
    elif code in (95, 96, 99):
        return "Thunderstorm"
    else:
        return "Unknown"


def _weather_severity(condition: str, rainfall_mm: float, visibility_km: float) -> dict:
    """Compute weather severity score and impact description."""
    score = 0.0
    factors = []

    if rainfall_mm > 50:
        score += 0.8
        factors.append(f"Very heavy rain ({rainfall_mm:.0f}mm/hr)")
    elif rainfall_mm > 20:
        score += 0.5
        factors.append(f"Heavy rain ({rainfall_mm:.0f}mm/hr)")
    elif rainfall_mm > 5:
        score += 0.2
        factors.append(f"Moderate rain ({rainfall_mm:.0f}mm/hr)")
    elif rainfall_mm > 0:
        score += 0.05
        factors.append(f"Light rain ({rainfall_mm:.1f}mm/hr)")

    if visibility_km < 1:
        score += 0.5
        factors.append(f"Very poor visibility ({visibility_km:.1f}km)")
    elif visibility_km < 3:
        score += 0.3
        factors.append(f"Low visibility ({visibility_km:.1f}km)")
    elif visibility_km < 5:
        score += 0.1
        factors.append(f"Reduced visibility ({visibility_km:.0f}km)")

    if "Thunderstorm" in condition:
        score += 0.4
        factors.append("Thunderstorm activity")

    score = min(score, 1.0)
    level = "SEVERE" if score > 0.6 else "MODERATE" if score > 0.3 else "MILD" if score > 0.1 else "CLEAR"

    return {
        "severity_score": round(score, 2),
        "severity_level": level,
        "factors": factors,
    }


async def fetch_corridor_weather() -> dict[str, dict]:
    """
    Fetch current weather for ALL corridor stations from Open-Meteo.
    Returns dict of station_code -> weather_data.
    """
    global _weather_cache, _cache_timestamp

    # Check cache
    now = datetime.now(IST)
    if _cache_timestamp and (now - _cache_timestamp).total_seconds() < CACHE_TTL_SECONDS:
        return _weather_cache

    logger.info("Fetching real weather from Open-Meteo for %d corridor stations...", len(CORRIDOR_STATIONS))

    result = {}

    # Open-Meteo supports multiple locations in one call
    lats = ",".join(str(s["lat"]) for s in CORRIDOR_STATIONS)
    lons = ",".join(str(s["lon"]) for s in CORRIDOR_STATIONS)

    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lats}&longitude={lons}"
        f"&current=temperature_2m,relative_humidity_2m,rain,weather_code,wind_speed_10m,visibility"
        f"&timezone=Asia/Kolkata"
    )

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()

        # Open-Meteo returns an array when multiple locations are queried
        if isinstance(data, list):
            weather_list = data
        else:
            # Single location returns a dict
            weather_list = [data]

        for i, station in enumerate(CORRIDOR_STATIONS):
            if i >= len(weather_list):
                break

            current = weather_list[i].get("current", {})
            weather_code = current.get("weather_code", 0)
            condition = _weather_code_to_condition(weather_code)
            rainfall = current.get("rain", 0) or 0
            # Open-Meteo visibility is in meters, convert to km
            vis_m = current.get("visibility", 10000) or 10000
            visibility_km = vis_m / 1000.0

            severity = _weather_severity(condition, rainfall, visibility_km)

            result[station["code"]] = {
                "station_code": station["code"],
                "station_name": station["short_name"],
                "temperature_c": current.get("temperature_2m", 0),
                "humidity_pct": current.get("relative_humidity_2m", 0),
                "rainfall_mm": rainfall,
                "wind_speed_kmh": current.get("wind_speed_10m", 0),
                "visibility_km": round(visibility_km, 1),
                "weather_code": weather_code,
                "condition": condition,
                "severity": severity,
                "timestamp": current.get("time", now.isoformat()),
                "source": "Open-Meteo (real data)",
            }

        _weather_cache = result
        _cache_timestamp = now
        logger.info("Weather fetched: %d stations", len(result))

    except Exception as e:
        logger.error("Failed to fetch weather: %s", e)
        # Return cached data or empty
        if _weather_cache:
            logger.info("Using cached weather data")
            return _weather_cache

        # Generate fallback
        for station in CORRIDOR_STATIONS:
            result[station["code"]] = {
                "station_code": station["code"],
                "station_name": station["short_name"],
                "temperature_c": 28,
                "humidity_pct": 70,
                "rainfall_mm": 0,
                "wind_speed_kmh": 10,
                "visibility_km": 10.0,
                "weather_code": 0,
                "condition": "Clear",
                "severity": {"severity_score": 0, "severity_level": "CLEAR", "factors": []},
                "timestamp": now.isoformat(),
                "source": "FALLBACK (API unreachable)",
            }

    return result


def fetch_corridor_weather_sync() -> dict[str, dict]:
    """Synchronous version for use in non-async contexts."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, use a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(lambda: asyncio.run(fetch_corridor_weather())).result()
        return loop.run_until_complete(fetch_corridor_weather())
    except RuntimeError:
        return asyncio.run(fetch_corridor_weather())
