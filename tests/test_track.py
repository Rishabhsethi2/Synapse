"""
End-to-end test for the new /api/corridor/track endpoint.
Tests both a corridor train and a non-corridor train.
"""
import httpx, json

BASE = "http://localhost:8000/api"

def divider(title):
    print(f"\n{'='*55}")
    print(f"  {title}")
    print('='*55)

# --- Test 1: Corridor train (Mandovi Express) ---
divider("Test 1: Corridor Train (10103 Mandovi Express)")
r = httpx.post(f"{BASE}/corridor/track", json={"train_no": "10103"}, timeout=20)
print(f"Status: {r.status_code}")

if r.status_code == 200:
    d = r.json()
    live = d["live"]
    print(f"  Train: {live['train_name']} ({live['train_no']})")
    print(f"  Route: {live['source_name']} -> {live['destination_name']}")
    print(f"  At: {live['current_station_name']} ({live['current_station']})")
    print(f"  Delay: {live['delay']}m")
    print(f"  Is corridor: {live['is_corridor']}")
    print(f"  Weather source: {d.get('weather_source')}")
    print(f"  Other trains: {len(d.get('other_trains', []))}")
    print(f"  Predictions: {len(d.get('predictions', []))}")
    for p in d.get("predictions", [])[:3]:
        expl_n = len(p.get("explanations", []))
        wx = p.get("weather", {})
        print(f"    {p['station_code']:6s} {p.get('station_name',''):15s} | "
              f"+{p['predicted_delay']}m [{p['lower_bound']}-{p['upper_bound']}m] | "
              f"weather={wx.get('condition','N/A'):12s} | {expl_n} explanations")
        for e in p.get("explanations", [])[:2]:
            print(f"      -> {e['description'][:60]}")
else:
    print(f"  ERROR: {r.json()}")

# --- Test 2: Non-corridor train ---
divider("Test 2: Non-Corridor Train (19038 Avadh Express)")
r2 = httpx.post(f"{BASE}/corridor/track", json={"train_no": "19038"}, timeout=20)
print(f"Status: {r2.status_code}")

if r2.status_code == 200:
    d2 = r2.json()
    live2 = d2["live"]
    print(f"  Train: {live2['train_name']} ({live2['train_no']})")
    print(f"  Route: {live2['source_name']} -> {live2['destination_name']}")
    print(f"  At: {live2['current_station_name']} ({live2['current_station']})")
    print(f"  Delay: {live2['delay']}m")
    print(f"  Is corridor: {live2['is_corridor']}")
    print(f"  Predictions: {len(d2.get('predictions', []))}")
    print(f"  Methodology: {d2.get('methodology', '')[:80]}")
    for p in d2.get("predictions", [])[:4]:
        print(f"    {p['station_code']:6s} {p.get('station_name',''):20s} | +{p['predicted_delay']}m")
else:
    print(f"  ERROR: {r2.json()}")

# --- Test 3: Invalid train ---
divider("Test 3: Invalid Train")
r3 = httpx.post(f"{BASE}/corridor/track", json={"train_no": "99999"}, timeout=20)
print(f"Status: {r3.status_code} (expected 400)")
print(f"  Detail: {r3.json().get('detail', '')}")

print("\n\nAll tests complete.")
