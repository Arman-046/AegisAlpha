from alpaca.trading.client import TradingClient
from alpaca.common.exceptions import APIError
from app_logging.logger import get_logger
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

log = get_logger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(APIError),
    reraise=True
)
def is_market_open(trading_client: TradingClient) -> bool:
    """
    Checks if the US market is currently open.
    Retries up to 3 times on API errors.
    """
    try:
        clock = trading_client.get_clock()
        return clock.is_open
    except APIError as e:
        log.warning(f"APIError checking market clock: {e}")
        raise e
    except Exception as e:
        log.error(f"Unexpected error checking market clock: {e}")
        return False
