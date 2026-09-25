"""
Mumbai-Goa Konkan Railway Corridor - Data Definitions

Real station coordinates, train definitions, and section characteristics
for the Konkan Railway corridor from Mumbai CSMT to Madgaon (Goa).
"""

# ── Corridor Stations (real lat/lon for Open-Meteo weather) ─────
CORRIDOR_STATIONS = [
    {
        "code": "CSMT",
        "name": "Chhatrapati Shivaji Maharaj Terminus",
        "short_name": "Mumbai CSMT",
        "lat": 18.9398,
        "lon": 72.8354,
        "km": 0,
        "zone": "CR",
        "elevation_m": 14,
        "section_type": "urban",
    },
    {
        "code": "DR",
        "name": "Dadar",
        "short_name": "Dadar",
        "lat": 19.0178,
        "lon": 72.8478,
        "km": 9,
        "zone": "CR",
        "elevation_m": 10,
        "section_type": "urban",
    },
    {
        "code": "TNA",
        "name": "Thane",
        "short_name": "Thane",
        "lat": 19.1860,
        "lon": 72.9781,
        "km": 34,
        "zone": "CR",
        "elevation_m": 7,
        "section_type": "urban",
    },
    {
        "code": "PNVL",
        "name": "Panvel Junction",
        "short_name": "Panvel",
        "lat": 18.9894,
        "lon": 73.1175,
        "km": 53,
        "zone": "CR",
        "elevation_m": 12,
        "section_type": "junction",
    },
    {
        "code": "ROHA",
        "name": "Roha",
        "short_name": "Roha",
        "lat": 18.4378,
        "lon": 73.1167,
        "km": 120,
        "zone": "KR",
        "elevation_m": 25,
        "section_type": "transition",
    },
    {
        "code": "MNI",
        "name": "Mangaon",
        "short_name": "Mangaon",
        "lat": 18.2289,
        "lon": 73.2803,
        "km": 147,
        "zone": "KR",
        "elevation_m": 45,
        "section_type": "ghat",
    },
    {
        "code": "KHED",
        "name": "Khed",
        "short_name": "Khed",
        "lat": 17.7175,
        "lon": 73.3956,
        "km": 203,
        "zone": "KR",
        "elevation_m": 55,
        "section_type": "ghat",
    },
    {
        "code": "CHPN",
        "name": "Chiplun",
        "short_name": "Chiplun",
        "lat": 17.5306,
        "lon": 73.5089,
        "km": 236,
        "zone": "KR",
        "elevation_m": 18,
        "section_type": "ghat",
    },
    {
        "code": "RN",
        "name": "Ratnagiri",
        "short_name": "Ratnagiri",
        "lat": 16.9944,
        "lon": 73.3000,
        "km": 313,
        "zone": "KR",
        "elevation_m": 10,
        "section_type": "coastal",
    },
    {
        "code": "SWV",
        "name": "Sawantwadi Road",
        "short_name": "Sawantwadi",
        "lat": 15.9036,
        "lon": 73.8167,
        "km": 427,
        "zone": "KR",
        "elevation_m": 35,
        "section_type": "ghat",
    },
    {
        "code": "KKW",
        "name": "Kudal",
        "short_name": "Kudal",
        "lat": 16.0000,
        "lon": 73.6833,
        "km": 406,
        "zone": "KR",
        "elevation_m": 20,
        "section_type": "coastal",
    },
    {
        "code": "THVM",
        "name": "Thivim",
        "short_name": "Thivim",
        "lat": 15.6000,
        "lon": 73.8167,
        "km": 468,
        "zone": "KR",
        "elevation_m": 30,
        "section_type": "coastal",
    },
    {
        "code": "KRMI",
        "name": "Karmali",
        "short_name": "Karmali",
        "lat": 15.4833,
        "lon": 73.9000,
        "km": 487,
        "zone": "KR",
        "elevation_m": 15,
        "section_type": "coastal",
    },
    {
        "code": "MAO",
        "name": "Madgaon Junction",
        "short_name": "Madgaon (Goa)",
        "lat": 15.3000,
        "lon": 73.9500,
        "km": 543,
        "zone": "KR",
        "elevation_m": 8,
        "section_type": "junction",
    },
]

# Quick lookups
STATION_BY_CODE = {s["code"]: s for s in CORRIDOR_STATIONS}
STATION_CODES = [s["code"] for s in CORRIDOR_STATIONS]

