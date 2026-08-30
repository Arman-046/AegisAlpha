from typing import Tuple
from config.settings import settings
from app_logging.logger import get_logger

log = get_logger(__name__)

class RiskRejection(Exception):
    """Raised when a trade fails hard risk checks."""
    pass

def check_circuit_breaker(start_of_day_equity: float, current_equity: float) -> bool:
    """
    Checks if the daily circuit breaker has been breached.
    """
    if start_of_day_equity <= 0:
        return False
        
    drawdown = (start_of_day_equity - current_equity) / start_of_day_equity
    if drawdown >= settings.DAILY_LOSS_LIMIT_PERCENT:
        log.warning(f"CIRCUIT BREAKER TRIGGERED: Drawdown of {drawdown*100:.2f}% exceeds {settings.DAILY_LOSS_LIMIT_PERCENT*100:.2f}% limit.")
        return True
        
    return False

def validate_max_open_positions(current_open_positions: int) -> bool:
    """
    Validates if a new trade can be opened.
    """
    if current_open_positions >= settings.MAX_OPEN_POSITIONS:
        log.warning(f"Max open positions reached ({settings.MAX_OPEN_POSITIONS}). Rejecting new trade.")
        return False
    return True

def calculate_final_position_size(
    symbol: str, 
    direction: str, 
    current_positions: list, 
    equity: float, 
    ask_price: float
) -> Tuple[int, float]:
    """
    Calculates the allowed quantity and total risk for a trade, applying all exposure limits.
    If the size is scaled down by sector or directional limits, it deterministically resizes.
    If the allowed size is less than 1 contract, raises RiskRejection.
    """
    if ask_price <= 0:
        raise RiskRejection("Ask price must be greater than zero.")
        
    cost_per_contract = ask_price * 100
    
    # 1. Single-Trade 2% Risk Check
    max_trade_risk = equity * settings.MAX_RISK_PERCENT
    
    # Calculate current exposures
    sector = settings.SECTOR_MAP.get(symbol, "Unknown")
    current_sector_exposure = 0.0
    current_directional_exposure = 0.0
    
    for pos in current_positions:
        opt_sym = pos.symbol
        try:
            from utils.occ import parse_occ_symbol
            parsed = parse_occ_symbol(opt_sym)
            underlying = parsed["underlying"]
            is_call = parsed["type"] == "call"
        except Exception:
            underlying = opt_sym
            is_call = True # Fallback if format is weird
            
        pos_sector = settings.SECTOR_MAP.get(underlying, "Unknown")
        if pos_sector == sector:
            current_sector_exposure += float(pos.cost_basis)
            
        pos_direction = "bullish" if is_call else "bearish"
        if pos_direction == direction:
            current_directional_exposure += float(pos.cost_basis)
            
    # 2. Sector Exposure Check
    max_sector_risk = (equity * settings.MAX_SECTOR_EXPOSURE_PERCENT) - current_sector_exposure
    
    # 3. Directional Exposure Check
    max_dir_risk = (equity * settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT) - current_directional_exposure
    
    # Deterministic final allowed risk
    allowed_risk = min(max_trade_risk, max_sector_risk, max_dir_risk)
    
    if allowed_risk < cost_per_contract:
        reasons = []
        if max_sector_risk < cost_per_contract: reasons.append(f"Sector limit ({sector})")
        if max_dir_risk < cost_per_contract: reasons.append(f"Directional limit ({direction})")
        if max_trade_risk < cost_per_contract: reasons.append("Single trade limit (2%)")
        raise RiskRejection(
            f"Trade rejected. Risk allowance (${allowed_risk:.2f}) is lower than cost per contract (${cost_per_contract:.2f}). Binders: {', '.join(reasons)}"
        )
        
    quantity = int(allowed_risk // cost_per_contract)
    total_risk = quantity * cost_per_contract
    
    if quantity < int(max_trade_risk // cost_per_contract):
        log.info(f"Trade RESIZED due to portfolio limits. Max trade quantity would be {int(max_trade_risk // cost_per_contract)}, but limited to {quantity}.")
    
    log.info(
        f"Risk Check Passed: Equity=${equity:.2f}, Ask=${ask_price:.2f}, "
        f"Allowed Risk=${allowed_risk:.2f}, Sizing: {quantity} contracts (${total_risk:.2f})"
    )
    
    return quantity, total_risk
