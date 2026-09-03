import json
import time

def inject_mock_data():
    now = time.time()
    
    # Update memory.json
    try:
        with open("state/memory.json", "r") as f:
            memory = json.load(f)
    except Exception:
        memory = {"history": [], "current_confidence_threshold": 0.7}
        
    if len(memory.get("history", [])) > 0:
        print("Data already exists. Skipping injection.")
        return
        
    mock_history = [
        {
            "timestamp": now - 3600 * 2,
            "symbol": "AAPL",
            "event": "Volatility Spike Detected",
            "direction": "bullish",
            "confidence": 0.88,
            "action": "EXECUTED",
            "reason": "Executed order for AAPL240517C00180000",
            "realized_pl": 0.0,
            "bull_thesis": "Strong momentum",
            "bear_thesis": "Overbought",
            "trader_synthesis": "Bullish thesis outweighs bear risks. Volatility is high but manageable. Proceeding with calls.",
            "quant_metrics": {"volatility_percentile": 0.85},
            "rank_score": 92.5,
            "option_candidate": "AAPL240517C00180000",
            "is_counterfactual": False,
            "mode": "LIVE_PAPER"
        },
        {
            "timestamp": now - 3600 * 5,
            "symbol": "NVDA",
            "event": "News: Earnings Beat",
            "direction": "bullish",
            "confidence": 0.95,
            "action": "EXECUTED",
            "reason": "Executed order for NVDA240517C00900000",
            "realized_pl": 0.0,
            "bull_thesis": "Incredible earnings",
            "bear_thesis": "Priced in",
            "trader_synthesis": "Momentum is undeniable. Executing.",
            "quant_metrics": {"volatility_percentile": 0.99},
            "rank_score": 98.0,
            "option_candidate": "NVDA240517C00900000",
            "is_counterfactual": False,
            "mode": "LIVE_PAPER"
        },
        {
            "timestamp": now - 3600 * 1.5,
            "symbol": "TSLA",
            "event": "News: Delivery Miss",
            "direction": "bearish",
            "confidence": 0.82,
            "action": "RISK_REJECTED",
            "reason": "Max risk exceeded. Cost per contract ($250) exceeds 2% risk allowance ($20).",
            "realized_pl": 0.0,
            "bull_thesis": "Oversold bounce",
            "bear_thesis": "Fundamentals deteriorating",
            "trader_synthesis": "Strong bear case, but options are too expensive for current portfolio equity.",
            "quant_metrics": {"volatility_percentile": 0.90},
            "rank_score": 85.0,
            "option_candidate": "TSLA240101P00200000",
            "is_counterfactual": True,
            "mode": "LIVE_PAPER"
        }
    ]
    
    memory["history"].extend(mock_history)
    with open("state/memory.json", "w") as f:
        json.dump(memory, f, indent=2)

    # Update observability.json
    try:
        with open("state/observability.json", "r") as f:
            obs = json.load(f)
    except Exception:
        obs = {}
        
    if "stats" not in obs:
        obs["stats"] = {}
        
    obs["stats"]["events_detected"] = obs["stats"].get("events_detected", 0) + 12
    obs["stats"]["ai_evaluations"] = obs["stats"].get("ai_evaluations", 0) + 8
    obs["stats"]["trades_approved"] = obs["stats"].get("trades_approved", 0) + 2
    obs["stats"]["risk_rejections"] = obs["stats"].get("risk_rejections", 0) + 1
    obs["stats"]["orders_submitted"] = obs["stats"].get("orders_submitted", 0) + 2
    
    if "activity_log" not in obs:
        obs["activity_log"] = []
        
    obs["activity_log"].extend([
        {"timestamp": now - 3600 * 2, "message": "Order submitted: AAPL240517C00180000"},
        {"timestamp": now - 3600 * 5, "message": "Order submitted: NVDA240517C00900000"},
        {"timestamp": now - 3600 * 1.5, "message": "Risk engine vetoed TSLA"}
    ])
    
    with open("state/observability.json", "w") as f:
        json.dump(obs, f, indent=2)
        
    print("Mock data injected.")

if __name__ == "__main__":
    inject_mock_data()
