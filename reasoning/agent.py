import asyncio
import json
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Tuple, Any
from config.settings import settings
from app_logging.logger import get_logger
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
import traceback

from google import genai
from google.genai import types

from mcp_tools.alpaca_mcp import ALPACA_MCP_TOOLS, mcp_client

from reasoning.prompts import (
    BULL_SYSTEM_PROMPT,
    BEAR_SYSTEM_PROMPT,
    TRADER_SYSTEM_PROMPT,
    RISK_SYSTEM_PROMPT,
    PORTFOLIO_MANAGER_SYSTEM_PROMPT,
    build_analyst_prompt,
    build_trader_prompt,
    build_risk_prompt
)

from state.observability import obs

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

class ScreenerCandidate(BaseModel):
    symbol: str
    score: int = Field(ge=0, le=100)
    reason: str
    bull_case: str
    bear_case: str
    confidence: float = Field(ge=0.0, le=1.0)
    key_risk: str
    options_interest: str

class ScreenerResponse(BaseModel):
    watchlist: list[ScreenerCandidate]

_async_client = None

def get_async_client():
    global _async_client
    if _async_client is None:
        try:
            if settings.GEMINI_API_KEY:
                _async_client = genai.Client(api_key=settings.GEMINI_API_KEY)
        except Exception as e:
            log.error(f"Failed to initialize Gemini Client: {e}")
    return _async_client

def is_transient_error(e: Exception) -> bool:
    err_str = str(e).lower()
    if "400" in err_str or "401" in err_str or "403" in err_str or "404" in err_str:
        return False
    return True

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_transient_error), reraise=False, retry_error_callback=lambda rs: None)
async def evaluate_screener_candidates(candidates_data: str) -> list[dict] | None:
    client = get_async_client()
    if not client: return None
    try:
        res = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=f"Please analyze these top quantitative candidates and select the 5 best:\n{candidates_data}",
            config=types.GenerateContentConfig(
                system_instruction=PORTFOLIO_MANAGER_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=ScreenerResponse,
                temperature=0.2
            )
        )
        if not res.text: return None
        
        data = json.loads(res.text)
        validated = ScreenerResponse(**data)
        
        return [c.model_dump() for c in validated.watchlist]
        
    except Exception as e:
        log.error(f"Failed to generate screener watchlist: {e}")
        return None


def get_gemini_tools() -> list:
    """Translates ALPACA_MCP_TOOLS to Gemini FunctionDeclarations"""
    gemini_funcs = []
    for t in ALPACA_MCP_TOOLS:
        props = t.get("input_schema", {}).get("properties", {})
        required = t.get("input_schema", {}).get("required", [])
        
        gemini_props = {}
        for k, v in props.items():
            type_str = v.get("type", "string").upper()
            gemini_props[k] = types.Schema(
                type=getattr(types.Type, type_str, types.Type.STRING),
                description=v.get("description", "")
            )
            
        func_decl = types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties=gemini_props,
                required=required
            ) if gemini_props else None
        )
        gemini_funcs.append(func_decl)
    return [types.Tool(function_declarations=gemini_funcs)]

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_transient_error), reraise=False, retry_error_callback=lambda rs: None)
async def _run_analyst(symbol: str, prompt: str, system_prompt: str) -> AnalystDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        res = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=AnalystDecision,
                temperature=0.0
            )
        )
        if not res.text:
            raise ValueError("Empty response from Gemini")
        data = json.loads(res.text)
        return AnalystDecision(**data)
    except Exception as e:
        log.warning(f"Analyst error for {symbol}: {e}")
        raise e

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_transient_error), reraise=False, retry_error_callback=lambda rs: None)
async def _run_trader(symbol: str, prompt: str) -> TraderDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        messages = [{"role": "user", "parts": [types.Part.from_text(text=prompt)]}]
        
        config = types.GenerateContentConfig(
            system_instruction=TRADER_SYSTEM_PROMPT,
            tools=get_gemini_tools(),
            temperature=0.0
        )
        
        res = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=messages,
            config=config
        )
        
        # Check if tool use was requested
        while res.function_calls:
            messages.append({"role": "model", "parts": res.candidates[0].content.parts})
            
            tool_responses = []
            for fn_call in res.function_calls:
                tool_name = fn_call.name
                tool_args = fn_call.args if fn_call.args else {}
                
                log.info(f"Trader requested tool: {tool_name} with {tool_args}")
                tool_result = await mcp_client.execute_tool(tool_name, tool_args)
                
                tool_responses.append(
                    types.Part.from_function_response(
                        name=tool_name,
                        response={"result": tool_result}
                    )
                )
                
            messages.append({"role": "user", "parts": tool_responses})
            
            res = await client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=messages,
                config=config
            )
            
        # Final pass to ensure we get structured output matching TraderDecision
        # Sometimes tools config doesn't perfectly mix with response_schema in one go,
        # so we extract the JSON or enforce it now if it didn't use a tool.
        # However, to be safe, we can just ask Gemini to parse its final answer into the schema.
        final_config = types.GenerateContentConfig(
            system_instruction=TRADER_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=TraderDecision,
            temperature=0.0
        )
        
        final_res = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=messages + [{"role": "user", "parts": [types.Part.from_text(text="Please provide your final decision in JSON matching the schema.")]}],
            config=final_config
        )

        if not final_res.text:
            raise ValueError("Empty final response from Gemini")
            
        data = json.loads(final_res.text)
        return TraderDecision(**data)
        
    except Exception as e:
        log.warning(f"Trader error for {symbol}: {e}")
        raise e

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_transient_error), reraise=False, retry_error_callback=lambda rs: None)
async def _run_risk_manager(symbol: str, prompt: str) -> RiskDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        res = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=RISK_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=RiskDecision,
                temperature=0.0
            )
        )
        if not res.text:
            raise ValueError("Empty response from Gemini")
        data = json.loads(res.text)
        return RiskDecision(**data)
    except Exception as e:
        log.warning(f"Risk Manager error for {symbol}: {e}")
        raise e

