import pytest
import datetime
import time
from unittest.mock import MagicMock, patch

from strategy.validation import validate_tradeability
from strategy.ranking import rank_opportunities
from state.memory import memory, DecisionMemory
from data.events import Event

def test_dte_valid_expiration():
    # Valid expiration calculated correctly
    # Use a contract expiring 10 days from now
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).date()
    future = now + datetime.timedelta(days=10)
    # Build OCC symbol: e.g. AAPL260116C00100000 -> AAPL + YYMMDD + C + 00100000
    yymmdd = future.strftime("%y%m%d")
    occ_symbol = f"AAPL{yymmdd}C00100000"
    
    snapshot = MagicMock()
    snapshot.latest_quote.bid_price = 1.0
    snapshot.latest_quote.ask_price = 1.1
    snapshot.open_interest = 100
    
    is_valid, reason, metrics = validate_tradeability("AAPL", occ_symbol, snapshot)
    assert metrics["dte"] == 10

def test_dte_missing_expiration():
    # Invalid OCC symbol structure
    snapshot = MagicMock()
    snapshot.latest_quote.bid_price = 1.0
    snapshot.latest_quote.ask_price = 1.1
    snapshot.open_interest = 100
    
    is_valid, reason, metrics = validate_tradeability("AAPL", "NOT_AN_OCC_SYMBOL", snapshot)
    assert metrics["dte"] == "UNAVAILABLE"

def test_opportunity_score_deterministic():
    opp1 = {
        "symbol": "AAPL",
        "confidence": 0.8,
        "vol_regime": "LOW",
        "delta_dist": 0.0,
        "spread": 0.0
    }
    
    opp2 = {
        "symbol": "AAPL",
        "confidence": 0.8,
        "vol_regime": "LOW",
        "delta_dist": 0.0,
        "spread": 0.0
    }
    
    r1 = rank_opportunities([opp1])[0]
    r2 = rank_opportunities([opp2])[0]
    
    # 0.8 * 40 = 32
    # LOW = 20
    # delta 0.0 = 20
    # spread 0.0 = 20
    # Total = 92
    assert r1["rank_score"] == 92.0
    assert r2["rank_score"] == 92.0
    assert r1["rank_score"] == r2["rank_score"]

def test_opportunity_score_bounds():
    opp_perfect = {
        "symbol": "AAPL",
        "confidence": 1.5, # Exceeds max, but logic clamps? Let's check. 
                           # Wait, rank_opportunities just multiplies. The final score is clamped.
        "vol_regime": "LOW",
        "delta_dist": 0.0,
        "spread": 0.0
    }
    
    opp_terrible = {
        "symbol": "TSLA",
        "confidence": -0.5,
        "vol_regime": "HIGH",
        "delta_dist": 1.0, # 20 - 40 = -20 (clamped to 0)
        "spread": 5.0 # 20 - 100 = -80 (clamped to 0)
    }
    
    r_perf = rank_opportunities([opp_perfect])[0]
    r_terr = rank_opportunities([opp_terrible])[0]
    
    assert r_perf["rank_score"] <= 100.0
    assert r_perf["rank_score"] == 100.0
    assert r_terr["rank_score"] >= 0.0
    assert r_terr["rank_score"] == 0.0

@pytest.mark.asyncio
async def test_counterfactual_semantics():
    from main import process_symbol
    from reasoning.agent import TraderDecision
    
    # Reset memory
    memory.history.clear()
    
    event = Event(timestamp=time.time(), symbol="AAPL", event_type="TEST", magnitude=0, source="TEST", market_context="Test")
    
    with patch("main.evaluate_symbol_pipeline") as mock_pipeline:
        # 1. AI UNAVAILABLE -> not counterfactual
        async def mock_fail(*args, **kwargs):
            return None, None
        mock_pipeline.side_effect = mock_fail
        await process_symbol(event, 0)
        
        last_entry = memory.history[-1]
        assert last_entry["action"] == "FAILED"
        assert last_entry["is_counterfactual"] is False
        
        # 2. Rejected opportunity -> counterfactual
        trader_decision = TraderDecision(direction="neutral", opportunity_exists=False, confidence=0.4, synthesis="No signal", rationale="Not sure")
        async def mock_pass(*args, **kwargs):
            return trader_decision, None
        mock_pipeline.side_effect = mock_pass
        await process_symbol(event, 0)
        
        last_entry = memory.history[-1]
        assert last_entry["action"] == "PASSED"
        assert last_entry["is_counterfactual"] is True

def test_executed_trade_is_live():
    # memory.add_decision manual check
    memory.history.clear()
    memory.add_decision("AAPL", "bullish", 0.9, "EXECUTED", "Good", is_counterfactual=False)
    
    # Ensure it's not counterfactual
    last_entry = memory.history[-1]
    assert last_entry["is_counterfactual"] is False
    
    # Ensure it counts in P&L logic
    memory.update_last_trade_pl("AAPL", 50.0)
    assert memory.history[-1]["realized_pl"] == 50.0
    
    # Add a counterfactual, ensure update_last_trade_pl doesn't modify it
    memory.add_decision("AAPL", "bullish", 0.9, "PASSED", "Pass", is_counterfactual=True)
    memory.update_last_trade_pl("AAPL", -10.0)
    assert memory.history[-1]["realized_pl"] == 0.0  # PASSED remains 0.0
    assert memory.history[-2]["realized_pl"] == -10.0 # EXECUTED gets the update
