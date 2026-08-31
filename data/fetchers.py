import datetime
from typing import Optional, List, Dict, Any
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from alpaca.data.requests import (
    StockBarsRequest, 
    OptionChainRequest,
    OptionSnapshotRequest,
    NewsRequest
)
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from alpaca.common.exceptions import APIError
from alpaca.trading.requests import GetOptionContractsRequest
from alpaca.trading.enums import ContractType

from data.clients import stock_data_client, option_data_client, news_client, trading_client
from app_logging.logger import get_logger

log = get_logger(__name__)

# Standard retry decorator for Alpaca data fetching
alpaca_retry = retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    retry=retry_if_exception_type(APIError),
    retry_error_callback=lambda retry_state: None
)

@alpaca_retry
def fetch_stock_bars(symbol: str, days: int = 180) -> Optional[Any]:
    """
    Fetches daily stock bars for the last 'days' days.
    Used for volatility calculations.
    """
    try:
        end = datetime.datetime.now(datetime.timezone.utc)
        start = end - datetime.timedelta(days=days)
        
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            feed=DataFeed.IEX # using IEX for free/paper typically, or SIP if funded
        )
        bars = stock_data_client.get_stock_bars(request)
        if not bars or symbol not in bars.data:
            log.warning(f"No bars returned for {symbol}")
            return None
        return bars.data[symbol]
    except APIError as e:
        log.warning(f"APIError fetching bars for {symbol}: {e}")
        raise e
    except Exception as e:
        log.error(f"Unexpected error fetching bars for {symbol}: {e}")
        return None

@alpaca_retry
def fetch_news(symbol: str, limit: int = 5) -> List[Any]:
    """
    Fetches the latest news articles for a symbol.
    """
    try:
        request = NewsRequest(
            symbols=symbol,
            limit=limit
        )
        news = news_client.get_news(request)
        if hasattr(news, 'news') and news.news:
            return news.news
        elif hasattr(news, 'data') and news.data:
            return news.data
        elif isinstance(news, list):
            return news
        return []
    except APIError as e:
        log.warning(f"APIError fetching news for {symbol}: {e}")
        raise e
    except Exception as e:
        log.error(f"Unexpected error fetching news for {symbol}: {e}")
        return []

@alpaca_retry
def fetch_option_contracts(symbol: str) -> List[Any]:
    """
    Fetches available option contracts for a symbol to find active expirations.
    """
    try:
        req = GetOptionContractsRequest(underlying_symbols=[symbol], status="active")
        res = trading_client.get_option_contracts(req)
        if not res or not res.option_contracts:
            log.warning(f"No option contracts found for {symbol}")
            return []
        return res.option_contracts
    except APIError as e:
        log.warning(f"APIError fetching option contracts for {symbol}: {e}")
        raise e
    except Exception as e:
        log.error(f"Unexpected error fetching option contracts for {symbol}: {e}")
        return []

@alpaca_retry
def fetch_option_chain(symbol: str) -> Dict[str, Any]:
    """
    Fetches the latest option chain snapshots for a symbol.
    Returns a dictionary mapping option_symbol to its snapshot data.
    """
    try:
        req = OptionChainRequest(underlying_symbol=symbol)
        res = option_data_client.get_option_chain(req)
        # res is typically a dict mapping option symbol to OptionSnapshot
        if not res:
            log.warning(f"Empty option chain returned for {symbol}")
            return {}
        return res
    except APIError as e:
        log.warning(f"APIError fetching option chain for {symbol}: {e}")
        raise e
    except Exception as e:
        log.error(f"Unexpected error fetching option chain for {symbol}: {e}")
        return {}

@alpaca_retry
def fetch_targeted_option_snapshots(symbols: List[str]) -> Dict[str, Any]:
    """
    Fetches option snapshots for a specific list of option symbols.
    This avoids fetching the entire chain.
    """
    if not symbols:
        return {}
        
    try:
        req = OptionSnapshotRequest(symbol_or_symbols=symbols)
        res = option_data_client.get_option_snapshots(req)
        if not res:
            log.warning("Empty option snapshots returned for targeted symbols.")
            return {}
        return res
    except APIError as e:
        log.warning(f"APIError fetching targeted snapshots: {e}")
        raise e
    except Exception as e:
        log.error(f"Unexpected error fetching targeted snapshots: {e}")
        return {}

def validate_option_snapshot(snapshot: Any) -> bool:
    """
    Validates if an option snapshot has the necessary data (quotes, etc.)
    to be traded safely.
    """
    if not snapshot:
        return False
    
    # Check for latest quote presence
    if not hasattr(snapshot, 'latest_quote') or snapshot.latest_quote is None:
        return False
        
    quote = snapshot.latest_quote
    # Check for valid bid/ask
    if not hasattr(quote, 'bid_price') or not hasattr(quote, 'ask_price'):
        return False
        
    if quote.bid_price is None or quote.ask_price is None:
        return False
        
    # Reject 0 bid (illiquid) unless we are explicitly holding it and it's a known artifact
    # For new entries, we strictly want liquidity
    if quote.bid_price <= 0.0:
        return False
        
    if quote.ask_price <= quote.bid_price:
        return False
        
    # Check implied volatility / greeks presence if required
    # Alpaca sometimes returns None for implied_volatility
    
    return True
