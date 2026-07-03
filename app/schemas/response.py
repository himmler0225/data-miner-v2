from datetime import datetime, UTC
from typing import Any
from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, **meta: Any) -> ApiResponse:
        return cls(success=True, data=data, meta={"timestamp": _ts(), **meta})

    @classmethod
    def fail(cls, error: str, **meta: Any) -> ApiResponse:
        return cls(success=False, error=error, meta={"timestamp": _ts(), **meta})


def _ts() -> str:
    return datetime.now(UTC).isoformat()
