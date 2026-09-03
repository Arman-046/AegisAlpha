from typing import List, Dict, Any
from app_logging.logger import get_logger

log = get_logger(__name__)

def rank_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Ranks filtered opportunities deterministically using an Engineering Quality Score.
    
    IMPORTANT ARCHITECTURAL NOTE:
    This 0-100 score is strictly an Engineering Quality Score. It is NOT a prediction of 
    profitability, probability of profit, or expected value. It exists solely to rank 
    valid candidates deterministically based on available, validated inputs.
    
    Components & Weights (Arbitrary Engineering Heuristics):
    1. AI Confidence (Weight: 40%): Propagates the AI's internal confidence (0.0 to 1.0).
    2. Market Context (Weight: 20%): Prefers lower volatility regimes to minimize premium decay risks.
       - "LOW": 20 pts, "NORMAL": 10 pts, "HIGH": 0 pts.
    3. Option Quality (Weight: 20%): Evaluates proximity to 0.50 Delta (At-The-Money).
       - Formula: max(0, 20 - (abs(abs(delta) - 0.5) * 40))
       - Missing delta yields default 0.5 delta_dist, resulting in 0 points.
    4. Liquidity (Weight: 20%): Evaluates bid-ask spread.
       - Formula: max(0, 20 - (spread * 20))
       - 0.0 spread = 20 pts, >1.0 spread = 0 pts. Missing/wide spread penalizes heavily.
       
    The final score is bounded to 0-100.
    """
    log.info(f"Ranking {len(opportunities)} valid candidates. All input candidates have already passed deterministic rejection filters.")
    for opp in opportunities:
        score_components = {
            "ai_confidence": 0.0,
            "market_context": 0.0,
            "option_quality": 0.0,
            "liquidity": 0.0
        }
        
        # 1. AI Confidence (Max 40 points)
        conf = opp.get("confidence", 0.0)
        score_components["ai_confidence"] = conf * 40.0
        
        # 2. Market Context (Max 20 points)
        regime = opp.get("vol_regime", "Normal").upper()
        if "LOW" in regime:
            score_components["market_context"] = 20.0
        elif "NORMAL" in regime:
            score_components["market_context"] = 10.0
        else:
            score_components["market_context"] = 0.0
            
        # 3. Option Quality (Max 20 points)
        # Closer to 50 delta (0 delta_dist) is better.
        delta_dist = opp.get("delta_dist", 0.5) 
        option_quality = max(0.0, 20.0 - (delta_dist * 40.0))
        score_components["option_quality"] = option_quality
        
        # 4. Liquidity (Max 20 points)
        spread = opp.get("spread", 1.0)
        # 0.0 spread = 20 points, 1.0+ spread = 0 points
        liquidity = max(0.0, 20.0 - (spread * 20.0))
        score_components["liquidity"] = liquidity
        
        total_score = sum(score_components.values())
        opp["rank_score"] = min(100.0, max(0.0, total_score))
        opp["score_breakdown"] = score_components
        
    ranked = sorted(opportunities, key=lambda x: x["rank_score"], reverse=True)
    
    if ranked:
        log.info(f"Top Ranked Opportunity: {ranked[0]['symbol']} (Score: {ranked[0]['rank_score']:.2f})")
        
    return ranked
