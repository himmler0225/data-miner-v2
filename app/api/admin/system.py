from __future__ import annotations

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query

from app.config.proxy import get_proxy, registry
from app.middleware import verify_api_key
from app.schemas.response import ApiResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/proxy/status")
async def proxy_status():
    return ApiResponse.ok(registry.status())


@router.post("/proxy/rotate")
async def proxy_rotate(country: Optional[str] = None):
    registry.rotate(country)
    return ApiResponse.ok({"rotated": True, "country": country})


@router.get("/proxy/test")
async def test_proxy(pool: str = Query("vn")):
    country = pool.upper()
    proxy_url = await get_proxy(country)
    if not proxy_url:
        return ApiResponse.ok(
            {"status": "error", "detail": f"No proxy for '{country}'"}
        )
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=10) as client:
            resp = await client.get("http://httpbin.org/ip")
            ip = resp.json().get("origin", "unknown")
        return ApiResponse.ok({"status": "ok", "pool": country, "exit_ip": ip})
    except Exception as e:
        return ApiResponse.ok({"status": "error", "pool": country, "error": repr(e)})
