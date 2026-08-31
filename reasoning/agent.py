import asyncio
import json
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Tuple, Any
from config.settings import settings
from app_logging.logger import get_logger
from tenacity import retry, wait_exponential, stop_after_attempt
import anthropic
from mcp_tools.alpaca_mcp import ALPACA_MCP_TOOLS, mcp_client

from reasoning.prompts import (
    BULL_SYSTEM_PROMPT,
    BEAR_SYSTEM_PROMPT,
    TRADER_SYSTEM_PROMPT,
    RISK_SYSTEM_PROMPT,
    build_analyst_prompt,
    build_trader_prompt,
    build_risk_prompt
)

log = get_logger(__name__)

class AnalystDecision(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

class TraderDecision(BaseModel):
    direction: Literal["bullish", "bearish", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    
class RiskDecision(BaseModel):
    approved: bool
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

_async_client = None

def get_async_client():
    global _async_client
    if _async_client is None:
        try:
            _async_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        except Exception:
            pass
    return _async_client

def _extract_json(raw_text: str) -> dict:
    if raw_text.startswith("```json"):
        raw_text = raw_text.replace("```json", "", 1)
    if raw_text.startswith("```"):
        raw_text = raw_text.replace("```", "", 1)
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    return json.loads(raw_text.strip())

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False, retry_error_callback=lambda rs: None)
async def _run_analyst(symbol: str, prompt: str, system_prompt: str) -> AnalystDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        res = await client.messages.create(
            model=settings.ANTHROPIC_MODEL_ID,
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}]
        )
        data = _extract_json(res.content[0].text)
        return AnalystDecision(**data)
    except Exception as e:
        log.warning(f"Analyst error for {symbol}: {e}")
        raise e

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False, retry_error_callback=lambda rs: None)
async def _run_trader(symbol: str, prompt: str) -> TraderDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        messages = [{"role": "user", "content": prompt}]
        # Trader has access to MCP tools
        res = await client.messages.create(
            model=settings.ANTHROPIC_MODEL_ID,
            max_tokens=400,
            system=TRADER_SYSTEM_PROMPT,
            messages=messages,
            tools=ALPACA_MCP_TOOLS
        )
        
        # Check if tool use was requested
        while res.stop_reason == "tool_use":
            tool_use = next(block for block in res.content if block.type == "tool_use")
            tool_name = tool_use.name
            tool_input = tool_use.input
            
            log.info(f"Trader requested tool: {tool_name} with {tool_input}")
            tool_result = await mcp_client.execute_tool(tool_name, tool_input)
            
            messages.append({"role": "assistant", "content": res.content})
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": tool_result
                    }
                ]
            })
            
            # Send result back
            res = await client.messages.create(
                model=settings.ANTHROPIC_MODEL_ID,
                max_tokens=400,
                system=TRADER_SYSTEM_PROMPT,
                messages=messages,
                tools=ALPACA_MCP_TOOLS
            )
            
        # Extract final JSON
        text_block = next((block.text for block in res.content if block.type == "text"), "")
        data = _extract_json(text_block)
        return TraderDecision(**data)
    except Exception as e:
        log.warning(f"Trader error for {symbol}: {e}")
        raise e

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=False, retry_error_callback=lambda rs: None)
async def _run_risk_manager(symbol: str, prompt: str) -> RiskDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        res = await client.messages.create(
            model=settings.ANTHROPIC_MODEL_ID,
            max_tokens=300,
            system=RISK_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        data = _extract_json(res.content[0].text)
        return RiskDecision(**data)
    except Exception as e:
        log.warning(f"Risk Manager error for {symbol}: {e}")
        raise e

async def evaluate_symbol_pipeline(symbol: str, bars_summary: str, news_summary: str, vol_regime: str, recent_context: str, threshold: float, open_positions: int, event_context: str = "") -> Tuple[TraderDecision | None, RiskDecision | None]:
    """Runs the full four-role reasoning pipeline asynchronously."""
    
    analyst_prompt = build_analyst_prompt(symbol, bars_summary, news_summary, vol_regime, event_context)
    
    # 1. Concurrent Bull and Bear
    log.info(f"[{symbol}] Starting concurrent Bull and Bear Analyst evaluation...")
    bull_task = asyncio.create_task(_run_analyst(symbol, analyst_prompt, BULL_SYSTEM_PROMPT))
    bear_task = asyncio.create_task(_run_analyst(symbol, analyst_prompt, BEAR_SYSTEM_PROMPT))
    
    bull_decision, bear_decision = await asyncio.gather(bull_task, bear_task)
    log.info(f"[{symbol}] Concurrent evaluation complete. Bull Conf: {bull_decision.confidence if bull_decision else None}, Bear Conf: {bear_decision.confidence if bear_decision else None}")
    
    if not bull_decision or not bear_decision:
        log.warning(f"Failed to get analyst decisions for {symbol}")
        return None, None
        
    bull_arg = f"Conf: {bull_decision.confidence}, Rationale: {bull_decision.rationale}"
    bear_arg = f"Conf: {bear_decision.confidence}, Rationale: {bear_decision.rationale}"
    
    # 2. Synthesize via Trader
    trader_prompt = build_trader_prompt(symbol, bull_arg, bear_arg, recent_context, threshold)
    trader_decision = await _run_trader(symbol, trader_prompt)
    
    if not trader_decision or trader_decision.direction == "neutral" or trader_decision.confidence < threshold:
        return trader_decision, None
        
    # 3. Risk Manager Validation
    risk_prompt = build_risk_prompt(symbol, trader_decision.direction, trader_decision.confidence, vol_regime, open_positions)
    risk_decision = await _run_risk_manager(symbol, risk_prompt)
    
    return trader_decision, risk_decision
