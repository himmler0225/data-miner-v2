import httpx
from fastapi import APIRouter, Depends
from app.middleware import verify_api_key
from app.config.urls import proxy_manager, proxy_manager_us
from app.schemas.response import ApiResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])

@router.get("/proxy/status")
async def proxy_status():
    return ApiResponse.ok({"vn": proxy_manager.status(), "us": proxy_manager_us.status()})

@router.post("/proxy/rotate")
async def proxy_rotate():
    proxy_manager.rotate()
    proxy_manager_us.rotate()
    return ApiResponse.ok({"rotated": True})

@router.get("/proxy/test")
async def test_proxy(pool: str = "vn"):
    mgr = proxy_manager_us if pool == "us" else proxy_manager
    proxy_url = await mgr.get_proxy()
    if not proxy_url:
        return ApiResponse.ok({"status": "error", "detail": f"No proxy in '{pool}' pool"})
    try:
        async with httpx.AsyncClient(proxy=proxy_url, timeout=10) as client:
            resp = await client.get("http://httpbin.org/ip")
            ip = resp.json().get("origin", "unknown")
        return ApiResponse.ok({"status": "ok", "pool": pool, "exit_ip": ip})
    except Exception as e:
        return ApiResponse.ok({"status": "error", "pool": pool, "error": repr(e)})
