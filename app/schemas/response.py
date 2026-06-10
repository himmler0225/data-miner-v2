from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    success: bool
    data:    Any                    = None
    error:   Optional[str]          = None
    meta:    Dict[str, Any]         = Field(default_factory=dict)

    @classmethod
    def ok(cls, data: Any = None, **meta: Any) -> ApiResponse:
        return cls(
            success=True,
            data=data,
            meta={"timestamp": _ts(), **meta},
        )

    @classmethod
    def fail(cls, error: str, **meta: Any) -> ApiResponse:
        return cls(
            success=False,
            error=error,
            meta={"timestamp": _ts(), **meta},
        )


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()
