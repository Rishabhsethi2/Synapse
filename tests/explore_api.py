"""Explore the IRCTC RapidAPI response format."""
import httpx, json

API_KEY = "f178b412bdmshcf6fb36da84a909p15a00fjsnffa3ed5a185d"
HEADERS = {
    "Content-Type": "application/json",
    "x-rapidapi-host": "irctc1.p.rapidapi.com",
    "x-rapidapi-key": API_KEY,
}

# Test with a Mumbai-Goa train
r = httpx.get(
    "https://irctc1.p.rapidapi.com/api/v1/liveTrainStatus?trainNo=10103&startDay=1",
    headers=HEADERS, timeout=15,
)
d = r.json()
data = d.get("data", {})

print("=== Train Info ===")
print(f"  Train: {data.get('train_number')} {data.get('train_name')}")
print(f"  Source: {data.get('source')} ({data.get('source_stn_name')})")
print(f"  Dest: {data.get('destination')} ({data.get('dest_stn_name')})")
print(f"  Status: {data.get('status')}")
print(f"  Current Station: {data.get('current_station_code')} ({data.get('current_station_name')})")
print(f"  Delay: {data.get('delay')} minutes")
print(f"  Distance from source: {data.get('distance_from_source')}/{data.get('total_distance')} km")
print(f"  Update: {data.get('status_as_of')}")

print("\n=== Upcoming Stations ===")
upcoming = data.get("upcoming_stations", [])
for st in upcoming[:5]:
    if st.get("station_code"):
        print(f"  {st.get('station_code'):6s} {st.get('station_name'):20s} | "
              f"sta={st.get('sta')} eta={st.get('eta')} | "
              f"delay={st.get('arrival_delay')}m | "
              f"dist={st.get('distance_from_source')}km")

print("\n=== Previous Stations ===")
prev = data.get("previous_stations", [])
for st in prev[-5:]:
    if st.get("station_code"):
        print(f"  {st.get('station_code'):6s} {st.get('station_name'):20s} | "
              f"sta={st.get('sta')} actual={st.get('actual_arrival', 'N/A')} | "
              f"delay={st.get('delay', 'N/A')}m | "
              f"dist={st.get('distance_from_source')}km")

print("\n=== Raw keys ===")
print("  Data keys:", list(data.keys())[:30])
