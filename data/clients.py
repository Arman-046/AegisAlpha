from alpaca.trading.client import TradingClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from config.settings import settings

# Initialize singletons for Alpaca clients

def get_trading_client() -> TradingClient:
    return TradingClient(
        api_key=settings.APCA_API_KEY_ID,
        secret_key=settings.APCA_API_SECRET_KEY,
        paper=settings.PAPER
    )

def get_stock_data_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        api_key=settings.APCA_API_KEY_ID,
        secret_key=settings.APCA_API_SECRET_KEY
    )

def get_option_data_client() -> OptionHistoricalDataClient:
    return OptionHistoricalDataClient(
        api_key=settings.APCA_API_KEY_ID,
        secret_key=settings.APCA_API_SECRET_KEY
    )

def get_news_client() -> NewsClient:
    return NewsClient(
        api_key=settings.APCA_API_KEY_ID,
        secret_key=settings.APCA_API_SECRET_KEY
    )

trading_client = get_trading_client()
stock_data_client = get_stock_data_client()
option_data_client = get_option_data_client()
news_client = get_news_client()
