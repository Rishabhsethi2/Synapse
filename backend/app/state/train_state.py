"""
Synapse — Train State Engine

Manages the current state of each train in the system.
Tracks position, delay, data freshness, and triggers downstream
recomputation when state changes.

In REPLAY mode, state is advanced by the replay engine.
In LIVE mode (future), state would be updated by GPS/NTES feeds.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from ..config import settings

logger = logging.getLogger(__name__)
IST = ZoneInfo(settings.TIMEZONE)


class TrainStateEntry:
    """
    Current state of a single train at a point in time.

    This is a mutable, in-memory object — NOT a Pydantic model.
    Pydantic models are used for API serialization; this is the
    internal working state.
    """

    __slots__ = (
        "train_no", "timestamp", "current_station_index",
        "current_station_code", "current_delay_minutes",
        "speed_kmh", "source", "source_timestamp",
        "route_station_codes", "route_station_nos",
        "total_stations", "has_departed_origin",
        "has_arrived_destination", "last_update_time",
        "_previous_delay_minutes",
    )

    def __init__(
        self,
        train_no: str,
        route_station_codes: list[str],
        route_station_nos: list[int],
    ):
        self.train_no = train_no
        self.timestamp: Optional[datetime] = None
        self.current_station_index: int = 0
        self.current_station_code: str = route_station_codes[0] if route_station_codes else ""
        self.current_delay_minutes: int = 0
        self.speed_kmh: Optional[float] = None
        self.source: str = "REPLAY"  # LIVE | REPLAY | SIMULATED
        self.source_timestamp: Optional[datetime] = None
        self.route_station_codes = route_station_codes
        self.route_station_nos = route_station_nos
        self.total_stations = len(route_station_codes)
        self.has_departed_origin = False
        self.has_arrived_destination = False
        self.last_update_time: Optional[datetime] = None
        self._previous_delay_minutes: int = 0

    def update_position(
        self,
        station_index: int,
        station_code: str,
        delay_minutes: int,
        timestamp: datetime,
        source: str = "REPLAY",
    ) -> bool:
        """
        Update train position. Returns True if state materially changed
        (station or delay changed), triggering downstream recomputation.
        """
        changed = (
            self.current_station_index != station_index
            or self.current_delay_minutes != delay_minutes
        )

        self._previous_delay_minutes = self.current_delay_minutes
        self.current_station_index = station_index
        self.current_station_code = station_code
        self.current_delay_minutes = delay_minutes
        self.timestamp = timestamp
        self.source = source
        self.source_timestamp = timestamp
        self.last_update_time = datetime.now(IST)

        if station_index == 0:
            self.has_departed_origin = True
        if station_index >= self.total_stations - 1:
            self.has_arrived_destination = True

        if changed:
            logger.debug(
                "Train %s state changed: station=%s (idx=%d), delay=%d min",
                self.train_no, station_code, station_index, delay_minutes,
            )

        return changed

    @property
    def delay_change(self) -> int:
        """Change in delay from last update (positive = worsening)."""
        return self.current_delay_minutes - self._previous_delay_minutes

    @property
    def remaining_stations(self) -> list[str]:
        """Station codes yet to be reached."""
        if self.current_station_index >= self.total_stations - 1:
            return []
        return self.route_station_codes[self.current_station_index + 1:]

    @property
    def remaining_station_indices(self) -> list[int]:
        """Station sequence numbers yet to be reached."""
        if self.current_station_index >= self.total_stations - 1:
            return []
        return list(range(self.current_station_index + 1, self.total_stations))

    @property
    def journey_progress(self) -> float:
        """Fraction of route completed (0.0 to 1.0)."""
        if self.total_stations <= 1:
            return 1.0
        return self.current_station_index / (self.total_stations - 1)

    @property
    def data_freshness_seconds(self) -> float:
        """Seconds since last update."""
        if self.last_update_time is None:
            return float("inf")
        delta = datetime.now(IST) - self.last_update_time
        return delta.total_seconds()

    @property
    def is_fresh(self) -> bool:
        return self.data_freshness_seconds < settings.FRESH_THRESHOLD

    @property
    def is_stale(self) -> bool:
        return self.data_freshness_seconds >= settings.STALE_THRESHOLD

    @property
    def is_dead(self) -> bool:
        return self.data_freshness_seconds >= settings.DEAD_THRESHOLD

    @property
    def freshness_label(self) -> str:
        if self.is_dead:
            return "DEAD"
        if self.is_stale:
            return "STALE"
        return "FRESH"


class TrainStateEngine:
    """
    Manages state for all active trains.

    Provides O(1) lookup by train_no and supports
    batch operations for network-level queries.
    """

    def __init__(self):
        self._trains: dict[str, TrainStateEntry] = {}
        self._update_count: int = 0

    def register_train(
        self,
        train_no: str,
        route_station_codes: list[str],
        route_station_nos: list[int],
    ) -> TrainStateEntry:
        """Register a train for state tracking."""
        entry = TrainStateEntry(train_no, route_station_codes, route_station_nos)
        self._trains[train_no] = entry
        logger.info(
            "Registered train %s with %d stations",
            train_no, len(route_station_codes),
        )
        return entry

    def get_train(self, train_no: str) -> Optional[TrainStateEntry]:
        """Get current state for a train."""
        return self._trains.get(train_no)

    def update_train(
        self,
        train_no: str,
        station_index: int,
        station_code: str,
        delay_minutes: int,
        timestamp: datetime,
        source: str = "REPLAY",
    ) -> bool:
        """
        Update a train's state. Returns True if state materially changed.
        """
        entry = self._trains.get(train_no)
        if entry is None:
            logger.warning("Attempted to update unregistered train: %s", train_no)
            return False

        changed = entry.update_position(
            station_index, station_code, delay_minutes, timestamp, source
        )
        if changed:
            self._update_count += 1

        return changed

    def get_all_active_trains(self) -> list[TrainStateEntry]:
        """Get all trains that haven't completed their journey."""
        return [
            t for t in self._trains.values()
            if not t.has_arrived_destination
        ]

    def get_trains_on_section(
        self,
        from_station: str,
        to_station: str,
    ) -> list[TrainStateEntry]:
        """
        Find trains currently on or approaching a section.
        Used for congestion and headway computation.
        """
        result = []
        for entry in self._trains.values():
            if entry.has_arrived_destination:
                continue
            # Check if the train's current position is at from_station
            # or if the section is in the train's remaining route
            if entry.current_station_code == from_station:
                result.append(entry)
            elif from_station in entry.remaining_stations:
                result.append(entry)
        return result

    def get_preceding_train(
        self,
        train_no: str,
        section_from: str,
        section_to: str,
    ) -> Optional[TrainStateEntry]:
        """
        Find the train immediately ahead on a shared section.

        'Preceding' means: a train that is on or has recently passed
        through the same section, ahead of the queried train.

        Returns None if no preceding train exists or data is insufficient.
        """
        target = self._trains.get(train_no)
        if target is None:
            return None

        candidates = []
        for entry in self._trains.values():
            if entry.train_no == train_no:
                continue
            if entry.has_arrived_destination:
                continue

            # Check if this train shares the section and is ahead
            try:
                target_section_idx = target.route_station_codes.index(section_from)
                other_section_idx = entry.route_station_codes.index(section_from)
            except ValueError:
                continue

            # The other train is 'preceding' if it's further along on the same section
            if (entry.current_station_index > other_section_idx and
                    target.current_station_index <= target_section_idx):
                candidates.append(entry)

        if not candidates:
            return None

        # Return the closest preceding train (smallest distance ahead)
        return min(candidates, key=lambda e: e.current_station_index)

    @property
    def active_train_count(self) -> int:
        return len([t for t in self._trains.values() if not t.has_arrived_destination])

    @property
    def total_updates(self) -> int:
        return self._update_count

    def reset(self):
        """Clear all train states (useful for replay restart)."""
        self._trains.clear()
        self._update_count = 0
