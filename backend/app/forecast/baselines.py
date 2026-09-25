import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from ..models.domain import Prediction, DataQuality, PredictionMode
from ..state.train_state import TrainStateEntry
from ..state.historical_state import HistoricalStateEngine
from ..config import settings
from zoneinfo import ZoneInfo

IST = ZoneInfo(settings.TIMEZONE)
logger = logging.getLogger(__name__)

class BaseForecaster:
    def _create_prediction(
        self,
        train_no: str,
        target_station_code: str,
        predicted_arrival: datetime,
        predicted_delay_minutes: float,
        model_version: str,
        data_quality: DataQuality
    ) -> Prediction:
        return Prediction(
            train_id=train_no,
            generated_at=datetime.now(IST),
            model_version=model_version,
            station_code=target_station_code,
            station_no=0,  # Could be derived from schedule
            predicted_arrival=predicted_arrival,
            predicted_delay_minutes=predicted_delay_minutes,
            data_quality=data_quality,
            prediction_mode=PredictionMode.LIVE
        )

class BaselineA_Schedule(BaseForecaster):
    """
    Predicts ETA = scheduled arrival time (ignores current state entirely).
    predicted_delay = 0 always.
    """
    def predict(
        self, 
        train_no: str, 
        target_station_code: str, 
        current_state: TrainStateEntry,
        schedule: List[Dict[str, Any]],
        historical_data: HistoricalStateEngine
    ) -> Optional[Prediction]:
        
        # Find scheduled arrival at target station
        target_schedule = next((s for s in schedule if s['station_code'] == target_station_code), None)
        if not target_schedule or not target_schedule.get('arrival_time'):
            return None
            
        # Parse scheduled arrival time (simplified for baseline)
        # Normally would need date + time, assuming 'scheduled_arrival' is a datetime in schedule dict
        sched_arrival = target_schedule.get('scheduled_arrival')
        if not sched_arrival:
            # Create dummy datetime for this baseline if not available
            sched_arrival = datetime.now(IST)
            
        return self._create_prediction(
            train_no=train_no,
            target_station_code=target_station_code,
            predicted_arrival=sched_arrival,
            predicted_delay_minutes=0.0,
            model_version="BaselineA_Schedule",
            data_quality=DataQuality.FULL
        )

class BaselineB_SchedulePlusDelay(BaseForecaster):
    """
    Predicts ETA = scheduled arrival + current_delay_minutes.
    Assumes delay stays constant for the rest of the journey.
    """
    def predict(
        self, 
        train_no: str, 
        target_station_code: str, 
        current_state: TrainStateEntry,
        schedule: List[Dict[str, Any]],
        historical_data: HistoricalStateEngine
    ) -> Optional[Prediction]:
        
        target_schedule = next((s for s in schedule if s['station_code'] == target_station_code), None)
        if not target_schedule or not target_schedule.get('scheduled_arrival'):
            return None
            
        sched_arrival = target_schedule['scheduled_arrival']
        current_delay = current_state.current_delay_minutes
        predicted_arrival = sched_arrival + timedelta(minutes=current_delay)
        
        quality = DataQuality.FULL
        if current_state.is_stale:
            quality = DataQuality.STALE
        if current_state.is_dead:
            quality = DataQuality.FALLBACK
            
        return self._create_prediction(
            train_no=train_no,
            target_station_code=target_station_code,
            predicted_arrival=predicted_arrival,
            predicted_delay_minutes=current_delay,
            model_version="BaselineB_SchedulePlusDelay",
            data_quality=quality
        )

class BaselineC_Historical(BaseForecaster):
    """
    Predicts ETA = scheduled arrival + historical_mean_delay_at_target.
    Falls back to BaselineB if no historical data exists.
    """
    def predict(
        self, 
        train_no: str, 
        target_station_code: str, 
        current_state: TrainStateEntry,
        schedule: List[Dict[str, Any]],
        historical_data: HistoricalStateEngine
    ) -> Optional[Prediction]:
        
        target_schedule = next((s for s in schedule if s['station_code'] == target_station_code), None)
        if not target_schedule or not target_schedule.get('scheduled_arrival'):
            return None
            
        sched_arrival = target_schedule['scheduled_arrival']
        
        # Get historical data
        day_of_week = datetime.now(IST).weekday()
        hist_stats = historical_data.get_historical_delay(train_no, target_station_code, day_of_week)
        
        if hist_stats and 'mean' in hist_stats:
            predicted_delay = hist_stats['mean']
            predicted_arrival = sched_arrival + timedelta(minutes=predicted_delay)
            model_ver = "BaselineC_Historical"
        else:
            # Fallback to current delay (Baseline B)
            predicted_delay = current_state.current_delay_minutes
            predicted_arrival = sched_arrival + timedelta(minutes=predicted_delay)
            model_ver = "BaselineB_SchedulePlusDelay (Fallback)"
            
        quality = DataQuality.FULL
        if current_state.is_stale:
            quality = DataQuality.STALE
        if current_state.is_dead:
            quality = DataQuality.FALLBACK
            
        return self._create_prediction(
            train_no=train_no,
            target_station_code=target_station_code,
            predicted_arrival=predicted_arrival,
            predicted_delay_minutes=predicted_delay,
            model_version=model_ver,
            data_quality=quality
        )
