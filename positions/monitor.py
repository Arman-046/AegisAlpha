import datetime
from typing import List, Any
from data.clients import trading_client
from alpaca.common.exceptions import APIError
from app_logging.logger import get_logger
from config.settings import settings
from execution.orders import submit_limit_order

log = get_logger(__name__)

def evaluate_and_exit_positions(chain_snapshots: dict):
    """
    Evaluates open positions and forces deterministic exits based on hard limits.
    """
    try:
        positions = trading_client.get_all_positions()
    except APIError as e:
        log.warning(f"APIError fetching positions: {e}")
        return
    except Exception as e:
        log.error(f"Unexpected error fetching positions: {e}")
        return
        
    now = datetime.datetime.now(datetime.timezone.utc).date()
    
    for pos in positions:
        symbol = pos.symbol
        asset_class = pos.asset_class.name if hasattr(pos.asset_class, 'name') else str(pos.asset_class)
        
        if asset_class != "us_option":
            continue
            
        qty = abs(float(pos.qty))
        unrealized_pl_pc = float(pos.unrealized_plpc) if pos.unrealized_plpc else 0.0
        
        # We need the snapshot for DTE and illiquid quote protection
        snapshot = chain_snapshots.get(symbol)
        
        exit_reason = None
        
        # 1. Check Max Loss (e.g. -50%)
        # This could be configurable, hardcoding -0.5 for now as a deterministic protective stop
        if unrealized_pl_pc <= -0.50:
            exit_reason = "MAX_LOSS_BREACH"
            
        # 2. Check DTE if snapshot is available or if we parse the symbol
        # We'll parse the OCC symbol to get expiration date
        # Format: AAPL  240119C00150000 -> 240119 is YYMMDD
        try:
            from utils.occ import parse_occ_symbol
            parsed = parse_occ_symbol(symbol)
            exp_date = parsed["expiration"]
            dte = (exp_date - now).days
            
            if dte <= 2: # Exit before expiration weekend/day
                exit_reason = "MIN_DTE_BREACH"
        except Exception:
            pass # Ignore parsing errors, rely on Max Loss
            
        if exit_reason:
            log.warning(f"Deterministic Exit Triggered for {symbol}: {exit_reason}")
            
            if snapshot and snapshot.latest_quote:
                q = snapshot.latest_quote
                bid = q.bid_price
                ask = q.ask_price
                
                # Illiquid protection
                if bid is None or bid <= 0:
                    log.warning(f"Cannot exit {symbol}, bid is zero (illiquid). Holding.")
                    continue
                    
                # We want to sell to close. 
                # If we are long, we sell at the BID (or midpoint). 
                # Let's use midpoint.
                side = "SELL" if float(pos.qty) > 0 else "BUY" 
                
                submit_limit_order(
                    symbol=symbol,
                    qty=int(qty),
                    bid=bid,
                    ask=ask,
                    side=side
                )
            else:
                log.warning(f"Cannot exit {symbol}, missing pricing snapshot.")
