from typing import List, Dict, Any
from app_logging.logger import get_logger

log = get_logger(__name__)

def rank_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks filtered opportunities deterministically.
    Input opps should contain:
    - symbol
    - contract
    - confidence (adjusted by risk manager)
    - direction
    - spread
    - delta_dist
    - vol_regime ("Low", "Normal", "High")
    
    Returns a sorted list (highest score first).
    """
    log.info(f"Ranking {len(opportunities)} valid candidates. All input candidates have already passed deterministic rejection filters.")
    for opp in opportunities:
        score = 0.0
        
        # Base score is confidence (0.0 to 1.0) * 100
        score += opp.get("confidence", 0.0) * 100
        
        # Volatility Regime Bonus (e.g., Higher vol = higher premium, could be better or worse depending on strategy)
        regime = opp.get("vol_regime", "Normal")
        regime_upper = regime.upper()
        if "LOW" in regime_upper:
            score += 5 # Favorable for buying options (lower IV)
        elif "HIGH" in regime_upper:
            score -= 5 # Unfavorable for buying options (higher IV crush risk)
            
        # Spread penalty
        spread = opp.get("spread", 1.0)
        score -= (spread * 10) # Penetrate score for wide spreads
        
        # Delta distance penalty (closer to 50 delta is better)
        delta_dist = opp.get("delta_dist", 0.5)
        score -= (delta_dist * 20)
        
        opp["rank_score"] = score
        
    ranked = sorted(opportunities, key=lambda x: x["rank_score"], reverse=True)
    
    if ranked:
        log.info(f"Top Ranked Opportunity: {ranked[0]['symbol']} (Score: {ranked[0]['rank_score']:.2f})")
        
    return ranked
