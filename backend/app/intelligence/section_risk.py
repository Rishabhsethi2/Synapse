import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from ..config import settings
from ..models.domain import RiskAssessment

logger = logging.getLogger(__name__)
IST = ZoneInfo(settings.TIMEZONE)

class SectionRiskScorer:
    """
    Computes risk score for each remaining section of a route.
    Risk is based on model predictions and network observations.
    """
    
    def score_sections(
        self, 
        section_factors: list[dict], 
        predictions_by_section: dict[str, dict]
    ) -> list[RiskAssessment]:
        """
        Returns a sorted list of RiskAssessments for the provided sections.
        section_factors: factors from NetworkStateEngine
        predictions_by_section: mapping of section_id to expected delta delay and uncertainty growth
        """
        assessments = []
        
        for sf in section_factors:
            section_id = sf.get("section_id")
            preds = predictions_by_section.get(section_id, {})
            
            exp_marginal = preds.get('expected_marginal_delay', 0.0)
            unc_growth = preds.get('uncertainty_growth', 0.0)
            
            # Congestion factor from actual network state
            occupancy = sf.get('current_occupancy', 0)
            congestion_factor = max(1.0, float(occupancy))
            
            # Historical volatility (mocked here, should come from stats)
            hist_vol = preds.get('historical_volatility', 1.0)
            
            # Formula: (marginal_delay_impact) * congestion * volatility + uncertainty_penalty
            risk_score = (max(0, exp_marginal) * congestion_factor * hist_vol) + (unc_growth * 0.5)
            
            factors = []
            if exp_marginal > 2:
                factors.append("ACCUMULATION_ZONE")
            elif exp_marginal < -2:
                factors.append("RECOVERY_ZONE")
                
            if congestion_factor > 1.5:
                factors.append("HIGH_CONGESTION")
                
            assessments.append(RiskAssessment(
                section_id=section_id,
                generated_at=datetime.now(IST),
                risk_score=float(risk_score),
                expected_marginal_delay=float(exp_marginal),
                uncertainty_growth=float(unc_growth),
                congestion_factor=float(congestion_factor),
                historical_volatility=float(hist_vol),
                contributing_factors=factors
            ))
            
        assessments.sort(key=lambda x: x.risk_score, reverse=True)
        return assessments
