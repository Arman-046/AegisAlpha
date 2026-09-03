import asyncio
import json
from pydantic import BaseModel, Field, ValidationError
from typing import Literal, Tuple, Any
from config.settings import settings
from app_logging.logger import get_logger
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
import traceback

from groq import AsyncGroq

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

class BullDecision(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_evidence: str
    expected_directional_impact: str
    catalyst: str

class BearDecision(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    challenge_event: str
    noise_reasoning: str
    risks: str
    evidence_against_thesis: str

class TraderDecision(BaseModel):
    direction: Literal["bullish", "bearish", "neutral"]
    opportunity_exists: bool
    confidence: float = Field(ge=0.0, le=1.0)
    synthesis: str
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
            if settings.GROQ_API_KEY and settings.GROQ_API_KEY != "PK_DUMMY":
                _async_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        except Exception as e:
            log.error(f"Failed to initialize Groq Client: {e}")
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
        schema_json = ScreenerResponse.model_json_schema()
        system_msg = f"{PORTFOLIO_MANAGER_SYSTEM_PROMPT}\n\nYou must return a valid JSON object adhering to the following JSON schema:\n{json.dumps(schema_json)}"
        
        completion = await asyncio.wait_for(
            client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Please analyze these top quantitative candidates and select the 5 best:\n{candidates_data}"}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            ),
            timeout=60.0
        )
        res_text = completion.choices[0].message.content
        if not res_text: return None
        
        data = json.loads(res_text)
        validated = ScreenerResponse(**data)
        
        return [c.model_dump() for c in validated.watchlist]
        
    except Exception as e:
        log.error(f"Failed to generate screener watchlist: {e}")
        return None


def get_groq_tools() -> list:
    """Translates ALPACA_MCP_TOOLS to OpenAI FunctionDeclarations"""
    tools = []
    for t in ALPACA_MCP_TOOLS:
        tools.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t.get("input_schema", {"type": "object", "properties": {}})
            }
        })
    return tools

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_transient_error), reraise=False, retry_error_callback=lambda rs: None)
async def _run_analyst(symbol: str, prompt: str, system_prompt: str, schema_class) -> Any:
    client = get_async_client()
    if not client: return None
    try:
        schema_json = schema_class.model_json_schema()
        system_msg = f"{system_prompt}\n\nYou must return a valid JSON object adhering to the following JSON schema:\n{json.dumps(schema_json)}"
        
        completion = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        res_text = completion.choices[0].message.content
        if not res_text:
            raise ValueError("Empty response from Groq")
        data = json.loads(res_text)
        return schema_class(**data)
    except Exception as e:
        log.warning(f"Analyst error for {symbol}: {e}")
        raise e

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_transient_error), reraise=False, retry_error_callback=lambda rs: None)
async def _run_trader(symbol: str, prompt: str) -> TraderDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        messages = [
            {"role": "system", "content": TRADER_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        completion = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            tools=get_groq_tools(),
            tool_choice="auto",
            temperature=0.0
        )
        
        response_message = completion.choices[0].message
        
        while response_message.tool_calls:
            messages.append(response_message.model_dump(exclude_unset=True))
            
            for tool_call in response_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                
                log.info(f"Trader requested tool: {tool_name} with {tool_args}")
                tool_result = await mcp_client.execute_tool(tool_name, tool_args)
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps({"result": tool_result})
                })
                
            completion = await client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=messages,
                tools=get_groq_tools(),
                tool_choice="auto",
                temperature=0.0
            )
            response_message = completion.choices[0].message

        # Final pass to ensure we get structured output matching TraderDecision
        schema_json = TraderDecision.model_json_schema()
        messages.append({
            "role": "user",
            "content": f"Please provide your final decision in JSON matching this schema:\n{json.dumps(schema_json)}"
        })
        
        final_completion = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0
        )

        res_text = final_completion.choices[0].message.content
        if not res_text:
            raise ValueError("Empty final response from Groq")
            
        data = json.loads(res_text)
        return TraderDecision(**data)
        
    except Exception as e:
        log.warning(f"Trader error for {symbol}: {e}")
        raise e

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), retry=retry_if_exception(is_transient_error), reraise=False, retry_error_callback=lambda rs: None)
async def _run_risk_manager(symbol: str, prompt: str) -> RiskDecision | None:
    client = get_async_client()
    if not client: return None
    try:
        schema_json = RiskDecision.model_json_schema()
        system_msg = f"{RISK_SYSTEM_PROMPT}\n\nYou must return a valid JSON object adhering to the following JSON schema:\n{json.dumps(schema_json)}"
        completion = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        res_text = completion.choices[0].message.content
        if not res_text:
            raise ValueError("Empty response from Groq")
        data = json.loads(res_text)
        return RiskDecision(**data)
    except Exception as e:
        log.warning(f"Risk Manager error for {symbol}: {e}")
        raise e

async def evaluate_symbol_pipeline(symbol: str, bars_summary: str, news_summary: str, vol_regime: str, recent_context: str, threshold: float, open_positions: int, event_context: str = "") -> Tuple[TraderDecision | None, RiskDecision | None]:
    """Runs the full four-role reasoning pipeline asynchronously."""
    
    analyst_prompt = build_analyst_prompt(symbol, bars_summary, news_summary, vol_regime, event_context)
    
    # 1. Concurrent Bull and Bear
    log.info(f"[{symbol}] Starting concurrent Bull and Bear Analyst evaluation with Groq...")
    obs.update_stage("BULL", "PROCESSING")
    obs.update_stage("BEAR", "PROCESSING")
    
    bull_task = asyncio.create_task(_run_analyst(symbol, analyst_prompt, BULL_SYSTEM_PROMPT, BullDecision))
    bear_task = asyncio.create_task(_run_analyst(symbol, analyst_prompt, BEAR_SYSTEM_PROMPT, BearDecision))
    
    try:
        bull_decision, bear_decision = await asyncio.wait_for(
            asyncio.gather(bull_task, bear_task), timeout=90.0
        )
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
        
    bull_arg = f"Conf: {bull_decision.confidence}, Catalyst: {bull_decision.catalyst}, Impact: {bull_decision.expected_directional_impact}, Evidence: {bull_decision.supporting_evidence}"
    bear_arg = f"Conf: {bear_decision.confidence}, Challenge: {bear_decision.challenge_event}, Risks: {bear_decision.risks}, Evidence Against: {bear_decision.evidence_against_thesis}"
    
    # 2. Synthesize via Trader
    obs.update_stage("TRADER", "PROCESSING")
    trader_prompt = build_trader_prompt(symbol, bull_arg, bear_arg, recent_context, threshold)
    try:
        trader_decision = await asyncio.wait_for(_run_trader(symbol, trader_prompt), timeout=150.0)
        if trader_decision:
            obs.update_stage("TRADER", "COMPLETED")
        else:
            obs.update_stage("TRADER", "FAILED")
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
        risk_decision = await asyncio.wait_for(_run_risk_manager(symbol, risk_prompt), timeout=90.0)
        if risk_decision:
            obs.update_stage("RISK", "COMPLETED")
        else:
            obs.update_stage("RISK", "FAILED")
    except Exception as e:
        log.warning(f"Risk manager failed for {symbol}: {e}")
        obs.update_stage("RISK", "FAILED")
        return trader_decision, None
    
    return trader_decision, risk_decision
