"""Tool registry — import handlers to populate TOOL_REGISTRY."""

import app.tools.handlers  # noqa: F401 — side-effect: registers all tools
from app.tools.registry import AgentToolSpec, TOOL_REGISTRY, register

__all__ = ["AgentToolSpec", "TOOL_REGISTRY", "register"]
