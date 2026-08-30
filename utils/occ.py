import re
import datetime
from app_logging.logger import get_logger

log = get_logger(__name__)

# OCC option symbol format: AAPL230915C00150000
# 1-6 chars underlying, 6 chars date (YYMMDD), 1 char type (C/P), 8 chars strike (multiplied by 1000)
OCC_REGEX = re.compile(r"^([A-Z0-9]{1,6})(\d{6})([CP])(\d{8})$")

def parse_occ_symbol(symbol: str) -> dict:
    """
    Parses an OCC standard option symbol.
    Returns a dict with underlying, expiration, type, and strike.
    Raises ValueError if the symbol is malformed.
    """
    match = OCC_REGEX.match(symbol)
    if not match:
        raise ValueError(f"Malformed OCC option symbol: {symbol}")
        
    underlying = match.group(1)
    date_str = match.group(2)
    type_str = match.group(3)
    strike_str = match.group(4)
    
    # Parse expiration date
    try:
        expiration = datetime.datetime.strptime(date_str, "%y%m%d").date()
    except ValueError as e:
        raise ValueError(f"Invalid date in OCC symbol {symbol}: {e}")
        
    option_type = "call" if type_str == "C" else "put"
    strike = int(strike_str) / 1000.0
    
    return {
        "underlying": underlying,
        "expiration": expiration,
        "type": option_type,
        "strike": strike
    }