# ── Corridor Trains ─────────────────────────────────────────────
CORRIDOR_TRAINS = [
    {
        "train_no": "10103",
        "name": "Mandovi Express",
        "type": "MAIL-EXP",
        "direction": "DN",  # Mumbai → Goa
        "origin": "CSMT",
        "destination": "MAO",
        "departure": "07:10",
        "arrival": "19:25",
        "frequency": "Daily",
        "priority": 2,
        "stops": ["CSMT", "DR", "TNA", "PNVL", "ROHA", "MNI", "KHED", "CHPN", "RN", "KKW", "SWV", "THVM", "KRMI", "MAO"],
        "scheduled_times": {
            "CSMT": ("", "07:10"), "DR": ("07:25", "07:27"), "TNA": ("07:55", "07:57"),
            "PNVL": ("08:30", "08:35"), "ROHA": ("09:50", "09:52"), "MNI": ("10:15", "10:17"),
            "KHED": ("11:10", "11:12"), "CHPN": ("11:55", "12:00"), "RN": ("13:15", "13:20"),
            "KKW": ("15:40", "15:42"), "SWV": ("16:10", "16:12"), "THVM": ("17:20", "17:22"),
            "KRMI": ("17:50", "17:52"), "MAO": ("19:25", ""),
        },
    },
    {
        "train_no": "10104",
        "name": "Mandovi Express",
        "type": "MAIL-EXP",
        "direction": "UP",  # Goa → Mumbai
        "origin": "MAO",
        "destination": "CSMT",
        "departure": "07:00",
        "arrival": "19:15",
        "frequency": "Daily",
        "priority": 2,
        "stops": list(reversed(["CSMT", "DR", "TNA", "PNVL", "ROHA", "MNI", "KHED", "CHPN", "RN", "KKW", "SWV", "THVM", "KRMI", "MAO"])),
        "scheduled_times": {
            "MAO": ("", "07:00"), "KRMI": ("07:30", "07:32"), "THVM": ("08:00", "08:02"),
            "SWV": ("09:10", "09:12"), "KKW": ("09:40", "09:42"), "RN": ("12:00", "12:05"),
            "CHPN": ("13:20", "13:25"), "KHED": ("14:10", "14:12"), "MNI": ("15:05", "15:07"),
            "ROHA": ("15:30", "15:32"), "PNVL": ("16:50", "16:55"), "TNA": ("17:30", "17:32"),
            "DR": ("18:05", "18:07"), "CSMT": ("19:15", ""),
        },
    },
    {
        "train_no": "22119",
        "name": "Tejas Express",
        "type": "TEJAS",
        "direction": "DN",
        "origin": "CSMT",
        "destination": "MAO",
        "departure": "06:00",
        "arrival": "14:20",
        "frequency": "Daily",
        "priority": 1,  # High priority - premium train
        "stops": ["CSMT", "DR", "TNA", "PNVL", "ROHA", "CHPN", "RN", "THVM", "KRMI", "MAO"],
        "scheduled_times": {
            "CSMT": ("", "06:00"), "DR": ("06:15", "06:16"), "TNA": ("06:40", "06:42"),
            "PNVL": ("07:10", "07:12"), "ROHA": ("08:10", "08:12"), "CHPN": ("09:45", "09:47"),
            "RN": ("10:55", "10:57"), "THVM": ("12:50", "12:52"), "KRMI": ("13:20", "13:22"),
            "MAO": ("14:20", ""),
        },
    },
    {
        "train_no": "10111",
        "name": "Konkan Kanya Express",
        "type": "MAIL-EXP",
        "direction": "DN",
        "origin": "CSMT",
        "destination": "MAO",
        "departure": "23:00",
        "arrival": "11:30",
        "frequency": "Daily",
        "priority": 2,
        "stops": ["CSMT", "DR", "TNA", "PNVL", "ROHA", "MNI", "KHED", "CHPN", "RN", "KKW", "SWV", "THVM", "KRMI", "MAO"],
        "scheduled_times": {
            "CSMT": ("", "23:00"), "DR": ("23:18", "23:20"), "TNA": ("23:50", "23:52"),
            "PNVL": ("00:30", "00:35"), "ROHA": ("02:00", "02:02"), "MNI": ("02:30", "02:32"),
            "KHED": ("03:30", "03:32"), "CHPN": ("04:20", "04:25"), "RN": ("05:45", "05:50"),
            "KKW": ("08:00", "08:02"), "SWV": ("08:30", "08:32"), "THVM": ("09:35", "09:37"),
            "KRMI": ("10:10", "10:12"), "MAO": ("11:30", ""),
        },
    },
    {
        "train_no": "12051",
        "name": "Jan Shatabdi Express",
        "type": "SHTBD",
        "direction": "DN",
        "origin": "CSMT",
        "destination": "MAO",
        "departure": "05:25",
        "arrival": "16:50",
        "frequency": "Daily",
        "priority": 1,
        "stops": ["CSMT", "DR", "TNA", "PNVL", "ROHA", "KHED", "CHPN", "RN", "KKW", "SWV", "THVM", "KRMI", "MAO"],
        "scheduled_times": {
            "CSMT": ("", "05:25"), "DR": ("05:40", "05:42"), "TNA": ("06:10", "06:12"),
            "PNVL": ("06:45", "06:50"), "ROHA": ("08:15", "08:17"), "KHED": ("09:30", "09:32"),
            "CHPN": ("10:15", "10:20"), "RN": ("11:40", "11:45"), "KKW": ("13:50", "13:52"),
            "SWV": ("14:20", "14:22"), "THVM": ("15:15", "15:17"), "KRMI": ("15:45", "15:47"),
            "MAO": ("16:50", ""),
        },
    },
    {
        "train_no": "12617",
        "name": "Mangala Lakshadweep Express",
        "type": "SF",
        "direction": "DN",
        "origin": "CSMT",
        "destination": "MAO",  # continues further but we track till Goa
        "departure": "10:00",
        "arrival": "22:15",
        "frequency": "Daily",
        "priority": 2,
        "stops": ["CSMT", "DR", "TNA", "PNVL", "ROHA", "CHPN", "RN", "KKW", "SWV", "THVM", "KRMI", "MAO"],
        "scheduled_times": {
            "CSMT": ("", "10:00"), "DR": ("10:18", "10:20"), "TNA": ("10:50", "10:52"),
            "PNVL": ("11:25", "11:30"), "ROHA": ("13:00", "13:02"), "CHPN": ("14:50", "14:55"),
            "RN": ("16:10", "16:15"), "KKW": ("18:30", "18:32"), "SWV": ("19:00", "19:02"),
            "THVM": ("20:10", "20:12"), "KRMI": ("20:45", "20:47"), "MAO": ("22:15", ""),
        },
    },
]

