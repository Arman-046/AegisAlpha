import asyncio
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    server_params = StdioServerParameters(
        command="cmd.exe",
        args=["/c", "uvx", "alpaca-mcp-server"],
        env={
            **os.environ,
            "ALPACA_API_KEY": "dummy",
            "ALPACA_SECRET_KEY": "dummy"
        }
    )

    print("Starting client...")
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                for tool in tools.tools:
                    print(f"Tool: {tool.name}")
                    print(f"  Description: {tool.description}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
