import pytest
from risk.hard_limits import calculate_final_position_size, check_circuit_breaker, validate_max_open_positions, RiskRejection
from config.settings import settings

class MockPosition:
    def __init__(self, symbol, cost_basis):
        self.symbol = symbol
        self.cost_basis = str(cost_basis)

@pytest.fixture(autouse=True)
def setup_limits():
    settings.SECTOR_MAP = {"AAPL": "Tech", "MSFT": "Tech", "TSLA": "Consumer"}
    settings.MAX_SECTOR_EXPOSURE_PERCENT = 0.06
    settings.MAX_DIRECTIONAL_EXPOSURE_PERCENT = 0.10
    settings.MAX_RISK_PERCENT = 0.02
    yield

def test_circuit_breaker():
    assert check_circuit_breaker(100_000, 95_000) is True
    assert check_circuit_breaker(100_000, 96_000) is False
    assert check_circuit_breaker(100_000, 105_000) is False

def test_max_open_positions():
    assert validate_max_open_positions(4) is True
    assert validate_max_open_positions(5) is False
    assert validate_max_open_positions(6) is False

def test_trade_allowed():
    # Equity 100k, limits: Trade 2k, Sector 6k, Dir 10k
    # No existing positions
    qty, risk = calculate_final_position_size("AAPL", "bullish", [], 100_000, 5.0)
    # Ask 5.0 -> $500 per contract. Max risk 2k -> 4 contracts = 2000
    assert qty == 4
    assert risk == 2000.0

def test_trade_resized_by_sector_limit():
    # Equity 100k
    # Existing Tech Bullish position: 5000
    positions = [MockPosition("MSFT230915C00150000", 5000.0)]
    
    # New trade AAPL (Tech). Max Tech = 6000. Left = 1000.
    # Single trade limit = 2000. Ask 5.0 -> $500/contract. 
    # Max contracts by trade limit = 4 (2000). But sector limit bounds it to 1000 -> 2 contracts.
    qty, risk = calculate_final_position_size("AAPL", "bullish", positions, 100_000, 5.0)
    assert qty == 2
    assert risk == 1000.0

def test_trade_rejected_by_sector_limit():
    # Equity 100k. Tech = 6000 max.
    # Existing Tech: 5800.
    positions = [MockPosition("MSFT230915C00150000", 5800.0)]
    
    # Left = 200. Ask = 5.0 ($500). Not enough for 1 contract.
    with pytest.raises(RiskRejection, match="Sector limit"):
        calculate_final_position_size("AAPL", "bullish", positions, 100_000, 5.0)

def test_trade_rejected_by_directional_limit():
    # Equity 100k. Max Bullish = 10000.
    # Existing Bullish: 9800 across different sectors.
    positions = [
        MockPosition("MSFT230915C00150000", 4900.0), # Tech Bullish
        MockPosition("TSLA230915C00150000", 4900.0)  # Consumer Bullish
    ]
    
    # New trade AAPL Bullish. Tech left = 6000 - 4900 = 1100.
    # Direction left = 10000 - 9800 = 200.
    # Ask = 5.0 ($500). Fails directional.
    with pytest.raises(RiskRejection, match="Directional limit"):
        calculate_final_position_size("AAPL", "bullish", positions, 100_000, 5.0)

def test_trade_rejected_by_both():
    # Equity 100k. Tech max = 6000. Bullish max = 10000.
    # Existing: Tech Bullish = 5800. Consumer Bullish = 4000.
    positions = [
        MockPosition("MSFT230915C00150000", 5800.0),
        MockPosition("TSLA230915C00150000", 4000.0)
    ]
    # Sector left = 200. Direction left = 200. Ask = 5.0 ($500). Both breached.
    with pytest.raises(RiskRejection) as exc:
        calculate_final_position_size("AAPL", "bullish", positions, 100_000, 5.0)
    assert "Sector limit" in str(exc.value)
    assert "Directional limit" in str(exc.value)

def test_trade_rejected_single_trade_limit():
    # Ask 25.0 -> $2500 per contract. Max trade risk = 2000.
    with pytest.raises(RiskRejection, match="Single trade limit"):
        calculate_final_position_size("AAPL", "bullish", [], 100_000, 25.0)
