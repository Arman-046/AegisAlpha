import pytest
import asyncio
from unittest.mock import patch, MagicMock
from main import process_symbol
from state.memory import memory
from mcp_tools.alpaca_mcp import mcp_client

@pytest.fixture(autouse=True)
def mock_mcp():
    mcp_client._initialized = True
    mcp_client.session = MagicMock()
    mcp_client.session.call_tool = MagicMock()

@pytest.fixture(autouse=True)
def clean_memory():
    memory.history.clear()
    yield
    memory.history.clear()

@pytest.mark.asyncio
@patch("main.fetch_stock_bars")
@patch("main.fetch_news")
@patch("main.evaluate_symbol_pipeline")
@patch("main.fetch_option_contracts")
@patch("main.select_contract_with_snapshot")
@patch("main.validate_option_snapshot")
async def test_valid_opportunity_path(
    mock_validate, mock_select_contract, mock_fetch_contracts, 
    mock_eval, mock_news, mock_bars
):
    # Mock data to simulate a valid opportunity passing through the pipeline
    mock_bars.return_value = [MagicMock(close=100.0) for _ in range(180)]
    mock_news.return_value = [MagicMock(headline="Good news")]
    
    # 4-role pipeline output: Trader approves, Risk Manager approves
    trader_mock = MagicMock()
    trader_mock.direction = "bullish"
    trader_mock.confidence = 0.9
    trader_mock.rationale = "Bullish structure"
    
    risk_mock = MagicMock()
    risk_mock.approved = True
    risk_mock.adjusted_confidence = 0.85
    risk_mock.rationale = "Risk is fine"
    
    mock_eval.return_value = (trader_mock, risk_mock)
    
    # Options data
    contract_mock = MagicMock()
    contract_mock.type.value = "call"
    contract_mock.symbol = "AAPL260116C00100000"
    # Ensure it passes DTE filters in select_contract
    import datetime
    contract_mock.expiration_date = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20)).date()
    mock_fetch_contracts.return_value = [contract_mock]
    
    snapshot_mock = MagicMock()
    snapshot_mock.latest_quote.bid_price = 1.0
    snapshot_mock.latest_quote.ask_price = 1.1
    snapshot_mock.open_interest = 100
    snapshot_mock.greeks = None
    mock_select_contract.return_value = ("AAPL260116C00100000", snapshot_mock)
    
    mock_validate.return_value = True
    
    # Run the process
    result = await process_symbol("AAPL", 0)
    
    # Ensure it returns a valid opportunity dictionary for execution
    assert result is not None
    assert result["symbol"] == "AAPL"
    assert result["contract"] == "AAPL260116C00100000"
    assert result["direction"] == "bullish"
    assert result["confidence"] == 0.85

@pytest.mark.asyncio
@patch("main.fetch_stock_bars")
@patch("main.fetch_news")
@patch("main.evaluate_symbol_pipeline")
@patch("main.fetch_option_contracts")
async def test_invalid_opportunity_path_risk_veto(
    mock_fetch_contracts, mock_eval, mock_news, mock_bars
):
    # Mock data
    mock_bars.return_value = [MagicMock(close=100.0) for _ in range(180)]
    mock_news.return_value = []
    
    # 4-role pipeline output: Trader approves, Risk Manager VETOS
    trader_mock = MagicMock()
    trader_mock.direction = "bullish"
    trader_mock.confidence = 0.8
    trader_mock.rationale = "Looks okay"
    
    risk_mock = MagicMock()
    risk_mock.approved = False
    risk_mock.adjusted_confidence = 0.0
    risk_mock.rationale = "Too much risk"
    
    mock_eval.return_value = (trader_mock, risk_mock)
    
    result = await process_symbol("TSLA", 0)
    assert result is None
    # Ensure memory recorded the veto
    assert len(memory.history) > 0
    assert memory.history[-1]["action"] == "VETOED"
