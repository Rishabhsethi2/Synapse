"""
Synapse — Replay Engine

The replay engine is the heartbeat of the demo. Since we don't have
live data feeds, replay simulates the sequential arrival of
observations from historical data.

CRITICAL INVARIANT: At replay time t, only information available
at or before t is visible to the prediction engine. Future
information is never leaked.

The replay engine:
1. Loads a historical journey (train + date)
2. Steps through stations chronologically
3. At each step: updates train state, triggers prediction
4. Records every prediction revision
5. At journey end: compares predictions to actual outcomes
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Callable
from zoneinfo import ZoneInfo

from ..config import settings
from ..models.domain import (
    Prediction, PredictionRevision, PredictionMode, DataQuality,
)

logger = logging.getLogger(__name__)
IST = ZoneInfo(settings.TIMEZONE)


class ReplayJourneyStep:
    """One observation in a replayed journey."""

    __slots__ = (
        "train_no", "date", "station_no", "station_code",
        "delay_minutes", "timestamp", "is_final_station",
        "scheduled_arrival", "scheduled_departure",
        "distance_from_origin_km",
    )

    def __init__(
        self,
        train_no: str,
        date: str,
        station_no: int,
        station_code: str,
        delay_minutes: Optional[int],
        scheduled_arrival: Optional[str],
        scheduled_departure: Optional[str],
        distance_from_origin_km: float,
        is_final_station: bool = False,
    ):
        self.train_no = train_no
        self.date = date
        self.station_no = station_no
        self.station_code = station_code
        self.delay_minutes = delay_minutes if delay_minutes is not None else 0
        self.scheduled_arrival = scheduled_arrival
        self.scheduled_departure = scheduled_departure
        self.distance_from_origin_km = distance_from_origin_km
        self.is_final_station = is_final_station

        # Compute a simulated timestamp from the date + scheduled time + delay
        self.timestamp = self._compute_timestamp()

    def _compute_timestamp(self) -> datetime:
        """
        Derive observation timestamp from date, scheduled time, and delay.
        This simulates when NTES/RTIS would report this observation.
        """
        try:
            base_date = datetime.strptime(self.date, "%Y-%m-%d")
        except (ValueError, TypeError):
            base_date = datetime.now()

        time_str = self.scheduled_arrival or self.scheduled_departure
        if time_str:
            try:
                parts = time_str.split(":")
                hour, minute = int(parts[0]), int(parts[1])
                base_dt = base_date.replace(
                    hour=hour, minute=minute, second=0,
                    tzinfo=IST,
                )
                # Add delay to get actual observation time
                return base_dt + timedelta(minutes=self.delay_minutes)
            except (ValueError, IndexError):
                pass

        # Fallback: use base date with station_no-based offset
        return base_date.replace(
            hour=6, minute=0, second=0, tzinfo=IST
        ) + timedelta(hours=self.station_no)


class ReplayScenario:
    """
    A complete replay scenario for one or more trains.

    Manages the chronological ordering of observations and
    provides step-by-step replay with temporal causality.
    """

    def __init__(self, scenario_id: str = "default"):
        self.scenario_id = scenario_id
        self.steps: list[ReplayJourneyStep] = []
        self.current_step_index: int = -1
        self.is_started: bool = False
        self.is_completed: bool = False
        self.revealed_steps: list[ReplayJourneyStep] = []

        # Prediction tracking
        self.prediction_history: dict[str, list[Prediction]] = {}
        # Key: "{train_no}:{station_code}" -> list of predictions over time
        self.actual_delays: dict[str, float] = {}
        # Key: "{train_no}:{station_code}" -> actual delay

    def load_journey(
        self,
        journey_data: list[dict],
        schedule_data: list[dict],
    ):
        """
        Load a journey from historical delay data + schedule.

        Args:
            journey_data: List of dicts with keys:
                train_no, date, station_no, station_code, delay_minutes
            schedule_data: List of dicts with keys:
                station_no, station_code, arrival_time, departure_time,
                distance_from_origin_km
        """
        # Build schedule lookup
        schedule_lookup = {}
        for stop in schedule_data:
            schedule_lookup[int(stop["station_no"])] = stop

        # Build steps
        total_stations = len(journey_data)
        for i, obs in enumerate(journey_data):
            station_no = int(obs["station_no"])
            sched = schedule_lookup.get(station_no, {})

            step = ReplayJourneyStep(
                train_no=obs["train_no"],
                date=obs["date"],
                station_no=station_no,
                station_code=obs["station_code"],
                delay_minutes=obs.get("delay_minutes"),
                scheduled_arrival=sched.get("arrival_time"),
                scheduled_departure=sched.get("departure_time"),
                distance_from_origin_km=float(sched.get("distance_from_origin_km", 0)),
                is_final_station=(i == total_stations - 1),
            )
            self.steps.append(step)

            # Record actual delay for evaluation
            key = f"{obs['train_no']}:{obs['station_code']}"
            if obs.get("delay_minutes") is not None:
                self.actual_delays[key] = float(obs["delay_minutes"])

        # Sort by timestamp to ensure chronological order
        self.steps.sort(key=lambda s: s.timestamp)

        logger.info(
            "Loaded replay scenario '%s' with %d steps for train(s): %s",
            self.scenario_id,
            len(self.steps),
            ", ".join(set(s.train_no for s in self.steps)),
        )

    def start(self):
        """Start the replay from the beginning."""
        self.current_step_index = -1
        self.is_started = True
        self.is_completed = False
        self.revealed_steps.clear()
        self.prediction_history.clear()
        logger.info("Replay scenario '%s' started", self.scenario_id)

    def tick(self) -> Optional[ReplayJourneyStep]:
        """
        Advance replay by one step.

        Returns the newly revealed observation, or None if replay
        is complete.
        """
        if not self.is_started:
            self.start()

        self.current_step_index += 1

        if self.current_step_index >= len(self.steps):
            self.is_completed = True
            logger.info("Replay scenario '%s' completed", self.scenario_id)
            return None

        step = self.steps[self.current_step_index]
        self.revealed_steps.append(step)

        logger.debug(
            "Replay tick %d: train=%s station=%s delay=%d",
            self.current_step_index,
            step.train_no,
            step.station_code,
            step.delay_minutes,
        )

        return step

    def record_prediction(self, prediction: Prediction):
        """Record a prediction for later evaluation."""
        key = f"{prediction.train_id}:{prediction.station_code}"
        if key not in self.prediction_history:
            self.prediction_history[key] = []
        self.prediction_history[key].append(prediction)

    def get_evaluation(self) -> dict:
        """
        Evaluate predictions against actual outcomes.

        Returns metrics: MAE, RMSE, per-station errors,
        prediction count, coverage (if intervals available).
        """
        errors = []
        station_errors: dict[str, list[float]] = {}
        coverage_hits = 0
        coverage_total = 0
        interval_widths = []

        for key, predictions in self.prediction_history.items():
            actual = self.actual_delays.get(key)
            if actual is None:
                continue

            # Use the LAST prediction (most recent before arrival)
            if not predictions:
                continue
            final_pred = predictions[-1]

            error = final_pred.predicted_delay_minutes - actual
            abs_error = abs(error)
            errors.append(abs_error)

            # Per-station tracking
            station = key.split(":")[1]
            if station not in station_errors:
                station_errors[station] = []
            station_errors[station].append(abs_error)

            # Coverage check (if interval exists)
            if final_pred.lower_bound and final_pred.upper_bound:
                coverage_total += 1
                # Check if actual falls within interval
                actual_arrival_delay = actual
                pred_lower_delay = final_pred.predicted_delay_minutes - (
                    final_pred.prediction_interval_minutes or 0
                ) / 2
                pred_upper_delay = final_pred.predicted_delay_minutes + (
                    final_pred.prediction_interval_minutes or 0
                ) / 2
                if pred_lower_delay <= actual_arrival_delay <= pred_upper_delay:
                    coverage_hits += 1
                interval_widths.append(final_pred.prediction_interval_minutes or 0)

        if not errors:
            return {"error": "No predictions to evaluate"}

        import numpy as np
        errors_arr = np.array(errors)

        result = {
            "mae": float(np.mean(errors_arr)),
            "rmse": float(np.sqrt(np.mean(errors_arr ** 2))),
            "median_ae": float(np.median(errors_arr)),
            "max_ae": float(np.max(errors_arr)),
            "prediction_count": len(errors),
            "station_count": len(station_errors),
        }

        # Per-station MAE
        result["per_station_mae"] = {
            station: float(np.mean(errs))
            for station, errs in station_errors.items()
        }

        # Coverage metrics
        if coverage_total > 0:
            result["coverage"] = coverage_hits / coverage_total
            result["mean_interval_width"] = float(np.mean(interval_widths))
            result["coverage_total"] = coverage_total

        # Prediction revision analysis
        revision_counts = []
        for key, preds in self.prediction_history.items():
            revision_counts.append(len(preds))
        result["mean_revisions_per_station"] = float(np.mean(revision_counts))

        return result

    @property
    def current_time(self) -> Optional[datetime]:
        """Current replay time (timestamp of last revealed step)."""
        if not self.revealed_steps:
            return None
        return self.revealed_steps[-1].timestamp

    @property
    def progress(self) -> float:
        """Replay progress (0.0 to 1.0)."""
        if not self.steps:
            return 0.0
        return (self.current_step_index + 1) / len(self.steps)

    def get_state_summary(self) -> dict:
        """Current state of the replay for API consumption."""
        return {
            "scenario_id": self.scenario_id,
            "is_started": self.is_started,
            "is_completed": self.is_completed,
            "total_steps": len(self.steps),
            "current_step": self.current_step_index + 1,
            "progress": self.progress,
            "current_time": self.current_time.isoformat() if self.current_time else None,
            "trains": list(set(s.train_no for s in self.steps)),
            "prediction_mode": "REPLAY",
        }


class ReplayEngine:
    """
    Top-level replay engine that manages scenarios and orchestrates
    the replay → state update → prediction → recording loop.
    """

    def __init__(self):
        self.scenarios: dict[str, ReplayScenario] = {}
        self.active_scenario_id: Optional[str] = None

    def create_scenario(
        self,
        scenario_id: str,
        journey_data: list[dict],
        schedule_data: list[dict],
    ) -> ReplayScenario:
        """Create a new replay scenario from data."""
        scenario = ReplayScenario(scenario_id)
        scenario.load_journey(journey_data, schedule_data)
        self.scenarios[scenario_id] = scenario
        return scenario

    def get_scenario(self, scenario_id: str) -> Optional[ReplayScenario]:
        return self.scenarios.get(scenario_id)

    def get_active_scenario(self) -> Optional[ReplayScenario]:
        if self.active_scenario_id:
            return self.scenarios.get(self.active_scenario_id)
        return None

    def start_scenario(self, scenario_id: str) -> bool:
        scenario = self.scenarios.get(scenario_id)
        if scenario is None:
            return False
        scenario.start()
        self.active_scenario_id = scenario_id
        return True

    def tick(self) -> Optional[ReplayJourneyStep]:
        """Advance the active scenario by one step."""
        scenario = self.get_active_scenario()
        if scenario is None:
            return None
        return scenario.tick()
