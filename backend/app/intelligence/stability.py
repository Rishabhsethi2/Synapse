import logging
import numpy as np
from datetime import datetime
from collections import defaultdict, deque
from zoneinfo import ZoneInfo

from ..config import settings
from ..models.domain import ForecastStability, StabilityState, PredictionRevision

logger = logging.getLogger(__name__)
IST = ZoneInfo(settings.TIMEZONE)

class ForecastStabilityTracker:
    """
    Tracks and classifies the stability of ETA predictions over time.
    """
    
    def __init__(self):
        # Maps (train_id, station_code) -> deque of recent ETAs (datetime objects)
        # Also maps to deque of PredictionRevision
        self._etas = defaultdict(lambda: deque(maxlen=settings.STABILITY_WINDOW_SIZE))
        self._revisions = defaultdict(lambda: deque(maxlen=settings.STABILITY_WINDOW_SIZE))
        
    def record_prediction(
        self, 
        train_id: str, 
        station_code: str, 
        timestamp: datetime, 
        eta: datetime,
        model_version: str = settings.MODEL_VERSION,
        contributing_factors: list[str] = None
    ):
        """Records a new prediction for stability tracking."""
        key = (train_id, station_code)
        
        if len(self._etas[key]) > 0:
            prev_eta = self._etas[key][-1]
            change_mins = (eta - prev_eta).total_seconds() / 60.0
            
            rev = PredictionRevision(
                train_id=train_id,
                station_code=station_code,
                timestamp=timestamp,
                previous_eta=prev_eta,
                new_eta=eta,
                change_minutes=change_mins,
                contributing_factors=contributing_factors or [],
                model_version=model_version
            )
            self._revisions[key].append(rev)
            
        self._etas[key].append(eta)
        
    def get_stability(self, train_id: str, station_code: str) -> ForecastStability:
        """Returns the stability assessment for a train/station."""
        key = (train_id, station_code)
        etas = self._etas.get(key, [])
        revisions = list(self._revisions.get(key, []))
        
        if len(etas) < 2:
            return ForecastStability(
                train_id=train_id,
                station_code=station_code,
                recent_revisions=revisions,
                stability_index=StabilityState.STABLE,
                variance_minutes=0.0
            )
            
        # Compute variance in minutes
        base_time = etas[0]
        minutes_diffs = [(e - base_time).total_seconds() / 60.0 for e in etas]
        variance = np.var(minutes_diffs)
        
        state = StabilityState.STABLE
        if variance > settings.STABILITY_VOLATILE_THRESHOLD:
            state = StabilityState.VOLATILE
        elif variance > settings.STABILITY_STABLE_THRESHOLD:
            state = StabilityState.SETTLING
            
        return ForecastStability(
            train_id=train_id,
            station_code=station_code,
            recent_revisions=revisions,
            stability_index=state,
            variance_minutes=float(variance)
        )
        
    def get_revision_history(self, train_id: str, station_code: str) -> list[PredictionRevision]:
        """Gets the history of revisions."""
        key = (train_id, station_code)
        return list(self._revisions.get(key, []))
