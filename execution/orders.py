import uuid
from typing import Optional, Any
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass
from data.clients import trading_client
from alpaca.common.exceptions import APIError
from app_logging.logger import get_logger

log = get_logger(__name__)

def submit_limit_order(symbol: str, qty: int, bid: float, ask: float, side: OrderSide = OrderSide.BUY) -> Optional[Any]:
    """
    Submits a limit order at the midpoint price.
    """
    if ask <= bid or ask <= 0:
        log.warning(f"Invalid bid/ask for {symbol}: Bid {bid}, Ask {ask}. Cannot submit order.")
        return None
        
    midpoint = round((bid + ask) / 2.0, 2)
    
    # Generate unique client order ID to prevent duplicates
    client_order_id = f"trader_{uuid.uuid4().hex[:12]}"
    
    req = LimitOrderRequest(
        symbol=symbol,
        qty=qty,
        side=side,
        time_in_force=TimeInForce.DAY,
        limit_price=midpoint,
        client_order_id=client_order_id
    )
    
    try:
        order = trading_client.submit_order(req)
        log.info(f"Submitted Limit {side.name} Order for {qty} of {symbol} at ${midpoint} (ID: {order.id})")
        return order
    except APIError as e:
        log.error(f"APIError submitting order for {symbol}: {e}")
        return None
    except Exception as e:
        log.error(f"Unexpected error submitting order for {symbol}: {e}")
        return None
