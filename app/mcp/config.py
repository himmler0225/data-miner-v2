import os

MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
MCP_SSE_PATH: str = os.getenv("MCP_SSE_PATH", "/mcp")
