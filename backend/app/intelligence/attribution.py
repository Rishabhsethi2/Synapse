import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import settings
from ..models.domain import Attribution, AttributionFactor, Direction

logger = logging.getLogger(__name__)
IST = ZoneInfo(settings.TIMEZONE)

class AttributionEngine:
    """
    Maps raw feature contributions to human-readable factors.
    Uses model's feature contributions (like SHAP).
    """
    
    METHODOLOGY = 'MODEL_FEATURE_CONTRIBUTION'
    
    FEATURE_MAP = {
        'current_delay_minutes': 'Current accumulated delay',
        'preceding_train_delay': 'Preceding train delay',
        'section_congestion_score': 'Section congestion',
        'historical_mean_delay': 'Historical pattern',
        'delay_change_from_previous': 'Recent delay trend',
        'distance_from_origin_km': 'Journey progression',
        'cumulative_journey_fraction': 'Journey progression',
        'is_weekend': 'Weekend schedule pattern',
        'day_of_week': 'Weekly schedule pattern'
    }
    
    def get_attribution(
        self, 
        train_id: str, 
        station_code: str, 
        feature_contributions: dict[str, float]
    ) -> Attribution:
        """
        Creates an Attribution object from raw feature contributions.
        """
        factors = []
        
        if not feature_contributions:
            return Attribution(
                train_id=train_id,
                station_code=station_code,
                generated_at=datetime.now(IST),
                factors=[]
            )
            
        for feat, contrib in feature_contributions.items():
            if abs(contrib) < 0.1: # filter out negligible contributions
                continue
                
            readable_name = self.FEATURE_MAP.get(feat, feat)
            
            direction = Direction.NEUTRAL
            if contrib > 0:
                direction = Direction.INCREASING_DELAY
            elif contrib < 0:
                direction = Direction.DECREASING_DELAY
                
            factors.append(AttributionFactor(
                name=readable_name,
                contribution_minutes=contrib,
                direction=direction,
                methodology=self.METHODOLOGY
            ))
            
        # Sort factors by absolute contribution, descending
        factors.sort(key=lambda x: abs(x.contribution_minutes), reverse=True)
        
        return Attribution(
            train_id=train_id,
            station_code=station_code,
            generated_at=datetime.now(IST),
            factors=factors
        )
