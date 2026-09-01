import pytest
import asyncio
from unittest.mock import patch, MagicMock
from reasoning.agent import (
    _run_analyst, _run_trader, _run_risk_manager, evaluate_symbol_pipeline,
    AnalystDecision, TraderDecision, RiskDecision
)

class MockGeminiResponse:
    def __init__(self, text, function_calls=None):
        self.text = text
        self.function_calls = function_calls or []
        
    @property
    def candidates(self):
        class MockCandidate:
            class MockContent:
                parts = []
            content = MockContent()
        return [MockCandidate()]

@pytest.fixture
def mock_gemini_client():
    with patch("reasoning.agent.get_async_client") as mock_get:
        client = MagicMock()
        mock_get.return_value = client
        yield client

@pytest.mark.asyncio
async def test_gemini_successful_analyst_response(mock_gemini_client):
    mock_gemini_client.aio.models.generate_content = MagicMock(return_value=asyncio.Future())
    mock_gemini_client.aio.models.generate_content.return_value.set_result(
        MockGeminiResponse('{"confidence": 0.8, "rationale": "Looks good"}')
    )
    
    result = await _run_analyst("AAPL", "Prompt", "System Prompt")
    assert isinstance(result, AnalystDecision)
    assert result.confidence == 0.8

@pytest.mark.asyncio
async def test_gemini_trader_structured_output(mock_gemini_client):
    mock_gemini_client.aio.models.generate_content = MagicMock(return_value=asyncio.Future())
    mock_gemini_client.aio.models.generate_content.return_value.set_result(
        MockGeminiResponse('{"direction": "bullish", "confidence": 0.75, "rationale": "I agree"}')
    )
    
    result = await _run_trader("AAPL", "Prompt")
    assert isinstance(result, TraderDecision)
    assert result.direction == "bullish"

@pytest.mark.asyncio
async def test_gemini_failure_raises_exception(mock_gemini_client):
    mock_gemini_client.aio.models.generate_content = MagicMock(side_effect=Exception("API Error 400"))
    
    with pytest.raises(Exception) as exc:
        await _run_analyst("AAPL", "Prompt", "System Prompt")
    assert "API Error 400" in str(exc.value)

@pytest.mark.asyncio
async def test_concurrent_bull_bear(mock_gemini_client):
    mock_gemini_client.aio.models.generate_content = MagicMock(return_value=asyncio.Future())
    mock_gemini_client.aio.models.generate_content.return_value.set_result(
        MockGeminiResponse('{"confidence": 0.9, "rationale": "Argument"}')
    )
    
    with patch("reasoning.agent._run_trader", return_value=TraderDecision(direction="neutral", confidence=0.0, rationale="pass")) as mock_trader:
        trader_decision, risk_decision = await evaluate_symbol_pipeline(
            "AAPL", "bars", "news", "normal", "context", 0.65, 0, "event"
        )
        assert trader_decision is not None
        assert trader_decision.direction == "neutral"

@pytest.mark.asyncio
async def test_gemini_failure_aborts_pipeline(mock_gemini_client):
    mock_gemini_client.aio.models.generate_content = MagicMock(side_effect=Exception("API Error 400"))
    
    trader_decision, risk_decision = await evaluate_symbol_pipeline(
        "AAPL", "bars", "news", "normal", "context", 0.65, 0, "event"
    )
    
    assert trader_decision is None
    assert risk_decision is None
