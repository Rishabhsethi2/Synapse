import logging
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class HistoricalStateEngine:
    """
    Pre-computes aggregated statistics from historical delay data.
    Stores results in memory (dicts) for fast O(1) lookup during inference.
    """
    
    def __init__(self):
        # (train_no, station_code, day_of_week) -> dict
        self._delay_stats: Dict[tuple, dict] = {}
        # (from_station, to_station) -> dict
        self._section_running_time: Dict[tuple, dict] = {}
        # (train_no, from_station, to_station) -> dict
        self._train_section_running_time: Dict[tuple, dict] = {}
        # station_code -> dict
        self._station_dwell_time: Dict[str, dict] = {}
        # (train_no, station_code) -> dict
        self._train_station_dwell_time: Dict[tuple, dict] = {}
        # train_no -> dict
        self._train_reliability: Dict[str, dict] = {}
        # (train_no, section_id) -> float
        self._recovery_rate: Dict[tuple, float] = {}

    def fit(self, df: pd.DataFrame, cutoff_date: Optional[str] = None):
        """
        Compute all historical aggregates from the dataframe.
        df should contain columns: date, train_no, station_name (or station_code), delay.
        """
        if df.empty:
            logger.warning("Empty dataframe provided to HistoricalStateEngine.fit")
            return

        # Use working copy
        work_df = df.copy()
        
        # Enforce cutoff date to avoid leakage
        if cutoff_date:
            work_df['date'] = pd.to_datetime(work_df['date'])
            work_df = work_df[work_df['date'] < pd.to_datetime(cutoff_date)]
            
        if work_df.empty:
            logger.warning("Dataframe empty after applying cutoff date")
            return
            
        # Standardize columns
        if 'station_name' in work_df.columns and 'station_code' not in work_df.columns:
            work_df['station_code'] = work_df['station_name']

        # Ensure delay is numeric
        work_df['delay'] = pd.to_numeric(work_df['delay'], errors='coerce')
        work_df = work_df.dropna(subset=['delay'])
        
        # Add day of week (0=Monday, 6=Sunday)
        work_df['date'] = pd.to_datetime(work_df['date'])
        work_df['day_of_week'] = work_df['date'].dt.dayofweek

        logger.info(f"Computing historical stats from {len(work_df)} records")

        self._compute_delay_stats(work_df)
        self._compute_train_reliability(work_df)
        self._compute_recovery_rate(work_df)
        
        logger.info("Historical state engine fitting complete")

    def _compute_delay_stats(self, df: pd.DataFrame):
        # Delay distributions per train, station, day_of_week
        grouped = df.groupby(['train_no', 'station_code', 'day_of_week'])['delay']
        
        for name, group in grouped:
            self._delay_stats[name] = {
                'mean': float(group.mean()),
                'median': float(group.median()),
                'p25': float(group.quantile(0.25)),
                'p75': float(group.quantile(0.75)),
                'p90': float(group.quantile(0.90)),
                'std': float(group.std()) if len(group) > 1 else 0.0,
                'n_obs': int(len(group))
            }
            
        # Fallback without day_of_week
        grouped_no_dow = df.groupby(['train_no', 'station_code'])['delay']
        for name, group in grouped_no_dow:
            self._delay_stats[(name[0], name[1], -1)] = {
                'mean': float(group.mean()),
                'median': float(group.median()),
                'p25': float(group.quantile(0.25)),
                'p75': float(group.quantile(0.75)),
                'p90': float(group.quantile(0.90)),
                'std': float(group.std()) if len(group) > 1 else 0.0,
                'n_obs': int(len(group))
            }

    def _compute_train_reliability(self, df: pd.DataFrame):
        # Mean delay and buckets
        grouped = df.groupby('train_no')['delay']
        for train_no, group in grouped:
            total = len(group)
            if total == 0:
                continue
                
            on_time = (group <= 15).sum()
            late = ((group > 15) & (group <= 60)).sum()
            very_late = (group > 60).sum()
            
            self._train_reliability[train_no] = {
                'mean_delay': float(group.mean()),
                'on_time_pct': float(on_time / total),
                'late_pct': float(late / total),
                'very_late_pct': float(very_late / total)
            }

    def _compute_recovery_rate(self, df: pd.DataFrame):
        # Simple heuristic: delay reduction between consecutive stations
        # A more robust approach would need proper sequence alignment.
        # Storing a simple dict for mock implementation if sequence isn't fully available.
        # Assuming df has station_no to sort properly.
        if 'station_no' in df.columns:
            df = df.sort_values(['train_no', 'date', 'station_no'])
            df['prev_delay'] = df.groupby(['train_no', 'date'])['delay'].shift(1)
            df['prev_station'] = df.groupby(['train_no', 'date'])['station_code'].shift(1)
            
            # Recovery is when delay decreases (prev_delay - delay > 0)
            valid = df.dropna(subset=['prev_delay', 'prev_station'])
            valid['recovery'] = valid['prev_delay'] - valid['delay']
            
            # Group by train, section
            grouped = valid.groupby(['train_no', 'prev_station', 'station_code'])['recovery']
            for name, group in grouped:
                train_no, from_st, to_st = name
                section_id = f"{from_st}->{to_st}"
                # mean recovery
                self._recovery_rate[(train_no, section_id)] = float(group.mean())
                
            # Generic section recovery
            grouped_sec = valid.groupby(['prev_station', 'station_code'])['recovery']
            for name, group in grouped_sec:
                from_st, to_st = name
                section_id = f"{from_st}->{to_st}"
                self._recovery_rate[('ALL', section_id)] = float(group.mean())

    def get_historical_delay(self, train_no: str, station_code: str, day_of_week: int) -> Optional[dict]:
        """Get delay stats for a train at a station on a specific day of week."""
        # Try specific day
        res = self._delay_stats.get((train_no, station_code, day_of_week))
        if res: return res
        
        # Try fallback (all days)
        res = self._delay_stats.get((train_no, station_code, -1))
        return res

    def get_section_running_time(self, from_station: str, to_station: str, train_no: Optional[str] = None) -> Optional[dict]:
        """Get running time stats for a section."""
        if train_no:
            res = self._train_section_running_time.get((train_no, from_station, to_station))
            if res: return res
        
        return self._section_running_time.get((from_station, to_station))

    def get_station_dwell_time(self, station_code: str, train_no: Optional[str] = None) -> Optional[dict]:
        """Get dwell time stats for a station."""
        if train_no:
            res = self._train_station_dwell_time.get((train_no, station_code))
            if res: return res
            
        return self._station_dwell_time.get(station_code)

    def get_train_reliability(self, train_no: str) -> Optional[dict]:
        """Get overall reliability stats for a train."""
        return self._train_reliability.get(train_no)

    def get_delay_recovery_rate(self, train_no: str, section_id: str) -> float:
        """Get typical delay recovery amount (minutes) on a section."""
        # Try train specific
        val = self._recovery_rate.get((train_no, section_id))
        if val is not None:
            return val
            
        # Try global section
        val = self._recovery_rate.get(('ALL', section_id))
        if val is not None:
            return val
            
        return 0.0
