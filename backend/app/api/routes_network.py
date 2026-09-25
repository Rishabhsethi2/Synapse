"""
Synapse - Network API Routes
"""
from fastapi import APIRouter, HTTPException

from ..dependencies import (
    network_state_engine, section_risk_scorer,
    propagation_estimator, train_state_engine,
    route_lookup, station_lookup,
)

router = APIRouter(tags=["network"])


@router.get("/sections/{section_id}/risk")
def get_section_risk(section_id: str):
    """Get risk assessment for a railway section."""
    factors = network_state_engine.get_section_risk_factors(section_id)
    if "error" in factors:
        raise HTTPException(404, f"Section {section_id} not found")

    return {
        "section_id": section_id,
        "current_occupancy": factors["current_occupancy"],
        "total_trains_scheduled": factors["total_trains_scheduled"],
        "distance_km": factors["distance_km"],
        "scheduled_running_time_minutes": factors["scheduled_running_time_minutes"],
        "is_shared": factors["is_shared"],
    }


@router.get("/network/vulnerability")
def get_network_vulnerability():
    """Get network-wide vulnerability ranking of sections."""
    sections = []
    for section_id in list(network_state_engine._sections.keys())[:100]:
        factors = network_state_engine.get_section_risk_factors(section_id)
        if "error" not in factors:
            sections.append(factors)

    # Sort by occupancy and shared status
    sections.sort(
        key=lambda s: (s["current_occupancy"], s["total_trains_scheduled"]),
        reverse=True,
    )

    return {
        "total_sections": network_state_engine.total_sections,
        "occupied_sections": network_state_engine.occupied_sections,
        "high_risk_sections": sections[:20],
    }


@router.get("/network/stats")
def get_network_stats():
    """Get overall network statistics."""
    return {
        "total_stations": len(station_lookup),
        "total_routes": len(route_lookup),
        "total_sections": network_state_engine.total_sections,
        "occupied_sections": network_state_engine.occupied_sections,
        "active_trains": train_state_engine.active_train_count,
        "graph_nodes": network_state_engine.graph.number_of_nodes(),
        "graph_edges": network_state_engine.graph.number_of_edges(),
    }


@router.get("/feeder/{train_id}/sync-window")
def get_feeder_sync_window(train_id: str):
    """Get feeder sync window for connecting trains at a station."""
    route = route_lookup.get(train_id, [])
    if not route:
        raise HTTPException(404, f"Train {train_id} route not found")

    destination = route[-1]["station_name"]

    return {
        "train_id": train_id,
        "destination_station": destination,
        "message": "Feeder sync windows are computed during replay mode when train state is active.",
        "methodology": "QUANTILE_REGRESSION_INTERVAL",
    }
