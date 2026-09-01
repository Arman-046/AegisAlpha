import json
import os
import time
from typing import Dict, Any, List
from threading import Lock

OBSERVABILITY_FILE = "state/observability.json"

class ObservabilityState:
    def __init__(self):
        self._lock = Lock()
        self.state = {
            "last_heartbeat": 0,
            "status": "STOPPED",
            "current_symbol": None,
            "current_event": None,
            "pipeline": {
                "EVENT": "WAITING",
                "DATA": "WAITING",
                "BULL": "WAITING",
                "BEAR": "WAITING",
                "TRADER": "WAITING",
                "OPTION": "WAITING",
                "RANK": "WAITING",
                "RISK": "WAITING",
                "EXECUTE": "WAITING",
                "MONITOR": "WAITING"
            },
            "recent_activities": [],
            "error_history": [],
            "stats": {
                "events_detected": 0,
                "ai_evaluations": 0,
                "ai_failures": 0,
                "rank_rejections": 0,
                "risk_rejections": 0,
                "trades_approved": 0,
                "orders_submitted": 0
            },
            "last_terminal_state": {
                "status": "WAITING FOR EVENT",
                "reason": "No qualifying market event has triggered the strategy."
            },
            "ai_provider_status": "AVAILABLE"
        }
        self._load()

    def _load(self):
        if os.path.exists(OBSERVABILITY_FILE):
            try:
                with open(OBSERVABILITY_FILE, "r") as f:
                    loaded = json.load(f)
                    # Merge loaded state with defaults to handle schema changes
                    self._merge_dicts(self.state, loaded)
            except Exception:
                pass

    def _merge_dicts(self, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._merge_dicts(base[k], v)
            else:
                base[k] = v

    def _save(self):
        with self._lock:
            try:
                os.makedirs("state", exist_ok=True)
                with open(OBSERVABILITY_FILE, "w") as f:
                    json.dump(self.state, f, indent=2)
            except Exception:
                pass

    def heartbeat(self, status="RUNNING"):
        self.state["last_heartbeat"] = time.time()
        self.state["status"] = status
        self._save()

    def start_evaluation(self, symbol: str, event_msg: str):
        self.state["current_symbol"] = symbol
        self.state["current_event"] = event_msg
        
        # Reset pipeline
        for stage in self.state["pipeline"]:
            self.state["pipeline"][stage] = "WAITING"
            
        self.state["pipeline"]["EVENT"] = "COMPLETED"
        
        self.state["last_terminal_state"] = {
            "status": "PROCESSING",
            "reason": f"Evaluating opportunity for {symbol}"
        }
        self.increment_stat("events_detected")
        self.log_activity(f"Event detected \u2014 {symbol}: {event_msg}")
        self._save()

    def update_stage(self, stage: str, status: str):
        if stage in self.state["pipeline"]:
            self.state["pipeline"][stage] = status
            self._save()

    def set_terminal_state(self, status: str, reason: str):
        self.state["last_terminal_state"] = {
            "status": status,
            "reason": reason
        }
        self._save()

    def log_activity(self, msg: str):
        entry = {
            "timestamp": time.time(),
            "message": msg
        }
        self.state["recent_activities"].insert(0, entry)
        self.state["recent_activities"] = self.state["recent_activities"][:50]
        self._save()

    def log_error(self, category: str, msg: str):
        entry = {
            "timestamp": time.time(),
            "category": category,
            "message": msg
        }
        self.state["error_history"].insert(0, entry)
        self.state["error_history"] = self.state["error_history"][:20]
        
        if category == "AI":
            self.state["ai_provider_status"] = "UNAVAILABLE"
            
        self._save()
        
    def mark_ai_available(self):
        self.state["ai_provider_status"] = "AVAILABLE"
        self._save()

    def increment_stat(self, stat_name: str):
        if stat_name in self.state["stats"]:
            self.state["stats"][stat_name] += 1
            self._save()

obs = ObservabilityState()