TRAIN_BY_NO = {t["train_no"]: t for t in CORRIDOR_TRAINS}

# ── Section Characteristics ────────────────────────────────────
# Konkan Railway is famous for its challenging terrain
SECTION_CHARACTERISTICS = {
    "CSMT->DR": {"track": "double", "terrain": "urban", "tunnels": 0, "bridges": 0, "speed_limit": 50, "risk": "low"},
    "DR->TNA": {"track": "double", "terrain": "urban", "tunnels": 0, "bridges": 1, "speed_limit": 80, "risk": "low"},
    "TNA->PNVL": {"track": "double", "terrain": "suburban", "tunnels": 0, "bridges": 1, "speed_limit": 100, "risk": "low"},
    "PNVL->ROHA": {"track": "single", "terrain": "transition", "tunnels": 2, "bridges": 3, "speed_limit": 100, "risk": "medium"},
    "ROHA->MNI": {"track": "single", "terrain": "ghat", "tunnels": 5, "bridges": 4, "speed_limit": 80, "risk": "high"},
    "MNI->KHED": {"track": "single", "terrain": "ghat", "tunnels": 8, "bridges": 6, "speed_limit": 70, "risk": "high"},
    "KHED->CHPN": {"track": "single", "terrain": "ghat", "tunnels": 6, "bridges": 5, "speed_limit": 75, "risk": "high"},
    "CHPN->RN": {"track": "single", "terrain": "coastal_ghat", "tunnels": 10, "bridges": 8, "speed_limit": 80, "risk": "high"},
    "RN->KKW": {"track": "single", "terrain": "coastal", "tunnels": 7, "bridges": 6, "speed_limit": 90, "risk": "medium"},
    "KKW->SWV": {"track": "single", "terrain": "coastal", "tunnels": 4, "bridges": 3, "speed_limit": 90, "risk": "medium"},
    "SWV->THVM": {"track": "single", "terrain": "coastal", "tunnels": 3, "bridges": 2, "speed_limit": 100, "risk": "medium"},
    "THVM->KRMI": {"track": "single", "terrain": "coastal", "tunnels": 1, "bridges": 1, "speed_limit": 100, "risk": "low"},
    "KRMI->MAO": {"track": "single", "terrain": "coastal", "tunnels": 0, "bridges": 1, "speed_limit": 100, "risk": "low"},
}

# Reverse sections for UP direction
for key in list(SECTION_CHARACTERISTICS.keys()):
    fr, to = key.split("->")
    reverse_key = f"{to}->{fr}"
    if reverse_key not in SECTION_CHARACTERISTICS:
        SECTION_CHARACTERISTICS[reverse_key] = SECTION_CHARACTERISTICS[key]


def get_section(from_code: str, to_code: str) -> dict:
    """Get section characteristics between two stations."""
    key = f"{from_code}->{to_code}"
    return SECTION_CHARACTERISTICS.get(key, {
        "track": "single", "terrain": "unknown", "tunnels": 0,
        "bridges": 0, "speed_limit": 80, "risk": "medium"
    })
