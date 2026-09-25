"""Quick test: verify delay recovery in corridor predictions."""
import httpx

BASE = "http://localhost:8000/api/corridor"

# Tejas (premium) starting with 30m delay at PNVL - should recover
r = httpx.post(f"{BASE}/predict", json={
    "train_no": "22119",
    "current_station": "PNVL",
    "current_delay": 30,
})
d = r.json()
print(f"=== {d['train_name']} ({d['train_type']}) ===")
print(f"Input delay at {d['current_station_name']}: {d['input_delay']}m")
print()
for p in d["predictions"]:
    bar = "#" * max(0, int(p["predicted_delay"]))
    print(f"  {p['station_code']:5s} {p['station_name']:15s} | {p['predicted_delay']:+6.1f}m [{p['lower_bound']:.0f}-{p['upper_bound']:.0f}m] {bar}")

first_delay = d["predictions"][0]["predicted_delay"]
last_delay = d["predictions"][-1]["predicted_delay"]
recovery = first_delay - last_delay
print(f"\nRecovery: {first_delay:.1f}m -> {last_delay:.1f}m = {recovery:.1f}m recovered")
print(f"Recovery %: {recovery/first_delay*100:.0f}%" if first_delay > 0 else "")

# Also test Mandovi (regular) - should recover less
print()
r2 = httpx.post(f"{BASE}/predict", json={
    "train_no": "10103",
    "current_station": "PNVL",
    "current_delay": 30,
})
d2 = r2.json()
print(f"=== {d2['train_name']} ({d2['train_type']}) ===")
print(f"Input delay at {d2['current_station_name']}: {d2['input_delay']}m")
print()
for p in d2["predictions"]:
    bar = "#" * max(0, int(p["predicted_delay"]))
    print(f"  {p['station_code']:5s} {p['station_name']:15s} | {p['predicted_delay']:+6.1f}m [{p['lower_bound']:.0f}-{p['upper_bound']:.0f}m] {bar}")

first_delay2 = d2["predictions"][0]["predicted_delay"]
last_delay2 = d2["predictions"][-1]["predicted_delay"]
recovery2 = first_delay2 - last_delay2
print(f"\nRecovery: {first_delay2:.1f}m -> {last_delay2:.1f}m = {recovery2:.1f}m recovered")
