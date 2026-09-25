import logging
from datetime import datetime
from typing import Dict, Any, Tuple, Optional

from ..state.train_state import TrainStateEngine
from ..state.network_state import NetworkStateEngine
from ..state.historical_state import HistoricalStateEngine
from ..models.domain import DataQuality

logger = logging.getLogger(__name__)

class FeatureEngine:
    """
    Computes feature vectors for ETA prediction using current state,
    schedule, and historical data.
    """
    
    def __init__(
        self,
        train_state_engine: TrainStateEngine,
        network_state_engine: NetworkStateEngine,
        historical_state_engine: HistoricalStateEngine
    ):
        self.train_state = train_state_engine
        self.network_state = network_state_engine
        self.historical_state = historical_state_engine
        self._cache: Dict[tuple, tuple] = {} # (train_no, target_station, timestamp) -> (features, quality)
        
    def compute_features(
        self, 
        train_no: str, 
        target_station_code: str, 
        timestamp: datetime
    ) -> Tuple[Dict[str, Any], DataQuality]:
        """
        Compute features for a specific train and target station at a given time.
        Returns a tuple of (feature_dict, data_quality).
        """
        cache_key = (train_no, target_station_code, timestamp)
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        features: Dict[str, Any] = {}
        data_quality = DataQuality.FULL
        fallback_features = []
        live_features = []
        
        # 1. Get Train State
        train_entry = self.train_state.get_train(train_no)
        if not train_entry:
            return {}, DataQuality.FALLBACK
            
        if train_entry.is_dead:
            data_quality = DataQuality.FALLBACK
        elif train_entry.is_stale:
            data_quality = DataQuality.STALE
            
        # Train features
        features['current_delay_minutes'] = train_entry.current_delay_minutes
        features['delay_change_from_previous'] = train_entry.delay_change
        features['journey_progress'] = train_entry.journey_progress
        features['stations_completed'] = train_entry.current_station_index + 1
        features['stations_remaining'] = train_entry.total_stations - (train_entry.current_station_index + 1)
        
        # Distance calculation (simplified, assumes route info is somehow available)
        # We would ideally get this from route data, but keeping simple for now
        features['distance_completed_km'] = None 
        features['distance_remaining_km'] = None
        
        # 2. Schedule Features
        day_of_week = timestamp.weekday()
        features['time_of_day_departure'] = timestamp.hour
        features['day_of_week'] = day_of_week
        features['is_weekend'] = 1 if day_of_week >= 5 else 0
        features['scheduled_running_time_to_target'] = None
        features['scheduled_dwell_times_remaining'] = None
        
        # 3. Historical Features
        hist_stats = self.historical_state.get_historical_delay(train_no, target_station_code, day_of_week)
        if hist_stats:
            features['historical_mean_delay_at_target'] = hist_stats.get('mean')
            features['historical_median_delay_at_target'] = hist_stats.get('median')
            features['historical_p90_delay_at_target'] = hist_stats.get('p90')
            features['historical_std_delay_at_target'] = hist_stats.get('std')
            features['historical_delay_dow'] = hist_stats.get('mean')
        else:
            features['historical_mean_delay_at_target'] = None
            features['historical_median_delay_at_target'] = None
            features['historical_p90_delay_at_target'] = None
            features['historical_std_delay_at_target'] = None
            features['historical_delay_dow'] = None
            
        # Find the next section ID to look up recovery
        remaining_stations = train_entry.remaining_stations
        if remaining_stations:
            next_station = remaining_stations[0]
            section_id = f"{train_entry.current_station_code}->{next_station}"
            features['historical_recovery_rate'] = self.historical_state.get_delay_recovery_rate(train_no, section_id)
        else:
            features['historical_recovery_rate'] = 0.0
            
        rel_stats = self.historical_state.get_train_reliability(train_no)
        if rel_stats:
            features['train_reliability_score'] = rel_stats.get('on_time_pct')
        else:
            features['train_reliability_score'] = None
            
        # 4. Network Features
        if remaining_stations:
            next_station = remaining_stations[0]
            section_id = f"{train_entry.current_station_code}->{next_station}"
            
            features['section_congestion_score'] = self.network_state.get_section_congestion(section_id)
            
            section_state = self.network_state.get_section_state(section_id)
            features['section_train_count'] = section_state.occupancy_count if section_state else 0
            
            headway = self.network_state.get_section_headway(train_no, section_id)
            features['headway_minutes'] = headway
            
            prec_train = self.train_state.get_preceding_train(train_no, train_entry.current_station_code, next_station)
            if prec_train:
                features['preceding_train_delay'] = prec_train.current_delay_minutes
            else:
                features['preceding_train_delay'] = None
                
            features['shared_section_count'] = len(self.network_state.get_shared_sections(train_no))
        else:
            features['section_congestion_score'] = None
            features['section_train_count'] = None
            features['headway_minutes'] = None
            features['preceding_train_delay'] = None
            features['shared_section_count'] = None
            
        # 5. Train type features
        # Need train details, assume it's passed or available. We'll set all to 0 for now as placeholder
        for t_type in ['is_rajdhani', 'is_shatabdi', 'is_superfast', 'is_mail_express', 'is_passenger']:
            features[t_type] = 0
            
        self._cache[cache_key] = (features, data_quality)
        return features, data_quality

