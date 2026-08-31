import time
from typing import List, Dict, Any

class DemoPortfolio:
    def __init__(self):
        self.reset_demo()

    def reset_demo(self):
        self.start_equity = 100000.0
        self.cash = 100000.0
        self.equity = 100000.0
        self.positions = {}  # {symbol: {"qty": int, "avg_price": float, "market_value": float}}
        self.orders = []
        self.fills = []
        self.realized_pl = 0.0
        self.unrealized_pl = 0.0
        self.trade_count = 0
        self.wins = 0
        self.losses = 0
        self.max_drawdown = 0.0
        self.peak_equity = 100000.0

    def simulate_fill(self, order):
        self.orders.append(order)
        cost = order.qty * order.limit_price * 100 # Options multiplier
        
        if order.side.upper() == "BUY":
            if self.cash < cost:
                raise ValueError("Insufficient cash in DemoPortfolio.")
                
            self.cash -= cost
            if order.symbol in self.positions:
                pos = self.positions[order.symbol]
                total_cost = (pos["qty"] * pos["avg_price"] * 100) + cost
                total_qty = pos["qty"] + order.qty
                pos["qty"] = total_qty
                pos["avg_price"] = (total_cost / 100) / total_qty
                pos["market_value"] = total_qty * order.limit_price * 100
            else:
                self.positions[order.symbol] = {
                    "qty": order.qty,
                    "avg_price": order.limit_price,
                    "market_value": cost
                }
        self.fills.append({
            "symbol": order.symbol,
            "qty": order.qty,
            "price": order.limit_price,
            "side": order.side,
            "time": order.submitted_at
        })
        self._update_equity()
        
    def simulate_exit(self, symbol: str, exit_price: float):
        """Simulate closing a position for the demo scenario."""
        if symbol not in self.positions:
            return
            
        pos = self.positions.pop(symbol)
        proceeds = pos["qty"] * exit_price * 100
        cost_basis = pos["qty"] * pos["avg_price"] * 100
        pl = proceeds - cost_basis
        
        self.cash += proceeds
        self.realized_pl += pl
        self.trade_count += 1
        
        if pl > 0:
            self.wins += 1
        else:
            self.losses += 1
            
        self._update_equity()
        
    def _update_equity(self):
        pos_value = sum(p["qty"] * p["avg_price"] * 100 for p in self.positions.values()) # In demo, assume mark is avg_price unless updated
        self.equity = self.cash + pos_value
        self.unrealized_pl = 0.0 # Without live data feed for demo positions, unrealized is 0 initially.
        
        if self.equity > self.peak_equity:
            self.peak_equity = self.equity
            
        dd = (self.peak_equity - self.equity) / self.peak_equity
        if dd > self.max_drawdown:
            self.max_drawdown = dd

    def get_mock_alpaca_positions(self) -> List[Any]:
        class MockPosition:
            def __init__(self, symbol, qty, avg_price):
                self.symbol = symbol
                self.qty = str(qty)
                self.cost_basis = str(qty * avg_price * 100)
                self.asset_class = "us_option"
        return [MockPosition(sym, p["qty"], p["avg_price"]) for sym, p in self.positions.items()]

demo_portfolio = DemoPortfolio()
