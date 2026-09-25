"""
Synapse — Network State Engine

Models the railway network as a graph of stations (nodes) and
sections (edges). Computes network-level features: section occupancy,
headway, congestion, and identifies train interactions.

The graph is built from schedule/route data. At runtime, train
positions are overlaid to compute dynamic network state.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Optional

import networkx as nx

from ..config import settings
from .train_state import TrainStateEngine, TrainStateEntry

logger = logging.getLogger(__name__)


class SectionState:
    """Dynamic state of a railway section between two stations."""

    __slots__ = (
        "section_id", "from_station", "to_station", "distance_km",
        "occupying_trains", "scheduled_running_time_minutes",
        "timestamp",
    )

    def __init__(self, from_station: str, to_station: str, distance_km: float = 0.0):
        self.section_id = f"{from_station}->{to_station}"
        self.from_station = from_station
        self.to_station = to_station
        self.distance_km = distance_km
        self.occupying_trains: list[str] = []  # train_nos currently on/approaching section
        self.scheduled_running_time_minutes: Optional[float] = None
        self.timestamp: Optional[datetime] = None

    @property
    def occupancy_count(self) -> int:
        return len(self.occupying_trains)

    @property
    def is_occupied(self) -> bool:
        return self.occupancy_count > 0

    @property
    def congestion_score(self) -> float:
        """
        Simple congestion metric: number of trains on/approaching section.
        0 = empty, 1 = one train (normal), >1 = congested.

        This is NOT a fabricated score — it directly counts observable trains.
        """
        return float(self.occupancy_count)


class NetworkStateEngine:
    """
    Maintains the railway network graph and computes network-level state.

    Graph structure:
    - Nodes: stations (with metadata: zone, coordinates)
    - Edges: sections between consecutive stations on routes
      (with metadata: distance, typical running time)

    The graph is built once from timetable data. Dynamic state
    (which trains are where) is computed from the TrainStateEngine.
    """

    def __init__(self, train_state_engine: TrainStateEngine):
        self.graph = nx.DiGraph()
        self.train_state_engine = train_state_engine
        self._sections: dict[str, SectionState] = {}
        # Maps section_id -> set of train_nos that use this section
        self._section_train_map: dict[str, set[str]] = defaultdict(set)

    def build_network(
        self,
        routes: dict[str, list[dict]],
        stations: dict[str, dict],
    ):
        """
        Build the network graph from route/station data.

        Args:
            routes: {train_no: [{station_code, station_no, distance_km, ...}, ...]}
            stations: {station_code: {full_name, zone, lat, lon, ...}}
        """
        # Add station nodes
        for code, info in stations.items():
            self.graph.add_node(
                code,
                full_name=info.get("full_name", code),
                zone=info.get("zone", ""),
                lat=info.get("lat"),
                lon=info.get("lon"),
            )

        # Add section edges from routes
        for train_no, stops in routes.items():
            for i in range(len(stops) - 1):
                from_code = stops[i]["station_code"]
                to_code = stops[i + 1]["station_code"]
                section_id = f"{from_code}->{to_code}"

                # Compute section distance
                dist_from = stops[i].get("distance_km", 0) or 0
                dist_to = stops[i + 1].get("distance_km", 0) or 0
                section_distance = dist_to - dist_from

                # Compute scheduled running time if times available
                running_time = None
                dep_time = stops[i].get("departure_time")
                arr_time = stops[i + 1].get("arrival_time")
                if dep_time and arr_time:
                    running_time = self._time_diff_minutes(dep_time, arr_time)

                # Add/update edge
                if not self.graph.has_edge(from_code, to_code):
                    self.graph.add_edge(
                        from_code, to_code,
                        distance_km=max(section_distance, 0),
                        scheduled_running_time=running_time,
                        train_count=1,
                    )
                else:
                    # Update train count for shared sections
                    self.graph[from_code][to_code]["train_count"] += 1
                    # Keep the best running time estimate
                    if running_time and (
                        self.graph[from_code][to_code]["scheduled_running_time"] is None
                        or running_time < self.graph[from_code][to_code]["scheduled_running_time"]
                    ):
                        self.graph[from_code][to_code]["scheduled_running_time"] = running_time

                # Track which trains use this section
                self._section_train_map[section_id].add(train_no)

                # Create section state if needed
                if section_id not in self._sections:
                    self._sections[section_id] = SectionState(
                        from_code, to_code, max(section_distance, 0)
                    )
                    if running_time:
                        self._sections[section_id].scheduled_running_time_minutes = running_time

        logger.info(
            "Built network: %d stations, %d sections, %d routes",
            self.graph.number_of_nodes(),
            self.graph.number_of_edges(),
            len(routes),
        )

    def update_section_occupancy(self, timestamp: datetime):
        """
        Recompute section occupancy from current train positions.
        Called after train state changes.
        """
        # Clear all occupancy
        for section in self._sections.values():
            section.occupying_trains.clear()
            section.timestamp = timestamp

        # Overlay current train positions
        for entry in self.train_state_engine.get_all_active_trains():
            if entry.current_station_index >= entry.total_stations - 1:
                continue

            # The train is on the section FROM current station TO next station
            current_code = entry.current_station_code
            remaining = entry.remaining_stations
            if remaining:
                next_code = remaining[0]
                section_id = f"{current_code}->{next_code}"
                if section_id in self._sections:
                    self._sections[section_id].occupying_trains.append(entry.train_no)

    def get_section_state(self, section_id: str) -> Optional[SectionState]:
        """Get current state of a section."""
        return self._sections.get(section_id)

    def get_section_congestion(self, section_id: str) -> float:
        """Get congestion score for a section."""
        section = self._sections.get(section_id)
        if section is None:
            return 0.0
        return section.congestion_score

    def get_section_headway(
        self,
        train_no: str,
        section_id: str,
    ) -> Optional[float]:
        """
        Estimate headway (time gap) to the preceding train on a section.

        Returns minutes ahead of preceding train, or None if no
        preceding train is identifiable.

        Note: Without GPS-level granularity, this is estimated from
        the delay difference between trains at shared stations.
        Labelled as 'estimated headway' in the API.
        """
        section = self._sections.get(section_id)
        if section is None:
            return None

        target = self.train_state_engine.get_train(train_no)
        if target is None:
            return None

        # Find other trains on the same section that are ahead
        for other_no in section.occupying_trains:
            if other_no == train_no:
                continue
            other = self.train_state_engine.get_train(other_no)
            if other is None:
                continue

            # Simple headway estimate: if both trains share a station,
            # use the delay difference as a proxy for headway
            if (other.current_station_index > target.current_station_index and
                    other.current_station_code in target.route_station_codes):
                # The other train is ahead — headway is roughly
                # (other's delay - our delay) + scheduled time gap
                headway = abs(other.current_delay_minutes - target.current_delay_minutes)
                return float(headway)

        return None

    def get_trains_sharing_section(self, section_id: str) -> list[str]:
        """Get all trains that traverse a section (from timetable)."""
        return list(self._section_train_map.get(section_id, set()))

    def get_shared_sections(self, train_no: str) -> list[str]:
        """Get sections used by this train that are also used by other trains."""
        result = []
        target = self.train_state_engine.get_train(train_no)
        if target is None:
            return result

        for i in range(len(target.route_station_codes) - 1):
            section_id = f"{target.route_station_codes[i]}->{target.route_station_codes[i+1]}"
            if section_id in self._section_train_map:
                if len(self._section_train_map[section_id]) > 1:
                    result.append(section_id)

        return result

    def get_downstream_stations(self, station_code: str, max_depth: int = 5) -> list[str]:
        """Get stations reachable downstream from a station (BFS)."""
        try:
            # BFS up to max_depth
            visited = set()
            queue = [(station_code, 0)]
            result = []
            while queue:
                node, depth = queue.pop(0)
                if depth > max_depth:
                    continue
                if node in visited:
                    continue
                visited.add(node)
                if node != station_code:
                    result.append(node)
                for neighbor in self.graph.successors(node):
                    if neighbor not in visited:
                        queue.append((neighbor, depth + 1))
            return result
        except nx.NetworkXError:
            return []

    def get_section_risk_factors(self, section_id: str) -> dict:
        """
        Compute risk factors for a section. Used by the section risk scorer.

        Returns observable factors, not fabricated scores.
        """
        section = self._sections.get(section_id)
        if section is None:
            return {"error": "section_not_found"}

        trains_using = self._section_train_map.get(section_id, set())

        return {
            "section_id": section_id,
            "current_occupancy": section.occupancy_count,
            "total_trains_scheduled": len(trains_using),
            "distance_km": section.distance_km,
            "scheduled_running_time_minutes": section.scheduled_running_time_minutes,
            "is_shared": len(trains_using) > 1,
        }

    @property
    def total_sections(self) -> int:
        return len(self._sections)

    @property
    def occupied_sections(self) -> int:
        return sum(1 for s in self._sections.values() if s.is_occupied)

    @staticmethod
    def _time_diff_minutes(dep_time: str, arr_time: str) -> Optional[float]:
        """Calculate minutes between departure and arrival times (HH:MM strings)."""
        try:
            dep_parts = dep_time.split(":")
            arr_parts = arr_time.split(":")
            dep_min = int(dep_parts[0]) * 60 + int(dep_parts[1])
            arr_min = int(arr_parts[0]) * 60 + int(arr_parts[1])
            diff = arr_min - dep_min
            if diff < 0:
                diff += 24 * 60  # Handle day crossing
            return float(diff)
        except (ValueError, IndexError):
            return None
