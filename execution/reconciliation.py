import time
from typing import Optional, Any
from data.clients import trading_client
from alpaca.common.exceptions import APIError
from app_logging.logger import get_logger

log = get_logger(__name__)

def verify_order_state(order_id: str, max_retries: int = 5, sleep_sec: int = 2) -> Optional[Any]:
    """
    Polls the order status until it reaches a terminal state, 
    or max retries are hit.
    Terminal states: filled, canceled, expired, rejected.
    """
    terminal_states = ['filled', 'canceled', 'expired', 'rejected']
    
    for attempt in range(max_retries):
        try:
            order = trading_client.get_order_by_id(order_id)
            status = order.status.name.lower()
            
            if status in terminal_states:
                log.info(f"Order {order_id} reached terminal state: {status.upper()}")
                if status == 'filled':
                    filled_qty = getattr(order, 'filled_qty', 0)
                    avg_price = getattr(order, 'filled_avg_price', 0)
                    log.info(f"Filled: {filled_qty} @ {avg_price}")
                return order
                
            log.debug(f"Order {order_id} is {status.upper()}, waiting...")
            time.sleep(sleep_sec)
            
        except APIError as e:
            log.warning(f"APIError polling order {order_id}: {e}")
            time.sleep(sleep_sec)
        except Exception as e:
            log.error(f"Unexpected error polling order {order_id}: {e}")
            break
            
    log.warning(f"Order {order_id} did not reach a terminal state within polling window.")
    # We could attempt to cancel it here if it didn't fill, based on "max slippage" rules.
    return None

def cancel_order(order_id: str) -> bool:
    try:
        trading_client.cancel_order_by_id(order_id)
        log.info(f"Requested cancellation of order {order_id}")
        return True
    except Exception as e:
        log.warning(f"Failed to cancel order {order_id}: {e}")
        return False
