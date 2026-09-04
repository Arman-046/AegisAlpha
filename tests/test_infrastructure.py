import pytest
import asyncio
from unittest.mock import patch, MagicMock
import time
from config.settings import settings

@pytest.fixture
def memory_mock():
    with patch("main.memory") as mem:
        yield mem

@pytest.fixture
def alpaca_mock():
    with patch("main.trading_client") as client:
        yield client

@pytest.fixture
def mock_fetchers():
    with patch("main.fetch_stock_bars", return_value=[MagicMock(close=100)]), \
         patch("main.fetch_news", return_value=[MagicMock(headline="News")]), \
         patch("main.calculate_realized_volatility_percentile", return_value="Normal"):
        yield

@pytest.mark.asyncio
async def test_gemini_failure_returns_failed(memory_mock, mock_fetchers):
    from main import process_symbol
    
    # Mock evaluate_symbol_pipeline to return (None, None) simulating API failure
    with patch("main.evaluate_symbol_pipeline", new_callable=MagicMock) as mock_pipeline:
        async def mock_coro(*args, **kwargs):
            return None, None
        mock_pipeline.side_effect = mock_coro
        
        from data.events import Event
        event = Event(timestamp=time.time(), symbol="AAPL", event_type="TEST", magnitude=0, source="TEST", market_context="Test")
        result = await process_symbol(event, open_positions=0)
        
        assert result is None
        memory_mock.add_decision.assert_called_once_with(
            "AAPL", "neutral", 0.0, "FAILED", "AI UNAVAILABLE: Groq API failure",
            event=event, is_counterfactual=False, mode="LIVE_PAPER"
        )

@pytest.mark.asyncio
async def test_genuine_neutral_decision(memory_mock, mock_fetchers):
    from main import process_symbol
    from reasoning.agent import TraderDecision
    
    with patch("main.evaluate_symbol_pipeline", new_callable=MagicMock) as mock_pipeline:
        async def mock_coro(*args, **kwargs):
            trader_decision = TraderDecision(direction="neutral", opportunity_exists=False, confidence=0.4, synthesis="No signal", rationale="Not sure")
            return trader_decision, None
        mock_pipeline.side_effect = mock_coro
        
        from data.events import Event
        event = Event(timestamp=time.time(), symbol="AAPL", event_type="TEST", magnitude=0, source="TEST", market_context="Test")
        result = await process_symbol(event, open_positions=0)
        
        assert result is None
        memory_mock.add_decision.assert_called_once_with(
            "AAPL", "neutral", 0.4, "PASSED", "No strong signal",
            event=event, trader_synthesis="No signal", is_counterfactual=True, mode="LIVE_PAPER"
        )

def test_event_detector_polling():
    from main import handle_bar, price_cache, last_eval_time
    price_cache.clear()
    last_eval_time.clear()
    
    class DummyBar:
        symbol = "AAPL"
        close = 150.0
        
    class DummyBarSmallMove:
        symbol = "AAPL"
        close = 150.1 # < 0.5%
        
    class DummyBarBigMove:
        symbol = "AAPL"
        close = 155.0 # > 0.5%
    
    # Needs a running event loop to test the task creation
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    import main
    main.main_loop = loop
    
    with patch("main.asyncio.run_coroutine_threadsafe") as mock_run, \
         patch("main.trigger_pipeline", return_value="mock_coro"):
        # 1. First bar adds to cache but no trigger
        loop.run_until_complete(handle_bar(DummyBar()))
        assert "AAPL" in price_cache
        assert price_cache["AAPL"] == 150.0
        mock_run.assert_not_called()
        
        # 2. Second bar with small move, no trigger
        loop.run_until_complete(handle_bar(DummyBarSmallMove()))
        assert price_cache["AAPL"] == 150.0 # Anchor price does not update on small move
        mock_run.assert_not_called()
        
        # 3. Third bar with big move, should trigger
        loop.run_until_complete(handle_bar(DummyBarBigMove()))
        assert price_cache["AAPL"] == 155.0 # Updates on trigger
        assert mock_run.call_count == 1
        
    loop.close()
        
def test_event_detector_no_polling():
    from main import handle_bar, price_cache, last_eval_time
    price_cache.clear()
    last_eval_time.clear()
    
    import main
    loop = asyncio.new_event_loop()
    main.main_loop = loop
    
    class DummyBar:
        symbol = "AAPL"
        close = 100.0
    class DummyBarSmallMove:
        symbol = "AAPL"
        close = 100.1
        
    with patch("main.asyncio.run_coroutine_threadsafe") as mock_run, \
         patch("main.trigger_pipeline", return_value="mock_coro"):
        # First tick
        loop.run_until_complete(handle_bar(DummyBar()))
        mock_run.assert_not_called()
        
        # Set last_eval_time back in time to simulate 15+ minutes passing
        last_eval_time["AAPL"] = time.time() - 1000
        
        # Small move after 15 minutes
        loop.run_until_complete(handle_bar(DummyBarSmallMove()))
        
        # Ensure it didn't trigger
        mock_run.assert_not_called()
        assert price_cache["AAPL"] == 100.0 # Anchor price remains unchanged
        
    loop.close()
