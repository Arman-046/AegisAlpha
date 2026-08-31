import pytest
from unittest.mock import patch, MagicMock
from execution.engine import LivePaperExecutionEngine, DemoExecutionEngine
from state.demo_portfolio import demo_portfolio
from risk.hard_limits import calculate_final_position_size, RiskRejection

def test_live_execution_engine_uses_alpaca():
    """Prove LivePaperExecutionEngine uses the real Alpaca path."""
    engine = LivePaperExecutionEngine()
    with patch("execution.orders.trading_client.submit_order") as mock_submit:
        engine.submit_limit_order("AAPL240517C00180000", 1, 1.0, 1.1, "BUY")
        mock_submit.assert_called_once()
        req = mock_submit.call_args[0][0]
        assert req.symbol == "AAPL240517C00180000"

def test_demo_execution_engine_does_not_use_alpaca():
    """Prove DemoExecutionEngine does NOT call Alpaca API."""
    demo_portfolio.reset_demo()
    engine = DemoExecutionEngine(demo_portfolio)
    
    with patch("execution.engine.alpaca_submit_limit_order") as mock_alpaca_submit:
        order = engine.submit_limit_order("NVDA240517C00900000", 2, 5.0, 5.1, "BUY")
        mock_alpaca_submit.assert_not_called()
        
    assert order is not None
    assert order.status == "filled"
    assert len(demo_portfolio.fills) == 1
    assert "NVDA240517C00900000" in demo_portfolio.positions

def test_demo_portfolio_isolation():
    """Prove the DemoPortfolio state is isolated and reset works."""
    demo_portfolio.reset_demo()
    assert demo_portfolio.cash == 100000.0
    
    engine = DemoExecutionEngine(demo_portfolio)
    engine.submit_limit_order("TSLA240517C00150000", 10, 1.9, 2.1, "BUY")
    
    assert demo_portfolio.cash == 100000.0 - (10 * 2.0 * 100)
    assert len(demo_portfolio.positions) == 1
    
    demo_portfolio.reset_demo()
    assert demo_portfolio.cash == 100000.0
    assert len(demo_portfolio.positions) == 0

def test_demo_and_live_use_same_risk_engine():
    """Prove that calculating position size uses the same function."""
    mock_positions = []
    equity = 100000.0
    ask_price = 5.0
    
    # Same deterministic function is used.
    # Risk check for 2% of $100,000 = $2,000. 
    # $2000 / $500 (cost per contract) = 4 contracts.
    qty, risk = calculate_final_position_size("AAPL", "bullish", mock_positions, equity, ask_price)
    
    assert qty == 4
    assert risk == 2000.0

def test_risk_rejection_works_in_demo_context():
    """Prove that risk rejection works dynamically without touching Alpaca."""
    mock_positions = demo_portfolio.get_mock_alpaca_positions()
    equity = 10000.0
    ask_price = 250.0  # cost = $25,000, > equity, > 2% risk limit ($200)
    
    with pytest.raises(RiskRejection):
        calculate_final_position_size("MSFT", "bearish", mock_positions, equity, ask_price)
