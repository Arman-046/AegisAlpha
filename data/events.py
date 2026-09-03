import time
from typing import Dict, Any
from dataclasses import dataclass

@dataclass
class Event:
    timestamp: float
    symbol: str
    event_type: str
    magnitude: float
    source: str
    market_context: str
    is_simulated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "symbol": self.symbol,
            "event_type": self.event_type,
            "magnitude": self.magnitude,
            "source": self.source,
            "market_context": self.market_context
        }
        
    def __str__(self) -> str:
        return f"[{self.event_type}] {self.symbol} - {self.market_context}"
