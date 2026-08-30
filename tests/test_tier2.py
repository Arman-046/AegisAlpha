import pytest
from state.memory import DecisionMemory
from strategy.ranking import rank_opportunities
from data.volatility import calculate_realized_volatility_percentile
import os

def test_memory_persistence():
    # Setup
    if os.path.exists("state/memory.json"):
        os.remove("state/memory.json")
        
    mem = DecisionMemory()
    mem.add_decision("AAPL", "bullish", 0.9, "EXECUTED", "Good earnings")
    
    # Reload
    mem2 = DecisionMemory()
    assert len(mem2.history) == 1
    assert mem2.history[0]["symbol"] == "AAPL"
    
def test_adaptive_confidence():
    mem = DecisionMemory()
    mem.history.clear()
    
    # Add a losing trade
    mem.add_decision("SPY", "bullish", 0.8, "EXECUTED", "Test")
    mem.update_last_trade_pl("SPY", -150.0)
    
    assert mem.current_confidence_threshold > 0.65 # Baseline is 0.65, so it should be raised
    
def test_ranking_opportunities():
    opps = [
        {"symbol": "AAPL", "confidence": 0.8, "spread": 0.5, "delta_dist": 0.1, "vol_regime": "Normal"},
        {"symbol": "TSLA", "confidence": 0.9, "spread": 2.0, "delta_dist": 0.4, "vol_regime": "High"}
    ]
    
    ranked = rank_opportunities(opps)
    
    assert len(ranked) == 2
    # AAPL has lower confidence but TSLA gets a huge penalty for spread, delta distance, and High vol regime
    assert ranked[0]["symbol"] == "AAPL"
    
def test_volatility_calc():
    class DummyBar:
        def __init__(self, c):
            self.close = c
            
    # Too little data
    bars = [DummyBar(100.0) for _ in range(10)]
    assert calculate_realized_volatility_percentile(bars) == "NORMAL"
    
    # Enough data, flat prices = zero vol, should just not crash
    bars = [DummyBar(100.0) for _ in range(60)]
    reg = calculate_realized_volatility_percentile(bars)
    assert reg == "EXPENSIVE / HIGH"
