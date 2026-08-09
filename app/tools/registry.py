from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal

Platform = Literal["youtube", "tiktok"]

TOOL_REGISTRY: dict[str, "AgentToolSpec"] = {}


@dataclass(frozen=True)
class AgentToolSpec:
    name: str
    description: str
    platform: Platform
    parameters: dict[str, Any]
    handler: Callable[[dict], Awaitable[Any]]
    expose_mcp: bool = True
    expose_agent: bool = True


def register(spec: AgentToolSpec) -> None:
    TOOL_REGISTRY[spec.name] = spec
