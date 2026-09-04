import asyncio
import json
from pydantic import BaseModel, Field
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception
from app_logging.logger import get_logger
from config.settings import settings

log = get_logger(__name__)

class MacroDecision(BaseModel):
    market_assessment: str
    threshold_modifier: float = Field(ge=-0.2, le=0.3)

async def _run_macro_agent(spy_prompt: str) -> MacroDecision | None:
    # Need to import inside to avoid circular dependency if agent imports this
    from reasoning.agent import get_async_client, is_transient_error
    from reasoning.prompts import MACRO_SYSTEM_PROMPT
    
    client = get_async_client()
    if not client: return None
    
    try:
        schema_json = MacroDecision.model_json_schema()
        system_msg = f"{MACRO_SYSTEM_PROMPT}\n\nYou must return a valid JSON object adhering to the following JSON schema:\n{json.dumps(schema_json)}"
        
        completion = await client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": spy_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        res_text = completion.choices[0].message.content
        if not res_text:
            raise ValueError("Empty response from Groq for Macro Agent")
        data = json.loads(res_text)
        return MacroDecision(**data)
    except Exception as e:
        log.warning(f"Macro Agent error: {e}")
        return None
