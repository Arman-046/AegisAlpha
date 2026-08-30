import numpy as np
from typing import List, Any
from app_logging.logger import get_logger

log = get_logger(__name__)

def calculate_realized_volatility_percentile(bars: List[Any], lookback_window: int = 20) -> str:
    """
    Calculates the 20-day realized volatility and ranks it as a percentile 
    against the full available window (e.g., 180 days).
    Returns a string describing the regime: "CHEAP / LOW VOL", "NORMAL", or "EXPENSIVE / HIGH VOL".
    """
    history_length = len(bars) if bars else 0
    if not bars or history_length < lookback_window * 2:
        log.warning(f"Insufficient data for volatility calc. History: {history_length}, Window: {lookback_window}")
        return "NORMAL"
        
    try:
        # Extract closing prices
        closes = [float(b.close) for b in bars]
        
        # Calculate daily log returns
        # Handle zero or negative closes just in case
        closes_safe = np.maximum(closes, 1e-8)
        returns = np.diff(np.log(closes_safe))
        
        # Calculate rolling standard deviations (volatility)
        rolling_vols = []
        for i in range(len(returns) - lookback_window + 1):
            window = returns[i:i + lookback_window]
            vol = np.std(window) * np.sqrt(252) # Annualized
            rolling_vols.append(vol)
            
        current_vol = rolling_vols[-1]
        
        # Calculate percentile of current vol relative to the lookback period
        percentile = sum(1 for v in rolling_vols if v <= current_vol) / len(rolling_vols)
        
        if percentile < 0.30:
            regime = "CHEAP / LOW"
        elif percentile > 0.70:
            regime = "EXPENSIVE / HIGH"
        else:
            regime = "NORMAL"
            
        log.info(
            f"Volatility Calculation: History={history_length} days, Window={lookback_window} days, "
            f"Current Vol={current_vol:.4f}, Percentile={percentile*100:.1f}%, Regime={regime}"
        )
        return regime
        
    except Exception as e:
        log.error(f"Error calculating volatility regime: {e}")
        return "NORMAL"
