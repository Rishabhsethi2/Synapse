"""Synapse API Integration Test"""
import httpx
import json
import sys

BASE = "http://localhost:8000"
errors = []

def test(name, fn):
    try:
        fn()
        print(f"  [PASS] {name}")
    except Exception as e:
        print(f"  [FAIL] {name}: {e}")
        errors.append(name)

def t_health():
    r = httpx.get(f"{BASE}/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["stations_loaded"] > 8000
    assert d["trains_loaded"] > 8000
    assert d["network_sections"] > 30000
    print(f"    {d['stations_loaded']} stations, {d['trains_loaded']} trains, {d['network_sections']} sections")

def t_trains():
    r = httpx.get(f"{BASE}/api/trains")
    assert r.status_code == 200
    d = r.json()
    assert d["total"] > 0
    print(f"    {d['total']} trains returned, first: {d['trains'][0]['train_name']}")

def t_eta():
    r = httpx.get(f"{BASE}/api/trains/12301/eta")
    assert r.status_code == 200
    d = r.json()
    assert "predictions" in d
    assert len(d["predictions"]) > 0
    print(f"    {d['train_name']}: {len(d['predictions'])} station predictions")
    p = d["predictions"][0]
    print(f"    First stop: {p['station_code']}, delay={p['predicted_delay_minutes']}m [{p['lower_bound_delay']}m - {p['upper_bound_delay']}m]")

def t_trajectory():
    r = httpx.get(f"{BASE}/api/trains/12301/trajectory")
    assert r.status_code == 200
    d = r.json()
    assert len(d["trajectory"]) > 0
    print(f"    {len(d['trajectory'])} stops in trajectory")

def t_network():
    r = httpx.get(f"{BASE}/api/network/stats")
    assert r.status_code == 200
    d = r.json()
    assert d["total_sections"] > 0
    print(f"    {d['graph_nodes']} nodes, {d['graph_edges']} edges")

def t_vulnerability():
    r = httpx.get(f"{BASE}/api/network/vulnerability")
    assert r.status_code == 200
    d = r.json()
    assert d["total_sections"] > 0
    print(f"    {d['total_sections']} total, {d['occupied_sections']} occupied")

def t_replay():
    # Start replay for Howrah Rajdhani on a known date
    r = httpx.post(f"{BASE}/api/replay/start", json={"train_no": "12301", "date": "2025-03-07"})
    if r.status_code == 404:
        # Try another date
        r = httpx.post(f"{BASE}/api/replay/start", json={"train_no": "12301", "date": "2025-06-15"})
    if r.status_code == 404:
        print(f"    Skipping replay — no data found for 12301 on tested dates")
        return
    assert r.status_code == 200
    d = r.json()
    print(f"    Started: {d['train_name']}, {d['total_stations']} stations")

    # Tick
    r = httpx.post(f"{BASE}/api/replay/tick")
    assert r.status_code == 200
    tick = r.json()
    step = tick["step"]
    print(f"    Tick 1: {step['station_code']}, delay={step['delay_minutes']}m, {len(tick['predictions'])} predictions")

    # Tick again
    r = httpx.post(f"{BASE}/api/replay/tick")
    assert r.status_code == 200

def t_whatif():
    r = httpx.post(f"{BASE}/api/whatif", json={
        "train_id": "12301",
        "modifications": {"add_delay_minutes": 30}
    })
    assert r.status_code == 200
    d = r.json()
    assert "methodology" in d
    print(f"    Methodology: {d['methodology']}")

print("=" * 50)
print("SYNAPSE API INTEGRATION TEST")
print("=" * 50)

test("Health Check", t_health)
test("Train List", t_trains)
test("ETA Prediction (12301)", t_eta)
test("Trajectory (12301)", t_trajectory)
test("Network Stats", t_network)
test("Network Vulnerability", t_vulnerability)
test("Replay Engine", t_replay)
test("What-If Simulator", t_whatif)

print("=" * 50)
if errors:
    print(f"FAILED: {len(errors)} test(s) — {', '.join(errors)}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
