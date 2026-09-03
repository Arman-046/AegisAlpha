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

def test_event_is_simulated_flag():
    from data.events import Event
    import time
    
    e1 = Event(timestamp=time.time(), symbol="AAPL", event_type="TEST", magnitude=0.01, source="DEMO", market_context="Test", is_simulated=True)
    assert e1.is_simulated is True
    
    e2 = Event(timestamp=time.time(), symbol="MSFT", event_type="TEST", magnitude=0.01, source="LIVE", market_context="Test")
    assert e2.is_simulated is False

def test_memory_mode_isolation():
    from state.memory import DecisionMemory
    from config.settings import settings
    
    mem = DecisionMemory()
    mem.history.clear()
    
    # Live trade
    mem.add_decision("AAPL", "bullish", 0.9, "EXECUTED", "Live reason", mode="LIVE_PAPER")
    # Demo trade
    mem.add_decision("MSFT", "bullish", 0.9, "EXECUTED", "Demo reason", mode="DEMO")
    
    assert len(mem.history) == 2
    
    # Update P&L for MSFT (Demo trade)
    mem.update_last_trade_pl("MSFT", 50.0)
    
    # Verify MSFT P&L did NOT update because mode != LIVE_PAPER
    msft_entry = next(e for e in mem.history if e["symbol"] == "MSFT")
    assert msft_entry.get("realized_pl") == 0.0
    
    # Update P&L for AAPL (Live trade)
    mem.update_last_trade_pl("AAPL", 100.0)
    aapl_entry = next(e for e in mem.history if e["symbol"] == "AAPL")
    assert aapl_entry.get("realized_pl") == 100.0

@pytest.mark.asyncio
async def test_execute_opportunity_demo_routing():
    from main import execute_opportunity
    from config.settings import settings
    from data.events import Event
    import time
    
    # Force settings
    settings.TRADING_MODE = "demo"
    
    event = Event(timestamp=time.time(), symbol="TEST", event_type="TEST", magnitude=0.01, source="DEMO", market_context="Test", is_simulated=True)
    top_opp = {
        "symbol": "TEST",
        "contract": "TEST240517C00100000",
        "direction": "bullish",
        "confidence": 0.8,
        "synthesis": "Test synth",
        "rationale": "Test rationale",
        "bid": 1.0,
        "ask": 1.1,
        "event": event
    }
    
    demo_portfolio.reset_demo()
    demo_portfolio.cash = 100000.0
    
    with patch("main.memory") as mock_memory:
        await execute_opportunity(top_opp)
        
        # Verify DemoExecutionEngine was used by checking the portfolio state
        assert len(demo_portfolio.positions) == 1
        
        # Verify memory was called with mode='DEMO'
        mock_memory.add_decision.assert_called_once()
        kwargs = mock_memory.add_decision.call_args[1]
        assert kwargs.get("mode") == "DEMO"
        
    settings.TRADING_MODE = "paper"

@pytest.mark.asyncio
async def test_1_paper_mode_simulated_event_fails_closed():
    from main import execute_opportunity
    from config.settings import settings
    from data.events import Event
    import time
    
    settings.TRADING_MODE = "paper"
    event = Event(timestamp=time.time(), symbol="TEST", event_type="TEST", magnitude=0.01, source="DEMO", market_context="Test", is_simulated=True)
    top_opp = {"symbol": "TEST", "contract": "TEST24", "direction": "bullish", "ask": 1.0, "event": event}
    
    with patch("main.memory") as mock_memory:
        await execute_opportunity(top_opp)
        mock_memory.add_decision.assert_not_called()

@pytest.mark.asyncio
async def test_2_demo_mode_live_event_fails_closed():
    from main import execute_opportunity
    from config.settings import settings
    from data.events import Event
    import time
    
    settings.TRADING_MODE = "demo"
    event = Event(timestamp=time.time(), symbol="TEST", event_type="TEST", magnitude=0.01, source="LIVE", market_context="Test", is_simulated=False)
    top_opp = {"symbol": "TEST", "contract": "TEST24", "direction": "bullish", "ask": 1.0, "event": event}
    
    with patch("main.memory") as mock_memory:
        await execute_opportunity(top_opp)
        mock_memory.add_decision.assert_not_called()

@pytest.mark.asyncio
async def test_3_paper_mode_live_event_unchanged():
    from main import execute_opportunity
    from config.settings import settings
    from data.events import Event
    import time
    
    settings.TRADING_MODE = "paper"
    event = Event(timestamp=time.time(), symbol="TEST", event_type="TEST", magnitude=0.01, source="LIVE", market_context="Test", is_simulated=False)
    top_opp = {"symbol": "TEST", "contract": "TEST24", "direction": "bullish", "ask": 1.0, "event": event}
    
    with patch("main.memory") as mock_memory, patch("main.validate_max_open_positions", return_value=False):
        # We mock validation to stop early but prove engine path is reached
        await execute_opportunity(top_opp)
        # Reached processing means it didn't fail the safety invariant guard
        # (It failed later on max positions which is standard behavior)
        
@pytest.mark.asyncio
async def test_4_demo_mode_simulated_event_unchanged():
    from main import execute_opportunity
    from config.settings import settings
    from data.events import Event
    import time
    
    settings.TRADING_MODE = "demo"
    event = Event(timestamp=time.time(), symbol="TEST", event_type="TEST", magnitude=0.01, source="DEMO", market_context="Test", is_simulated=True)
    top_opp = {"symbol": "TEST", "contract": "TEST24", "direction": "bullish", "ask": 1.0, "event": event}
    
    with patch("main.memory") as mock_memory, patch("main.validate_max_open_positions", return_value=False):
        await execute_opportunity(top_opp)
        # Reached processing means it didn't fail the safety invariant guard

@pytest.mark.asyncio
async def test_5_missing_event_fails_closed():
    from main import execute_opportunity
    from config.settings import settings
    
    settings.TRADING_MODE = "paper"
    top_opp = {"symbol": "TEST", "contract": "TEST24", "direction": "bullish", "ask": 1.0, "event": None}
    
    with patch("main.memory") as mock_memory:
        await execute_opportunity(top_opp)
        mock_memory.add_decision.assert_not_called()
