import datetime
from typing import List, Any, Optional
from config.settings import settings
from app_logging.logger import get_logger

log = get_logger(__name__)

def select_contract_with_snapshot(contracts: List[Any], direction: str):
    """
    Deterministically selects the best option contract from the available contracts.
    Filters by DTE and Type first, picks the top 20, fetches targeted snapshots, and selects the best.
    direction: "bullish" -> Call, "bearish" -> Put
    
    Returns (option_symbol, snapshot) if found, else (None, None).
    """
    if not contracts:
        return None, None
        
    now = datetime.datetime.now(datetime.timezone.utc).date()
    target_type = "call" if direction == "bullish" else "put"
    
    # 1. Filter locally first
    filtered_contracts = []
    for contract in contracts:
        if contract.type.value != target_type:
            continue
            
        if not contract.expiration_date:
            continue
            
        expiration_date = contract.expiration_date
        if isinstance(expiration_date, str):
            expiration_date = datetime.datetime.strptime(expiration_date, "%Y-%m-%d").date()
            
        dte = (expiration_date - now).days
        if dte < settings.MIN_DTE or dte > settings.MAX_DTE:
            continue
            
        filtered_contracts.append({
            "symbol": contract.symbol,
            "dte": dte
        })
        
    if not filtered_contracts:
        log.info(f"No valid {target_type} contracts found matching DTE criteria.")
        return None, None
        
    # Sort just by DTE to grab the closest to target range (or just take all if few)
    # Since we don't have moneyness without snapshots, we'll just take up to config limit contracts
    # and fetch snapshots for them. If there are too many strikes, we should ideally filter by strike.
    filtered_contracts.sort(key=lambda x: x["dte"])
    top_candidates = [c["symbol"] for c in filtered_contracts[:settings.MAX_TARGETED_OPTION_SNAPSHOTS]]
    
    from data.fetchers import fetch_targeted_option_snapshots
    snapshots = fetch_targeted_option_snapshots(top_candidates)
    
    if not snapshots:
        return None, None
        
    valid_candidates = []
    
    for opt_sym, snapshot in snapshots.items():
        if not snapshot.latest_quote:
            continue
            
        q = snapshot.latest_quote
        if q.bid_price is None or q.ask_price is None:
            continue
            
        if q.bid_price <= 0.0 or q.ask_price <= q.bid_price:
            continue
            
        spread = q.ask_price - q.bid_price
        oi = snapshot.open_interest if hasattr(snapshot, "open_interest") and snapshot.open_interest else 0
        
        if oi < 10: # Reject extremely illiquid options
            continue
            
        delta_dist = 0.5
        if hasattr(snapshot, "implied_volatility") and snapshot.implied_volatility:
            if hasattr(snapshot, "greeks") and snapshot.greeks:
                delta = snapshot.greeks.delta
                if delta is not None:
                    delta_dist = abs(abs(delta) - 0.5)
                    
        valid_candidates.append({
            "symbol": opt_sym,
            "dte": next((c["dte"] for c in filtered_contracts if c["symbol"] == opt_sym), 0),
            "spread": spread,
            "oi": oi,
            "delta_dist": delta_dist,
            "ask_price": q.ask_price,
            "snapshot": snapshot
        })
        
    if not valid_candidates:
        log.info(f"No valid {target_type} contracts found after snapshot liquidity check.")
        return None, None
        
    # Rank candidates: 
    valid_candidates.sort(key=lambda x: (x["delta_dist"], -x["oi"], x["spread"]))
    
    best_contract = valid_candidates[0]
    log.info(f"Selected contract: {best_contract['symbol']} (DTE: {best_contract['dte']}, OI: {best_contract['oi']})")
    
    return best_contract['symbol'], best_contract['snapshot']
