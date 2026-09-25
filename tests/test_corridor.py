"""Test the corridor prediction API."""
import httpx
import json

BASE = "http://localhost:8000/api/corridor"

# 1. Test corridor stations
print("=== Corridor Stations ===")
r = httpx.get(f"{BASE}/stations")
d = r.json()
print(f"  {d['count']} stations: {', '.join(s['code'] for s in d['stations'])}")

# 2. Test corridor trains
print("\n=== Corridor Trains ===")
r = httpx.get(f"{BASE}/trains")
for t in r.json()["trains"]:
    print(f"  {t['train_no']} {t['name']} ({t['type']}) {t['direction']}")

# 3. Test weather (real from Open-Meteo!)
print("\n=== Real Weather ===")
r = httpx.get(f"{BASE}/weather")
wx = r.json()
for code, w in wx["weather"].items():
    sev = w["severity"]["severity_level"]
    print(f"  {code:5s} | {w['condition']:15s} | {w['temperature_c']}C | Rain: {w['rainfall_mm']}mm | Vis: {w['visibility_km']}km | {sev}")
print(f"  Source: {wx['source']}")

# 4. Add another train on track for interaction demo
print("\n=== Setting up train interaction ===")
r = httpx.post(f"{BASE}/update-train", json={
    "train_no": "10103",
    "current_station": "RN",
    "current_delay": 22
})
print(f"  Updated 10103 (Mandovi) at Ratnagiri with 22m delay")

# 5. Run corridor prediction
print("\n=== Corridor Prediction ===")
r = httpx.post(f"{BASE}/predict", json={
    "train_no": "22119",
    "current_station": "PNVL",
    "current_delay": 15
})
if r.status_code != 200:
    print(f"  ERROR {r.status_code}: {r.json()}")
else:
    d = r.json()
    print(f"  Train: {d['train_name']} ({d['train_no']})")
    print(f"  Current: {d['current_station_name']} | Delay: {d['input_delay']}m")
    print(f"  Weather: {d['weather_source']}")
    print(f"  Trains on track: {len(d['trains_on_track'])}")
    print()

    for p in d["predictions"]:
        delay = p["predicted_delay"]
        lb = p["lower_bound"]
        ub = p["upper_bound"]
        wx = p["weather"]
        sec = p["section"]
        expl_count = len(p["explanations"])

        print(f"  {p['station_code']:5s} ({p['station_name']:15s}) | "
              f"delay={delay:+6.1f}m [{lb:.0f}-{ub:.0f}m] | "
              f"weather={wx.get('condition', 'N/A'):12s} | "
              f"terrain={sec['terrain']:10s} | "
              f"{expl_count} explanations")

        # Show top explanations
        for e in p["explanations"][:3]:
            print(f"       -> [{e['icon']}] {e['description']}")
        if expl_count > 3:
            print(f"       ... +{expl_count - 3} more")
        print()
