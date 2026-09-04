import json
import time
import os
import random

def get_base_obs():
    return {
        "last_heartbeat": time.time(),
        "status": "RUNNING",
        "current_symbol": "",
        "current_event": "",
        "pipeline": {
            "EVENT": "LISTENING", "DATA": "LISTENING", "BULL": "LISTENING", "BEAR": "LISTENING",
            "TRADER": "LISTENING", "OPTION": "LISTENING", "RANK": "LISTENING", "RISK": "LISTENING",
            "EXECUTE": "LISTENING", "MONITOR": "LISTENING"
        },
        "recent_activities": [],
        "error_history": [],
        "stats": {
            "events_detected": 0, "ai_evaluations": 0, "ai_failures": 0,
            "rank_rejections": 0, "risk_rejections": 0, "trades_approved": 0, "orders_submitted": 0
        },
        "last_terminal_state": {"status": "WAITING", "reason": "Listening for market events..."},
        "ai_provider_status": "AVAILABLE",
        "watchlist": {
            "status": "ACTIVE", "last_refresh": time.time(), "next_refresh": time.time() + 3600,
            "error": "", "scanned": 150, "candidates": 20, "ai_reviewed": 5, "size": 5,
            "picks": [
                {"symbol": "AAPL", "score": 92, "reason": "AR/VR Sales Beat Catalayst"},
                {"symbol": "TSLA", "score": 88, "reason": "Robotaxi Unveil Date"}
            ]
        }
    }

def reset_data():
    os.makedirs("state", exist_ok=True)
    with open("state/demo_memory.json", "w") as f: json.dump({"history": [], "current_confidence_threshold": 0.7}, f)
    with open("state/demo_observability.json", "w") as f: json.dump(get_base_obs(), f)
    with open("state/demo_portfolio.json", "w") as f: json.dump({"eq": 25000.0, "last_eq": 25000.0, "pnl": 0.0, "positions": []}, f)

def run_phase_1():
    obs = get_base_obs()
    obs["current_symbol"] = "AAPL"
    obs["current_event"] = "AAPL announces surprise AR/VR headset sales beat."
    obs["pipeline"]["EVENT"] = "COMPLETED"
    obs["pipeline"]["DATA"] = "COMPLETED"
    obs["pipeline"]["BULL"] = "PROCESSING"
    obs["pipeline"]["BEAR"] = "PROCESSING"
    obs["stats"]["events_detected"] = 1
    obs["recent_activities"] = [{"timestamp": time.time(), "message": "Event detected — AAPL: AR/VR Headset beat"}]
    with open("state/demo_observability.json", "w") as f: json.dump(obs, f)

def run_phase_2():
    obs = get_base_obs()
    obs["current_symbol"] = "AAPL"
    obs["current_event"] = "AAPL announces surprise AR/VR headset sales beat."
    for k in obs["pipeline"]: obs["pipeline"][k] = "COMPLETED"
    obs["pipeline"]["MONITOR"] = "PROCESSING"
    obs["stats"]["events_detected"] = 1
    obs["stats"]["ai_evaluations"] = 1
    obs["stats"]["trades_approved"] = 1
    obs["stats"]["orders_submitted"] = 1
    obs["recent_activities"] = [
        {"timestamp": time.time(), "message": "Order submitted: AAPL240101C00150000"},
        {"timestamp": time.time()-1, "message": "Risk engine approved AAPL trade"},
        {"timestamp": time.time()-2, "message": "AI Decision: BULLISH for AAPL (Conf: 0.95)"},
        {"timestamp": time.time()-4, "message": "Event detected — AAPL: AR/VR Headset beat"}
    ]
    obs["last_terminal_state"] = {"status": "TRADE APPROVED", "reason": "Risk limits passed. Trade executed successfully."}
    with open("state/demo_observability.json", "w") as f: json.dump(obs, f)
    
    mem = {
        "history": [
            {
                "timestamp": time.time(), "symbol": "AAPL", "event": "AAPL announces surprise AR/VR headset sales beat.",
                "direction": "bullish", "confidence": 0.95, "action": "EXECUTED", "reason": "Risk limits passed. Trade executed successfully.",
                "realized_pl": 0.0, "bull_arg": "The unexpected AR/VR headset sales beat serves as a massive catalyst.",
                "bear_arg": "Macro environment remains somewhat constrained, but the top-line beat is undeniably strong.",
                "trader_synthesis": "The bull case overwhelmingly dominates. Proceed with strong bullish conviction.",
                "quant_metrics": {"iv_rank": 35, "spread_bps": 5}, "rank_score": 92.5, "option_candidate": "AAPL240101C00150000",
                "is_counterfactual": False, "mode": "LIVE_PAPER"
            }
        ],
        "current_confidence_threshold": 0.7
    }
    with open("state/demo_memory.json", "w") as f: json.dump(mem, f)

def run_phase_3():
    aapl_pct = round(random.uniform(18.0, 26.5), 2)
    tsla_pct = round(random.uniform(2.0, 5.5), 2)
    total_profit = round(random.uniform(350.0, 650.0), 2)
    
    port = {
        "eq": 25000.0 + total_profit,
        "last_eq": 25000.0,
        "pnl": total_profit,
        "positions": [
            {"symbol": "AAPL", "qty": 500, "pl_pct": aapl_pct, "stop": 7.5},
            {"symbol": "TSLA", "qty": 100, "pl_pct": tsla_pct, "stop": -50.0}
        ]
    }
    with open("state/demo_portfolio.json", "w") as f: json.dump(port, f)
    
    mem = json.load(open("state/demo_memory.json"))
    mem["history"].insert(0, {
        "timestamp": time.time() - 3600, "symbol": "TSLA", "event": "Elon Musk announces new Robotaxi unveil date.",
        "direction": "bullish", "confidence": 0.88, "action": "EXECUTED", "reason": "Risk limits passed.",
        "realized_pl": 0.0, "bull_arg": "Robotaxi timeline accelerates revenue.",
        "bear_arg": "History of delays.",
        "trader_synthesis": "Short-term momentum is highly favorable.",
        "quant_metrics": {"iv_rank": 40, "spread_bps": 8}, "rank_score": 88.0, "option_candidate": "TSLA240517C00200000",
        "is_counterfactual": False, "mode": "LIVE_PAPER"
    })
    mem["history"].insert(0, {
        "timestamp": time.time() - 7200, "symbol": "NFLX", "event": "Subscriber growth misses by 2M in Q3.",
        "direction": "bearish", "confidence": 0.90, "action": "VETOED", "reason": "Macro Agent rejected.",
        "realized_pl": 0.0, "bull_arg": "N/A", "bear_arg": "Breaks growth narrative.",
        "trader_synthesis": "Strong bearish signal detected.",
        "quant_metrics": {"iv_rank": 80, "spread_bps": 12}, "rank_score": 65.0, "option_candidate": "NFLX240101P00400000",
        "is_counterfactual": True, "mode": "LIVE_PAPER"
    })
    with open("state/demo_memory.json", "w") as f: json.dump(mem, f)

def run_golden_path():
    reset_data()
    time.sleep(2)
    run_phase_1()
    time.sleep(3)
    run_phase_2()
    time.sleep(3)
    run_phase_3()

if __name__ == "__main__":
    run_golden_path()
