import pytest
import asyncio
from unittest.mock import patch, MagicMock
from config.settings import settings
from state.observability import obs

@pytest.mark.asyncio
@patch("strategy.screener.quantitative_prescreen")
@patch("reasoning.agent.evaluate_screener_candidates")
async def test_generate_watchlist_success(mock_eval, mock_quant):
    from strategy.screener import generate_watchlist
    
    mock_quant.return_value = [
        {"symbol": "AAPL", "price": 150.0, "volume": 1000, "momentum": 0.05},
        {"symbol": "MSFT", "price": 300.0, "volume": 800, "momentum": 0.04},
        {"symbol": "TSLA", "price": 200.0, "volume": 2000, "momentum": 0.03}
    ]
    
    mock_eval.return_value = [
        {"symbol": "TSLA", "score": 95, "reason": "High Volatility", "bull_case": "", "bear_case": "", "confidence": 0.9, "key_risk": "", "options_interest": ""},
        {"symbol": "AAPL", "score": 85, "reason": "Solid Setup", "bull_case": "", "bear_case": "", "confidence": 0.8, "key_risk": "", "options_interest": ""}
    ]
    
    old_watchlist = settings.WATCHLIST.copy()
    
    new_wl = await generate_watchlist()
    
    # Should sort by score and return symbols
    assert new_wl == ["TSLA", "AAPL"]
    
    # Observability should be updated
    assert obs.state["watchlist"]["status"] == "ACTIVE"
    assert obs.state["watchlist"]["size"] == 2
    assert obs.state["watchlist"]["candidates"] == 3

@pytest.mark.asyncio
@patch("strategy.screener.quantitative_prescreen")
async def test_generate_watchlist_quant_fail_fallback(mock_quant):
    from strategy.screener import generate_watchlist
    
    mock_quant.return_value = []
    
    old_watchlist = settings.WATCHLIST.copy()
    new_wl = await generate_watchlist()
    
    # Should fallback to existing watchlist
    assert new_wl == old_watchlist
    assert obs.state["watchlist"]["status"] == "FAILED"

@pytest.mark.asyncio
@patch("strategy.screener.quantitative_prescreen")
@patch("reasoning.agent.evaluate_screener_candidates")
async def test_generate_watchlist_gemini_fail_fallback(mock_eval, mock_quant):
    from strategy.screener import generate_watchlist
    
    mock_quant.return_value = [
        {"symbol": "AAPL", "price": 150.0, "volume": 1000, "momentum": 0.05}
    ]
    
    mock_eval.return_value = None # Simulate Gemini Failure
    
    old_watchlist = settings.WATCHLIST.copy()
    new_wl = await generate_watchlist()
    
    assert new_wl == old_watchlist
    assert obs.state["watchlist"]["status"] == "FAILED"
    assert obs.state["watchlist"]["error"] == "GROQ UNAVAILABLE"
