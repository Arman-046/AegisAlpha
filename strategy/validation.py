from typing import Dict, Any, Tuple
from app_logging.logger import get_logger

log = get_logger(__name__)

def validate_tradeability(symbol: str, contract: str, snapshot: Any, qty: int = 1) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Validates an option contract deterministically based on live Alpaca snapshot data.
    Ensures no hallucinated data. Returns (is_valid, reject_reason, metrics_dict).
    """
    metrics = {
        "liquidity_oi": 0,
        "spread": 0.0,
        "dte": "UNAVAILABLE", 
        "greeks": "UNAVAILABLE",
        "iv": "UNAVAILABLE",
        "expected_value": "UNAVAILABLE", # Cannot be reliably calculated without arbitrary probability assumptions
        "max_loss": 0.0
    }
    
    from utils.occ import parse_occ_symbol
    import datetime
    try:
        occ_data = parse_occ_symbol(contract)
        expiration = occ_data["expiration"]
        now = datetime.datetime.now(datetime.timezone.utc).date()
        metrics["dte"] = (expiration - now).days
    except Exception:
        metrics["dte"] = "UNAVAILABLE"

    
    if not snapshot or not snapshot.latest_quote:
        return False, "DATA UNAVAILABLE", metrics
        
    q = snapshot.latest_quote
    if getattr(q, "bid_price", None) is None or getattr(q, "ask_price", None) is None:
        return False, "DATA UNAVAILABLE", metrics
        
    if q.bid_price <= 0.0 or q.ask_price <= q.bid_price:
        return False, "OPTION ILLIQUID", metrics
        
    spread = q.ask_price - q.bid_price
    metrics["spread"] = spread
    
    if hasattr(snapshot, "open_interest") and snapshot.open_interest:
        metrics["liquidity_oi"] = snapshot.open_interest
        if snapshot.open_interest < 10:
            return False, "OPTION ILLIQUID", metrics
            
    if hasattr(snapshot, "implied_volatility") and snapshot.implied_volatility:
        metrics["iv"] = snapshot.implied_volatility
        
    if hasattr(snapshot, "greeks") and snapshot.greeks:
        metrics["greeks"] = {
            "delta": getattr(snapshot.greeks, "delta", None),
            "gamma": getattr(snapshot.greeks, "gamma", None),
            "theta": getattr(snapshot.greeks, "theta", None),
            "vega": getattr(snapshot.greeks, "vega", None),
            "rho": getattr(snapshot.greeks, "rho", None)
        }
        
    metrics["max_loss"] = q.ask_price * 100 * qty
    
    # Deterministic risk check based on market structure
    if spread > 1.50:
        return False, "SPREAD TOO WIDE", metrics
        
    return True, "", metrics
