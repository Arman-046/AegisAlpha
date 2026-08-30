import os
import json
import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from config.settings import settings

def analyze():
    client = TradingClient(settings.APCA_API_KEY_ID, settings.APCA_API_SECRET_KEY, paper=True)
    
    account = client.get_account()
    positions = client.get_all_positions()
    
    req = GetOrdersRequest(status=QueryOrderStatus.ALL)
    orders = client.get_orders(filter=req)
    
    total_trades = 0
    winning_trades = 0
    losing_trades = 0
    total_realized_pl = 0.0
    
    # We can try to fetch activities to get realized P&L accurately, but let's parse closed orders if possible
    # For now, let's just grab the portfolio history
    try:
        from alpaca.trading.requests import GetPortfolioHistoryRequest
        from alpaca.trading.enums import TimeFrame
        hist_req = GetPortfolioHistoryRequest(period="1M", timeframe=TimeFrame.Day)
        hist = client.get_portfolio_history(hist_req)
        start_equity = hist.equity[0] if hist.equity else float(account.equity)
    except Exception as e:
        print(f"History error: {e}")
        start_equity = 100000.0
        
    current_equity = float(account.equity)
    total_pl = current_equity - start_equity
    pl_pct = (total_pl / start_equity) * 100 if start_equity > 0 else 0
    
    print("========================================")
    print("AUTONOMOUS TRADING PERFORMANCE")
    print("========================================")
    print(f"Starting Equity: ${start_equity:.2f}")
    print(f"Current Equity:  ${current_equity:.2f}")
    print(f"Current Cash:    ${float(account.cash):.2f}")
    print(f"Buying Power:    ${float(account.buying_power):.2f}")
    print(f"Total P&L:       ${total_pl:.2f}")
    print(f"Return:          {pl_pct:.2f}%")
    print("")
    print(f"Current Open Positions: {len(positions)}")
    for p in positions:
        print(f"  {p.qty}x {p.symbol} - Unrealized P&L: ${float(p.unrealized_pl):.2f}")
        
    closed_orders = [o for o in orders if o.status.name == 'FILLED']
    print(f"\nTotal Filled Orders (Legs): {len(closed_orders)}")
    
    print("\n========================================")

if __name__ == "__main__":
    analyze()
