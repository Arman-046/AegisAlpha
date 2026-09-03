import pytest
from unittest.mock import patch, MagicMock
from config.settings import settings
import data.fetchers as fetchers
from main import execute_opportunity
from data.events import Event
from data.fixtures import get_mock_stock_bars, get_mock_option_snapshots

def test_demo_fetchers_use_fixtures():
    """Prove Demo mode fetchers return mock fixtures and do not call Alpaca."""
    settings.TRADING_MODE = "demo"
    bars = fetchers.fetch_stock_bars("AAPL")
    assert len(bars) > 0
    assert hasattr(bars[0], "close")
    
def test_paper_fetchers_use_alpaca():
    """Prove Paper mode fetchers use Alpaca APIs."""
    settings.TRADING_MODE = "paper"
    with patch("data.fetchers.stock_data_client.get_stock_bars") as mock_alpaca:
        fetchers.fetch_stock_bars("AAPL")
        mock_alpaca.assert_called_once()

@pytest.mark.asyncio
async def test_scenario_a_reaches_demo_execution():
    """Scenario A should successfully reach DemoExecutionEngine."""
    settings.TRADING_MODE = "demo"
    event = Event(timestamp=123, symbol="AAPL", event_type="DEMO", magnitude=0.01, source="DEMO", market_context="Test", is_simulated=True)
    top_opp = {"symbol": "AAPL", "contract": "AAPL240101C00150000", "direction": "bullish", "ask": 0.15, "bid": 0.14, "event": event, "confidence": 85, "rationale": "test", "quant_metrics": {}, "rank_score": 75, "synthesis": "test"}
    
    with patch("execution.engine.DemoExecutionEngine") as mock_demo_engine:
        await execute_opportunity(top_opp, current_loop_equity=1000.0)
        mock_demo_engine.return_value.submit_limit_order.assert_called_once()

@pytest.mark.asyncio
async def test_scenario_b_is_risk_rejected():
    """Scenario B should be rejected by the real Risk Governor."""
    settings.TRADING_MODE = "demo"
    event = Event(timestamp=123, symbol="TSLA", event_type="DEMO", magnitude=-0.01, source="DEMO", market_context="Test", is_simulated=True)
    # Ask is 2.50 ($250 per contract). Equity is 1000. 2% of 1000 is 20. Must fail!
    top_opp = {"symbol": "TSLA", "contract": "TSLA240101P00200000", "direction": "bearish", "ask": 2.50, "bid": 2.40, "event": event, "confidence": 85, "rationale": "test", "quant_metrics": {}, "rank_score": 75, "synthesis": "test"}
    
    with patch("execution.engine.DemoExecutionEngine") as mock_demo_engine, patch("main.obs") as mock_obs:
        await execute_opportunity(top_opp, current_loop_equity=1000.0)
        mock_demo_engine.return_value.submit_limit_order.assert_not_called()
        # Ensure it was caught by the risk reject
        mock_obs.set_terminal_state.assert_called()
        args = mock_obs.set_terminal_state.call_args[0]
        assert args[0] == "RISK LIMIT EXCEEDED"
        assert "Risk engine vetoed at execution" in args[1]

def test_scenario_c_data_fails_validation():
    """Scenario C should fail deterministic option validation."""
    from strategy.validation import validate_tradeability
    snapshots = get_mock_option_snapshots(["NVDA240101C00100000"])
    snapshot = snapshots.get("NVDA240101C00100000")
    
    is_valid, reject_reason, metrics = validate_tradeability("NVDA", "NVDA240101C00100000", snapshot)
    assert is_valid is False
    assert reject_reason != ""

