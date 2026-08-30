import json
import os
from collections import deque
from typing import List, Dict, Any
from app_logging.logger import get_logger
from config.settings import settings

log = get_logger(__name__)

MEMORY_FILE = "state/memory.json"
MAX_MEMORY_LEN = 20

class DecisionMemory:
    def __init__(self):
        self.history: deque = deque(maxlen=MAX_MEMORY_LEN)
        self.current_confidence_threshold = settings.BASE_MIN_CONFIDENCE
        self._load_state()

    def _load_state(self):
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r") as f:
                    data = json.load(f)
                    self.history = deque(data.get("history", []), maxlen=MAX_MEMORY_LEN)
                    self.current_confidence_threshold = data.get("current_confidence_threshold", settings.BASE_MIN_CONFIDENCE)
                log.info(f"Loaded decision memory. History size: {len(self.history)}")
            except Exception as e:
                log.error(f"Failed to load memory state: {e}")
                self.history = deque(maxlen=MAX_MEMORY_LEN)
                self.current_confidence_threshold = settings.BASE_MIN_CONFIDENCE

    def _save_state(self):
        try:
            with open(MEMORY_FILE, "w") as f:
                json.dump({
                    "history": list(self.history),
                    "current_confidence_threshold": self.current_confidence_threshold
                }, f, indent=2)
        except Exception as e:
            log.error(f"Failed to save memory state: {e}")

    def add_decision(self, symbol: str, direction: str, confidence: float, action: str, reason: str, realized_pl: float = 0.0):
        entry = {
            "symbol": symbol,
            "direction": direction,
            "confidence": confidence,
            "action": action,
            "reason": reason,
            "realized_pl": realized_pl
        }
        self.history.append(entry)
        self._save_state()

    def update_last_trade_pl(self, symbol: str, realized_pl: float):
        """Updates the P&L of the most recent trade for this symbol."""
        for entry in reversed(self.history):
            if entry["symbol"] == symbol and entry["action"] == "EXECUTED":
                entry["realized_pl"] = realized_pl
                break
        self._save_state()
        self._adapt_confidence_threshold()

    def _adapt_confidence_threshold(self):
        """
        Adapts the confidence threshold based on recent closed-trade results.
        Net negative -> Raise confidence threshold.
        Improving results -> Move threshold back toward baseline.
        """
        # Look at the last 5 executed trades
        recent_trades = [e for e in self.history if e["action"] == "EXECUTED"][-5:]
        if not recent_trades:
            return

        net_pl = sum(e.get("realized_pl", 0.0) for e in recent_trades)
        
        old_threshold = self.current_confidence_threshold
        
        if net_pl < 0:
            # Net negative -> Raise confidence by 0.05
            self.current_confidence_threshold = min(0.95, self.current_confidence_threshold + 0.05)
        elif net_pl > 0:
            # Improving -> Lower confidence toward baseline by 0.05
            self.current_confidence_threshold = max(settings.BASE_MIN_CONFIDENCE, self.current_confidence_threshold - 0.05)
            
        if old_threshold != self.current_confidence_threshold:
            log.info(f"Adaptive Confidence Adjusted: {old_threshold:.2f} -> {self.current_confidence_threshold:.2f} (Net P&L: {net_pl:.2f})")
            
        self._save_state()

    def get_recent_context(self, limit: int = 5) -> str:
        recent = list(self.history)[-limit:]
        if not recent:
            return "No recent trading history."
            
        context_lines = []
        for r in recent:
            context_lines.append(f"- {r['symbol']}: {r['direction']} (Conf: {r['confidence']}), Action: {r['action']}, P&L: {r.get('realized_pl', 0.0):.2f}")
        return "\n".join(context_lines)

# Singleton
memory = DecisionMemory()
