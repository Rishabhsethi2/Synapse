"""Test the Live Predict endpoint."""
import httpx
import json

r = httpx.post(
    "http://localhost:8000/api/predict/live",
    json={"train_no": "12301", "last_station": "DHN", "delay_minutes": 25},
)

d = r.json()
print("Status:", r.status_code)

if r.status_code != 200:
    print("Error:", d)
else:
    print(f"Train: {d['train_name']} ({d['train_no']})")
    print(f"Last Station: {d['last_station_full_name']} ({d['last_station']})")
    print(f"Input Delay: {d['input_delay_minutes']}m")
    print(f"Stations: {d['stations_passed']} passed, {d['stations_remaining']} remaining")
    print()
    print("Predictions:")
    for p in d["predictions"]:
        delay = p["predicted_delay_minutes"]
        lb = p["lower_bound"]
        ub = p["upper_bound"]
        marker = "***" if delay > 30 else "**" if delay > 15 else "*" if delay > 5 else ""
        print(f"  #{p['station_no']:2d} {p['station_code']:6s}  {p.get('scheduled_arrival', ''):>8s}  "
              f"delay={delay:+6.1f}m  [{lb:.0f}m - {ub:.0f}m] {marker}")
    print()
    print("Methodology:", d["methodology"])

# Test station search
print("\n--- Station Search ---")
r2 = httpx.get("http://localhost:8000/api/stations/search?q=NDLS")
print("NDLS search:", json.dumps(r2.json(), indent=2))

# Test train search
print("\n--- Train Search ---")
r3 = httpx.get("http://localhost:8000/api/trains/search?q=12301")
print("12301 search:", json.dumps(r3.json(), indent=2))
