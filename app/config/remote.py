from __future__ import annotations
import sys
import httpx

_REMOTABLE_STR = frozenset({"PROXY_VN", "PROXY_US", "RATE_LIMIT_DEFAULT", "RATE_LIMIT_BURST"})


async def load_and_apply() -> None:
    from app.config.settings import SUPABASE_URL, SUPABASE_SERVICE_KEY
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{SUPABASE_URL}/rest/v1/config",
                params={"select": "key,value"},
                headers={
                    "apikey":        SUPABASE_SERVICE_KEY,
                    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
                },
            )
            if not r.is_success:
                return
            remote: dict[str, str] = {
                row["key"]: row["value"]
                for row in r.json()
                if row.get("value")
            }
    except Exception:
        return

    settings = sys.modules["app.config.settings"]

    for key in _REMOTABLE_STR:
        if remote.get(key):
            setattr(settings, key, remote[key])

    # PROXY_VN / PROXY_US là list — parse lại sau khi set string
    for key in ("PROXY_VN", "PROXY_US"):
        if remote.get(key):
            parsed = [p.strip() for p in remote[key].split(",") if p.strip()]
            setattr(settings, key, parsed)

    # PROXY_LIST re-derive từ PROXY_VN
    vn = getattr(settings, "PROXY_VN", [])
    if vn:
        setattr(settings, "PROXY_LIST", vn)
