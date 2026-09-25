import logging
from datetime import datetime, timedelta
import numpy as np

from ..models.domain import DataQuality

logger = logging.getLogger(__name__)

class UncertaintyEngine:
    """
    Computes prediction intervals from quantile regression outputs,
    adjusted by data quality state.
    """
    
    METHODOLOGY = "QUANTILE_REGRESSION"
    
    def compute_interval(
        self, 
        q10: float, 
        q50: float, 
        q90: float, 
        data_quality: DataQuality,
        scheduled_arrival: datetime
    ) -> tuple[datetime, datetime]:
        """
        Computes the lower and upper bounds of the ETA based on quantiles and data quality.
        Widens the interval when data quality is degraded.
        """
        base_width = q90 - q10
        if base_width < 0:
            base_width = 0
            
        multiplier = 1.0
        if data_quality == DataQuality.DEGRADED:
            multiplier = 1.3
        elif data_quality == DataQuality.STALE:
            multiplier = 1.6
        elif data_quality == DataQuality.FALLBACK:
            multiplier = 2.0
            
        widened_width = base_width * multiplier
        
        # Center the widened interval around the median (q50)
        half_width = widened_width / 2.0
        lower_minutes = q50 - half_width
        upper_minutes = q50 + half_width
        
        lower_bound = scheduled_arrival + timedelta(minutes=lower_minutes)
        upper_bound = scheduled_arrival + timedelta(minutes=upper_minutes)
        
        return lower_bound, upper_bound
        
    def evaluate_calibration(self, predictions: list[dict], actuals: list[float]) -> dict:
        """
        Evaluates the calibration of the prediction intervals.
        predictions: list of dicts with 'q10', 'q50', 'q90' keys
        actuals: list of actual delay values
        """
        if not predictions or not actuals or len(predictions) != len(actuals):
            return {}
            
        coverage = 0
        widths = []
        
        for pred, act in zip(predictions, actuals):
            q10 = pred.get('q10', 0)
            q90 = pred.get('q90', 0)
            widths.append(q90 - q10)
            
            if q10 <= act <= q90:
                coverage += 1
                
        return {
            "methodology": self.METHODOLOGY,
            "coverage_percentage": (coverage / len(actuals)) * 100.0,
            "mean_width_minutes": float(np.mean(widths)) if widths else 0.0,
            "samples": len(actuals)
        }
