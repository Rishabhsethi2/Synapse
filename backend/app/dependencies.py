"""
Synapse — Dependency Injection Container

Initializes all engines at application startup and provides
FastAPI dependency injection functions.
"""
import logging
from pathlib import Path

from .config import settings
from .state.train_state import TrainStateEngine
from .state.network_state import NetworkStateEngine
from .state.historical_state import HistoricalStateEngine
from .features.feature_engine import FeatureEngine
from .forecast.model import SynapseForecaster
from .forecast.baselines import BaselineA_Schedule, BaselineB_SchedulePlusDelay, BaselineC_Historical
from .intelligence.attribution import AttributionEngine
from .intelligence.stability import ForecastStabilityTracker
from .intelligence.section_risk import SectionRiskScorer
from .intelligence.whatif import WhatIfEngine
from .intelligence.propagation import PropagationEstimator
from .replay.engine import ReplayEngine
from .data.loader import DataLoader

logger = logging.getLogger(__name__)

# ── Core state engines ──────────────────────────────────────────
train_state_engine = TrainStateEngine()
network_state_engine = NetworkStateEngine(train_state_engine)
historical_state_engine = HistoricalStateEngine()

# ── ML forecaster (loads trained LightGBM models) ───────────────
_models_dir = Path(settings.MODELS_DIR)
_point_model_path = _models_dir / "lgbm_point_v1.0.0.joblib"
_q10_model_path = _models_dir / "lgbm_q10_v1.0.0.joblib"
_q90_model_path = _models_dir / "lgbm_q90_v1.0.0.joblib"

synapse_forecaster = SynapseForecaster(
    model_path=str(_point_model_path) if _point_model_path.exists() else None,
    q10_path=str(_q10_model_path) if _q10_model_path.exists() else None,
    q90_path=str(_q90_model_path) if _q90_model_path.exists() else None,
)

# ── Baselines ───────────────────────────────────────────────────
baseline_a = BaselineA_Schedule()
baseline_b = BaselineB_SchedulePlusDelay()
baseline_c = BaselineC_Historical()

# ── Intelligence layer ──────────────────────────────────────────
attribution_engine = AttributionEngine()
stability_tracker = ForecastStabilityTracker()
section_risk_scorer = SectionRiskScorer()
whatif_engine = WhatIfEngine()
propagation_estimator = PropagationEstimator(damping_factor=0.5)

# ── Feature engine ──────────────────────────────────────────────
feature_engine = FeatureEngine(
    train_state_engine=train_state_engine,
    network_state_engine=network_state_engine,
    historical_state_engine=historical_state_engine,
)

# ── Replay engine ──────────────────────────────────────────────
replay_engine = ReplayEngine()

# ── Data loader ────────────────────────────────────────────────
data_loader = DataLoader(raw_data_dir=settings.DATA_RAW_DIR)

# ── Route / Station / Train lookup caches ──────────────────────
# These are populated during startup (see main.py lifespan)
station_lookup: dict = {}   # station_code -> {full_name, zone, ...}
train_lookup: dict = {}     # train_no -> {train_name, type_code, ...}
route_lookup: dict = {}     # train_no -> [{station_code, station_no, ...}, ...]


def startup_load_data():
    """
    Called once at application startup.
    Loads station, train, and schedule data into memory.
    Fits the historical state engine.
    """

    logger.info("Loading station data...")
    data_loader.load_stations()
    station_lookup.update(data_loader.stations)

    logger.info("Loading train data...")
    data_loader.load_trains()
    train_lookup.update(data_loader.trains)

    logger.info("Loading schedule data...")
    data_loader.load_schedule()
    route_lookup.update(data_loader.routes)

    # Build network graph from routes
    routes_for_graph = {}
    for train_no, stops in route_lookup.items():
        routes_for_graph[train_no] = [
            {
                "station_code": stop["station_name"],
                "station_no": stop["station_no"],
                "distance_km": stop.get("distance_from_origin", 0),
                "departure_time": str(stop["departure_time"]) if stop.get("departure_time") else None,
                "arrival_time": str(stop["arrival_time"]) if stop.get("arrival_time") else None,
            }
            for stop in stops
        ]

    stations_for_graph = {
        code: {
            "full_name": info.get("station_full_name", code),
            "zone": info.get("station_zone", ""),
        }
        for code, info in station_lookup.items()
    }

    if settings.ENABLE_NETWORK_GRAPH:
        network_state_engine.build_network(routes_for_graph, stations_for_graph)

    logger.info(
        "Startup complete: %d stations, %d trains, %d routes loaded",
        len(station_lookup), len(train_lookup), len(route_lookup),
    )


# ── FastAPI dependency getters ─────────────────────────────────
def get_train_state_engine() -> TrainStateEngine:
    return train_state_engine

def get_network_state_engine() -> NetworkStateEngine:
    return network_state_engine

def get_historical_state_engine() -> HistoricalStateEngine:
    return historical_state_engine

def get_synapse_forecaster() -> SynapseForecaster:
    return synapse_forecaster

def get_feature_engine() -> FeatureEngine:
    return feature_engine

def get_attribution_engine() -> AttributionEngine:
    return attribution_engine

def get_stability_tracker() -> ForecastStabilityTracker:
    return stability_tracker

def get_section_risk_scorer() -> SectionRiskScorer:
    return section_risk_scorer

def get_whatif_engine() -> WhatIfEngine:
    return whatif_engine

def get_propagation_estimator() -> PropagationEstimator:
    return propagation_estimator

def get_replay_engine() -> ReplayEngine:
    return replay_engine

def get_data_loader() -> DataLoader:
    return data_loader
