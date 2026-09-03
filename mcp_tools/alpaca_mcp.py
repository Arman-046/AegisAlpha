import asyncio
import os
import datetime
from typing import Dict, Any, List
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult

from data.clients import trading_client, stock_data_client, news_client
from alpaca.data.requests import StockBarsRequest, NewsRequest
from alpaca.data.timeframe import TimeFrame
from app_logging.logger import get_logger
from config.settings import settings

log = get_logger(__name__)

class MCPClientWrapper:
    def __init__(self):
        self.stack = AsyncExitStack()
        self.session = None
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self):
        async with self._lock:
            if self._initialized:
                return
            
            try:
                env = {
                    **os.environ,
                    "ALPACA_API_KEY": settings.APCA_API_KEY_ID,
                    "ALPACA_SECRET_KEY": settings.APCA_API_SECRET_KEY
                }
                server_params = StdioServerParameters(
                    command="cmd.exe",
                    args=["/c", "uvx", "alpaca-mcp-server"],
                    env=env
                )
                
                log.info("Starting official Alpaca MCP server via uvx...")
                read, write = await self.stack.enter_async_context(stdio_client(server_params))
                self.session = await self.stack.enter_async_context(ClientSession(read, write))
                await self.session.initialize()
                self._initialized = True
                log.info("Official Alpaca MCP server initialized successfully.")
            except Exception as e:
                log.error(f"Failed to initialize official MCP server: {e}. Will use python fallback.")
                await self.close()
                self._initialized = False

    async def execute_tool(self, name: str, arguments: dict) -> str:
        if not self._initialized:
            await self.initialize()
            
        if self._initialized and self.session:
            try:
                log.info(f"Executing MCP tool (Official Path): {name}")
                result: CallToolResult = await self.session.call_tool(name, arguments)
                if result.isError:
                    log.error(f"MCP server returned error for {name}: {result.content}")
                    raise Exception("MCP server error")
                
                # result.content is a list of TextContent or ImageContent
                texts = []
                for content in result.content:
                    if content.type == "text":
                        texts.append(content.text)
                return "\n".join(texts)
            except Exception as e:
                log.warning(f"Official MCP tool {name} failed: {e}. Falling back to alpaca-py.")
                
        return execute_mcp_tool_fallback(name, arguments)

    async def close(self):
        await self.stack.aclose()
        self._initialized = False
        self.session = None


# Singleton instance
mcp_client = MCPClientWrapper()


# Define the tools mapping for the Gemini LLM (matching official names roughly)
ALPACA_MCP_TOOLS = [
    {
        "name": "get_account_info",
        "description": "Retrieves the current Alpaca paper account information including equity, buying power, and status.",
        "input_schema": {
            "type": "object",
            "properties": {},
        }
    },
    {
        "name": "get_all_positions",
        "description": "Retrieves all current open positions in the portfolio.",
        "input_schema": {
            "type": "object",
            "properties": {},
        }
    },
    {
        "name": "get_stock_bars",
        "description": "Retrieves daily historical price bars for a given symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol_or_symbols": {"type": "string", "description": "Stock ticker symbol (e.g., AAPL)"},
                "timeframe": {"type": "string", "description": "Timeframe, use '1Day'"},
                "limit": {"type": "integer", "description": "Number of days (e.g. 30)"}
            },
            "required": ["symbol_or_symbols"]
        }
    },
    {
        "name": "get_news",
        "description": "Retrieves the latest news articles for a given symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbols": {"type": "string", "description": "Stock ticker symbol"},
                "limit": {"type": "integer", "description": "Number of articles"}
            },
            "required": ["symbols"]
        }
    }
]

def execute_mcp_tool_fallback(tool_name: str, args: Dict[str, Any]) -> str:
    """
    Fallback implementation using alpaca-py.
    """
    log.info(f"Executing MCP tool (Fallback Path): {tool_name}")
    try:
        if tool_name == "get_account_info":
            acct = trading_client.get_account()
            return f"Equity: ${acct.equity}, BP: ${acct.buying_power}, Status: {acct.status.name}"
            
        elif tool_name == "get_all_positions":
            positions = trading_client.get_all_positions()
            if not positions:
                return "No open positions."
            pos_strs = [f"{p.qty}x {p.symbol} (Unrealized P&L: {p.unrealized_pl})" for p in positions]
            return "\n".join(pos_strs)
            
        elif tool_name == "get_stock_bars":
            sym = args.get("symbol_or_symbols", args.get("symbol"))
            # Fallback uses days instead of strict limit if missing
            limit = args.get("limit", 30)
            end = datetime.datetime.now(datetime.timezone.utc)
            start = end - datetime.timedelta(days=limit)
            req = StockBarsRequest(symbol_or_symbols=sym, timeframe=TimeFrame.Day, start=start, end=end)
            bars = stock_data_client.get_stock_bars(req)
            if not bars or sym not in bars.data:
                return "No data found."
            lines = [f"{b.timestamp.date()}: Close=${b.close}" for b in bars.data[sym][-10:]]
            return "\n".join(lines)
            
        elif tool_name == "get_news":
            sym = args.get("symbols", args.get("symbol"))
            limit = args.get("limit", 3)
            req = NewsRequest(symbols=sym, limit=limit)
            news = news_client.get_news(req)
            if not news or not news.news:
                return "No news found."
            return "\n".join([f"- {n.headline}" for n in news.news])
            
        else:
            return f"Unknown tool: {tool_name}"
            
    except Exception as e:
        log.error(f"Fallback MCP Tool execution failed for {tool_name}: {e}")
        return f"Error executing fallback tool: {e}"
