import logging

logger = logging.getLogger(__name__)

class PropagationEstimator:
    """
    Estimates potential downstream impact of a train's delay on other trains
    using the network graph and shared sections.
    """
    
    METHODOLOGY = 'MODEL-ESTIMATED PROPAGATION'
    
    def __init__(self, damping_factor: float = 0.5):
        self.damping_factor = damping_factor
        
    def estimate_impact(
        self, 
        source_train_id: str, 
        source_delay_minutes: float, 
        section_id: str, 
        network_state_engine
    ) -> list[dict]:
        """
        Estimates the delay impact on other trains sharing the given section.
        """
        impacts = []
        
        if not network_state_engine:
            return impacts
            
        shared_trains = network_state_engine.get_trains_sharing_section(section_id)
        
        for other_train in shared_trains:
            if other_train == source_train_id:
                continue
                
            # Simple interaction model: delay propagates proportionally
            # In a full model, this would check temporal overlap on the section
            estimated_impact = source_delay_minutes * self.damping_factor
            
            if estimated_impact > 1.0: # threshold to report
                impacts.append({
                    "train_no": other_train,
                    "estimated_impact_minutes": float(estimated_impact),
                    "shared_section": section_id,
                    "confidence": "MEDIUM",
                    "methodology": self.METHODOLOGY
                })
                
        return impacts
