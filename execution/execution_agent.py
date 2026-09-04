import datetime
from typing import List, Any
from data.clients import trading_client
from alpaca.common.exceptions import APIError
from app_logging.logger import get_logger
from execution.orders import submit_limit_order

log = get_logger(__name__)

# Simple in-memory tracker for high water marks to calculate trailing stops
# Map of symbol -> max_unrealized_pl_pc
high_water_marks = {}

def evaluate_and_exit_positions(chain_snapshots: dict):
    """
    Execution Agent: Evaluates open positions and manages dynamic trailing stops
    and deterministic exits (Max Loss / DTE).
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
    
    # Cleanup closed positions from tracker
    current_symbols = {p.symbol for p in positions}
    keys_to_remove = [s for s in high_water_marks if s not in current_symbols]
    for k in keys_to_remove:
        del high_water_marks[k]
    
    for pos in positions:
        symbol = pos.symbol
        asset_class = pos.asset_class.name if hasattr(pos.asset_class, 'name') else str(pos.asset_class)
        
        if asset_class != "us_option":
            continue
            
        qty = abs(float(pos.qty))
        unrealized_pl_pc = float(pos.unrealized_plpc) if pos.unrealized_plpc else 0.0
        
        # Update high water mark
        if symbol not in high_water_marks:
            high_water_marks[symbol] = unrealized_pl_pc
        else:
            high_water_marks[symbol] = max(high_water_marks[symbol], unrealized_pl_pc)
            
        hwm = high_water_marks[symbol]
        
        snapshot = chain_snapshots.get(symbol)
        exit_reason = None
        
        # 1. Dynamic Trailing Stop Logic
        # If we have reached a good profit (e.g., > 20%), trail by 15% from the high water mark
        if hwm >= 0.20:
            if unrealized_pl_pc <= hwm - 0.15:
                exit_reason = "TRAILING_STOP_BREACH"
        else:
            # 2. Hard Max Loss (e.g. -50%)
            if unrealized_pl_pc <= -0.50:
                exit_reason = "MAX_LOSS_BREACH"
            
        # 3. Check DTE
        try:
            from utils.occ import parse_occ_symbol
            parsed = parse_occ_symbol(symbol)
            exp_date = parsed["expiration"]
            dte = (exp_date - now).days
            
            if dte <= 2: # Exit before expiration weekend/day
                exit_reason = "MIN_DTE_BREACH"
        except Exception:
            pass
            
        if exit_reason:
            log.warning(f"Execution Agent Triggered Exit for {symbol}: {exit_reason} (P&L: {unrealized_pl_pc*100:.1f}%)")
            
            if snapshot and snapshot.latest_quote:
                q = snapshot.latest_quote
                bid = q.bid_price
                ask = q.ask_price
                
                if bid is None or bid <= 0:
                    log.warning(f"Cannot exit {symbol}, bid is zero (illiquid). Holding.")
                    continue
                    
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
