from typing import Optional, Any
from abc import ABC, abstractmethod
import uuid
import time
from app_logging.logger import get_logger
from execution.orders import submit_limit_order as alpaca_submit_limit_order

log = get_logger(__name__)

class ExecutionEngine(ABC):
    @abstractmethod
    def submit_limit_order(self, symbol: str, qty: int, bid: float, ask: float, side: str) -> Optional[Any]:
        pass

class LivePaperExecutionEngine(ExecutionEngine):
    def submit_limit_order(self, symbol: str, qty: int, bid: float, ask: float, side: str = "BUY") -> Optional[Any]:
        from alpaca.trading.enums import OrderSide
        alpaca_side = OrderSide.BUY if side.upper() == "BUY" else OrderSide.SELL
        return alpaca_submit_limit_order(symbol, qty, bid, ask, alpaca_side)

class DemoExecutionEngine(ExecutionEngine):
    def __init__(self, portfolio):
        self.portfolio = portfolio

    def submit_limit_order(self, symbol: str, qty: int, bid: float, ask: float, side: str = "BUY") -> Optional[Any]:
        if ask <= bid or ask <= 0:
            log.warning(f"[DEMO] Invalid bid/ask for {symbol}: Bid {bid}, Ask {ask}.")
            return None
            
        midpoint = round((bid + ask) / 2.0, 2)
        
        client_order_id = f"demo_trader_{uuid.uuid4().hex[:12]}"
        
        # Simulate order object
        class DemoOrder:
            def __init__(self, id, symbol, qty, side, limit_price):
                self.id = id
                self.symbol = symbol
                self.qty = qty
                self.side = side
                self.limit_price = limit_price
                self.status = "filled"
                self.filled_qty = qty
                self.filled_avg_price = limit_price
                self.submitted_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                
        order = DemoOrder(client_order_id, symbol, qty, side, midpoint)
        
        log.info(f"[DEMO] Simulated {side} Order for {qty} of {symbol} at ${midpoint}")
        
        # Simulate fill in demo portfolio
        self.portfolio.simulate_fill(order)
        
        return order
