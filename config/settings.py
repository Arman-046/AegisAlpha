import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List

class Settings(BaseSettings):
    # API Keys
    APCA_API_KEY_ID: str = Field(..., description="Alpaca Paper API Key")
    APCA_API_SECRET_KEY: str = Field(..., description="Alpaca Paper API Secret")
    # AI API keys
    GROQ_API_KEY: str = Field(default="PK_DUMMY", env="GROQ_API_KEY")
    GROQ_MODEL: str = Field(default="openai/gpt-oss-20b", env="GROQ_MODEL")
    
    # Execution Mode
    TRADING_MODE: str = Field(default="paper", description="Execution mode: 'paper' or 'demo'")
    
    # Paper Trading Safety
    PAPER: bool = Field(default=True, description="Must be true for paper trading")
    
    # Dynamic Screener Parameters
    UNIVERSE: List[str] = Field(default=[
        "SPY", "QQQ", "AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "META", "GOOGL", "NFLX",
        "AMD", "INTC", "QCOM", "AVGO", "CSCO", "ORCL", "CRM", "ADBE",
        "JPM", "BAC", "V", "MA", "GS", "MS", 
        "XOM", "CVX", 
        "JNJ", "UNH", "LLY", "PFE"
    ], description="S&P 100 style liquid universe for the AI screener")
    MAX_SCREEN_CANDIDATES: int = Field(default=10, description="Max candidates to send to Gemini")
    WATCHLIST_SIZE: int = Field(default=5, description="Number of symbols in the dynamic watchlist")
    WATCHLIST_REFRESH_INTERVAL: int = Field(default=3600, description="Seconds between watchlist refreshes (1 hour)")
    
    # Trading Parameters
    WATCHLIST: List[str] = Field(default=["SPY", "AAPL", "MSFT", "NVDA", "TSLA"], description="Active watchlist (can be dynamically updated)")
    SECTOR_MAP: dict = Field(default={
        "SPY": "Market", "QQQ": "Market",
        "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AMZN": "Consumer", 
        "META": "Tech", "GOOGL": "Tech", "NFLX": "Consumer", "AMD": "Tech",
        "INTC": "Tech", "QCOM": "Tech", "AVGO": "Tech", "CSCO": "Tech", 
        "ORCL": "Tech", "CRM": "Tech", "ADBE": "Tech",
        "TSLA": "Consumer",
        "JPM": "Financials", "BAC": "Financials", "V": "Financials", "MA": "Financials", 
        "GS": "Financials", "MS": "Financials",
        "XOM": "Energy", "CVX": "Energy",
        "JNJ": "Healthcare", "UNH": "Healthcare", "LLY": "Healthcare", "PFE": "Healthcare"
    }, description="Map of symbols to sectors for correlation limits")
    MAX_SECTOR_EXPOSURE_PERCENT: float = Field(default=0.06, description="Max 6% risk per sector")
    MAX_DIRECTIONAL_EXPOSURE_PERCENT: float = Field(default=0.10, description="Max 10% risk per direction (Bullish/Bearish)")
    MAX_RISK_PERCENT: float = Field(default=0.02, description="Max 2% risk per trade of account equity")
    MAX_OPEN_POSITIONS: int = Field(default=5, description="Max concurrent option positions")
    BASE_MIN_CONFIDENCE: float = Field(default=0.65, description="Base minimum LLM confidence to trade")
    MIN_RANK_SCORE_THRESHOLD: float = Field(default=60.0, description="Minimum rank score to execute a trade")
    DAILY_LOSS_LIMIT_PERCENT: float = Field(default=0.05, description="Circuit breaker: 5% daily loss limit")
    
    # Option Parameters
    MIN_DTE: int = Field(default=14, description="Minimum days to expiration")
    MAX_DTE: int = Field(default=35, description="Maximum days to expiration")
    MAX_SLIPPAGE_PERCENT: float = Field(default=0.02, description="Max 2% slippage on limit orders")
    MAX_TARGETED_OPTION_SNAPSHOTS: int = Field(default=20, description="Max candidate contracts for snapshot fetching")
    
    @field_validator("PAPER")
    def validate_paper(cls, v):
        if not v:
            raise ValueError("PAPER must be True. Live trading is not permitted.")
        return v
        
    @field_validator("TRADING_MODE")
    def validate_trading_mode(cls, v):
        if v not in ["paper", "demo"]:
            raise ValueError("TRADING_MODE must be 'paper' or 'demo'")
        return v
        
    @field_validator("APCA_API_KEY_ID")
    def validate_api_key(cls, v, info):
        # Allow PK_DUMMY only if TRADING_MODE is demo
        mode = info.data.get('TRADING_MODE', 'paper')
        if v == "PK_DUMMY" and mode != "demo":
            raise ValueError("PK_DUMMY is only allowed in TRADING_MODE=demo")
        return v
        
    @field_validator("MAX_RISK_PERCENT")
    def validate_max_risk(cls, v):
        if v <= 0 or v > 0.05: # Hard cap at 5% just in case
            raise ValueError("MAX_RISK_PERCENT must be > 0 and <= 0.05")
        if v > 0.02:
            print("WARNING: Risk > 2% is generally not recommended, but capping at 5%")
        return v
        
    @field_validator("BASE_MIN_CONFIDENCE")
    def validate_confidence(cls, v):
        if v < 0 or v > 1:
            raise ValueError("BASE_MIN_CONFIDENCE must be between 0 and 1")
        return v
        
    @field_validator("MAX_OPEN_POSITIONS")
    def validate_positions(cls, v):
        if v < 0:
            raise ValueError("MAX_OPEN_POSITIONS cannot be negative")
        return v
        
    @field_validator("MAX_SLIPPAGE_PERCENT")
    def validate_slippage(cls, v):
        if v < 0:
            raise ValueError("MAX_SLIPPAGE_PERCENT cannot be negative")
        return v
        
    @field_validator("MAX_DTE")
    def validate_dte(cls, v, info):
        if 'MIN_DTE' in info.data and v < info.data['MIN_DTE']:
            raise ValueError("MAX_DTE cannot be less than MIN_DTE")
        return v

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# Singleton instance
try:
    settings = Settings()
except Exception as e:
    # We will let preflight catch this, or it can crash early on import
    # But usually we want to handle it gracefully in preflight
    print(f"Failed to load settings: {e}")
    settings = None
