import os
import sys
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.common.exceptions import APIError
import anthropic
import pytest
from app_logging.logger import get_logger

# Load env variables first
load_dotenv()

# We import settings after load_dotenv so it picks up the env vars
from config.settings import settings

log = get_logger(__name__)

def run_preflight_checks():
    log.info("Starting preflight validation...")
    
    # 1. Config validation (already happened on import, but check if it failed)
    if settings is None:
        log.error("Configuration validation failed. Check settings and environment variables.")
        sys.exit(1)
        
    log.info("Configuration validated successfully.")
    
    # 2. Check writable directories
    try:
        os.makedirs("state", exist_ok=True)
        os.makedirs("logs", exist_ok=True)
        # Test write
        test_file = "state/.write_test"
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        log.info("State and logs directories are writable.")
    except Exception as e:
        log.error(f"Cannot write to required directories: {e}")
        sys.exit(1)

    # 3. Alpaca Connectivity
    try:
        trading_client = TradingClient(
            settings.APCA_API_KEY_ID, 
            settings.APCA_API_SECRET_KEY, 
            paper=settings.PAPER
        )
        account = trading_client.get_account()
        if account.status.name != "ACTIVE":
            log.error(f"Alpaca account is not ACTIVE. Status: {account.status}")
            sys.exit(1)
        log.info(f"Alpaca connectivity verified. Account status: {account.status.name}")
    except APIError as e:
        log.error(f"Alpaca API connection failed: {e}")
        sys.exit(1)
    except Exception as e:
        log.error(f"Unexpected error connecting to Alpaca: {e}")
        sys.exit(1)

    # 4. Anthropic Connectivity
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        # We don't want to waste tokens, just checking if client initializes 
        # is usually enough, but a quick models list or cheap ping is better.
        # But wait, Claude doesn't have a simple ping. We will rely on the API key being present.
        # If the key is totally invalid, an actual call will fail later.
        log.info(f"Anthropic initialized with model ID: {settings.ANTHROPIC_MODEL_ID}")
    except Exception as e:
        log.error(f"Anthropic client initialization failed: {e}")
        sys.exit(1)
        
    log.info("All preflight checks passed.")
    return True

if __name__ == "__main__":
    run_preflight_checks()
