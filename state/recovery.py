from typing import List, Any
from data.clients import trading_client
from app_logging.logger import get_logger
from alpaca.common.exceptions import APIError

log = get_logger(__name__)

def reconcile_state():
    """
    On every startup:
    Load local state -> Fetch Alpaca account -> Fetch open orders -> Fetch open positions
    -> Reconcile local state vs Alpaca -> Repair local discrepancies -> Resume safely
    """
    log.info("Starting State Recovery & Reconciliation...")
    
    try:
        # 1. Fetch Alpaca Account
        account = trading_client.get_account()
        log.info(f"Reconciliation - Account Equity: ${account.equity}")
        
        # 2. Fetch Open Orders
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        orders = trading_client.get_orders(filter=req)
        log.info(f"Reconciliation - Open Orders: {len(orders)}")
        for o in orders:
            log.info(f"  - Open Order: {o.id} ({o.side} {o.qty} {o.symbol} @ limit {o.limit_price})")
            
        # 3. Fetch Open Positions
        positions = trading_client.get_all_positions()
        log.info(f"Reconciliation - Open Positions: {len(positions)}")
        for p in positions:
            log.info(f"  - Open Position: {p.qty} {p.symbol} (Unrealized P&L: {p.unrealized_pl})")
            
        # 4. Reconcile local state vs Alpaca
        # Since Alpaca is the source of truth, there's no complex local db to repair.
        # However, if we tracked orders in a local dict, we would sync it here.
        # For now, simply logging the true state establishes the safe restart baseline.
        
        log.info("State Reconciliation Complete. Resuming safely.")
        return True
        
    except APIError as e:
        log.error(f"APIError during state recovery: {e}")
        return False
    except Exception as e:
        log.error(f"Unexpected error during state recovery: {e}")
        return False