async def evaluate_symbol_pipeline(symbol: str, bars_summary: str, news_summary: str, vol_regime: str, recent_context: str, threshold: float, open_positions: int, event_context: str = "") -> Tuple[TraderDecision | None, RiskDecision | None]:
    """Runs the full four-role reasoning pipeline asynchronously."""
    
    analyst_prompt = build_analyst_prompt(symbol, bars_summary, news_summary, vol_regime, event_context)
    
    # 1. Concurrent Bull and Bear
    log.info(f"[{symbol}] Starting concurrent Bull and Bear Analyst evaluation with Gemini...")
    obs.update_stage("BULL", "PROCESSING")
    obs.update_stage("BEAR", "PROCESSING")
    bull_task = asyncio.create_task(_run_analyst(symbol, analyst_prompt, BULL_SYSTEM_PROMPT))
    bear_task = asyncio.create_task(_run_analyst(symbol, analyst_prompt, BEAR_SYSTEM_PROMPT))
    
    try:
        bull_decision, bear_decision = await asyncio.gather(bull_task, bear_task)
        log.info(f"[{symbol}] Concurrent evaluation complete. Bull Conf: {bull_decision.confidence if bull_decision else None}, Bear Conf: {bear_decision.confidence if bear_decision else None}")
    except Exception as e:
        log.warning(f"Failed to get analyst decisions for {symbol} due to error: {e}")
        obs.update_stage("BULL", "FAILED")
        obs.update_stage("BEAR", "FAILED")
        return None, None
    
    if not bull_decision or not bear_decision:
        log.warning(f"Failed to get analyst decisions for {symbol}")
        obs.update_stage("BULL", "FAILED")
        obs.update_stage("BEAR", "FAILED")
        return None, None
        
    obs.update_stage("BULL", "COMPLETED")
    obs.update_stage("BEAR", "COMPLETED")
        
    bull_arg = f"Conf: {bull_decision.confidence}, Rationale: {bull_decision.rationale}"
    bear_arg = f"Conf: {bear_decision.confidence}, Rationale: {bear_decision.rationale}"
    
    # 2. Synthesize via Trader
    obs.update_stage("TRADER", "PROCESSING")
    trader_prompt = build_trader_prompt(symbol, bull_arg, bear_arg, recent_context, threshold)
    try:
        trader_decision = await _run_trader(symbol, trader_prompt)
        obs.update_stage("TRADER", "COMPLETED")
    except Exception as e:
        log.warning(f"Trader failed for {symbol}: {e}")
        obs.update_stage("TRADER", "FAILED")
        return None, None
    
    if not trader_decision or trader_decision.direction == "neutral" or trader_decision.confidence < threshold:
        return trader_decision, None
        
    # 3. Risk Manager Validation
    obs.update_stage("RISK", "PROCESSING")
    risk_prompt = build_risk_prompt(symbol, trader_decision.direction, trader_decision.confidence, vol_regime, open_positions)
    try:
        risk_decision = await _run_risk_manager(symbol, risk_prompt)
        obs.update_stage("RISK", "COMPLETED")
    except Exception as e:
        log.warning(f"Risk manager failed for {symbol}: {e}")
        obs.update_stage("RISK", "FAILED")
        return trader_decision, None
    
    return trader_decision, risk_decision
