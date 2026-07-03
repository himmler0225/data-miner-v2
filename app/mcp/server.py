import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from app.tools.registry import TOOL_REGISTRY

server = Server("data-miner")


@server.list_tools()
async def list_tools() -> list[Tool]:
    out: list[Tool] = []
    for spec in TOOL_REGISTRY.values():
        if not spec.expose_mcp:
            continue
        out.append(
            Tool(
                name=spec.name,
                description=spec.description,
                inputSchema=spec.parameters,
            )
        )
    return out


@server.call_tool()
async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
    spec = TOOL_REGISTRY.get(name)
    if not spec or not spec.expose_mcp:
        raise ValueError(f"Unknown tool: {name}")

    args = arguments or {}
    try:
        data = await spec.handler(args)
        payload = {"success": True, "data": data}
    except Exception as exc:
        payload = {"success": False, "error": str(exc), "tool": name}

    return [TextContent(type="text", text=json.dumps(payload, ensure_ascii=False))]


async def main_stdio() -> None:
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main_stdio())