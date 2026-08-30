import pytest
import time
from unittest.mock import patch, MagicMock
import main
from main import handle_bar, handle_news, price_cache, last_eval_time

class MockBar:
    def __init__(self, symbol, close):
        self.symbol = symbol
        self.close = close

class MockNews:
    def __init__(self, symbols, headline):
        self.symbols = symbols
        self.headline = headline

@pytest.fixture(autouse=True)
def setup_teardown():
    price_cache.clear()
    last_eval_time.clear()
    main.main_loop = MagicMock()
    yield
    main.main_loop = None

@pytest.mark.asyncio
async def test_handle_bar_rate_limit():
    with patch("main.asyncio.run_coroutine_threadsafe") as mock_run:
        # First bar should trigger
        bar1 = MockBar("AAPL", 150.0)
        await handle_bar(bar1)
        assert mock_run.call_count == 1
        
        # Second bar immediately after should NOT trigger (throttled by time and <0.5% price change)
        bar2 = MockBar("AAPL", 150.0)
        await handle_bar(bar2)
        assert mock_run.call_count == 1
        
        # Third bar with 1% price change SHOULD trigger despite time throttle
        bar3 = MockBar("AAPL", 151.5)
        await handle_bar(bar3)
        assert mock_run.call_count == 2

@pytest.mark.asyncio
async def test_handle_news_rate_limit():
    with patch("main.asyncio.run_coroutine_threadsafe") as mock_run, \
         patch("main.settings.WATCHLIST", ["AAPL"]):
        news1 = MockNews(["AAPL"], "Apple releases new iPhone")
        await handle_news(news1)
        assert mock_run.call_count == 1
        
        # Immediate subsequent news for same symbol shouldn't trigger due to 15 min rate limit
        news2 = MockNews(["AAPL"], "More news about Apple")
        await handle_news(news2)
        assert mock_run.call_count == 1
        
@pytest.mark.asyncio
async def test_handle_news_not_in_watchlist():
    with patch("main.asyncio.run_coroutine_threadsafe") as mock_run, \
         patch("main.settings.WATCHLIST", ["TSLA"]):
        news1 = MockNews(["AAPL"], "Apple releases new iPhone")
        await handle_news(news1)
        assert mock_run.call_count == 0

@pytest.mark.asyncio
async def test_trigger_pipeline_hourly_limit():
    from main import trigger_pipeline, evals_this_hour, in_progress_evals
    evals_this_hour.clear()
    in_progress_evals.clear()
    
    with patch("main.process_symbol") as mock_process:
        mock_process.return_value = None  # don't execute order
        with patch("main.is_market_open", return_value=True):
            with patch("main.trading_client.get_all_positions", return_value=[]):
                # Run 1
                await trigger_pipeline("AAPL", "Event 1")
                assert mock_process.call_count == 1
                
                # Run 2
                await trigger_pipeline("AAPL", "Event 2")
                assert mock_process.call_count == 2
                
                # Run 3
                await trigger_pipeline("AAPL", "Event 3")
                assert mock_process.call_count == 3
                
                # Run 4 - should be suppressed
                await trigger_pipeline("AAPL", "Event 4")
                assert mock_process.call_count == 3  # Did not increment
