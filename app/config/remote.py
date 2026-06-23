from __future__ import annotations

import json
import sys

import httpx

_REMOTABLE_STR = frozenset({"PROXY_VN", "PROXY_US", "RATE_LIMIT_DEFAULT", "RATE_LIMIT_BURST"})

_JSON_DICT_KEYS = frozenset({
    "RATE_LIMITS",
    "BURST_LIMITS",
    "SERVICE_RATE_LIMITS",
})


def _normalize_proxy(p: str) -> str:
    """Convert host:port:user:pass → http://user:pass@host:port. Pass-through if already a URL."""
    if p.startswith("http://") or p.startswith("https://") or p.startswith("socks"):
        return p
    parts = p.split(":")
    if len(parts) == 4:
        host, port, user, passwd = parts
        return f"http://{user}:{passwd}@{host}:{port}"
    return p


def _apply_json_dict(settings, remote: dict, key: str, attr: str) -> None:
    raw = remote.get(key)
    if not raw:
        return
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return
    if isinstance(parsed, dict):
        setattr(settings, attr, {**getattr(settings, attr), **parsed})


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

    for key in _JSON_DICT_KEYS:
        _apply_json_dict(settings, remote, key, key)

    for key in ("PROXY_VN", "PROXY_US"):
        if remote.get(key):
            raw    = [p.strip() for p in remote[key].split(",") if p.strip()]
            parsed = [_normalize_proxy(p) for p in raw]
            setattr(settings, key, parsed)

    vn = getattr(settings, "PROXY_VN", [])
    if vn:
        setattr(settings, "PROXY_LIST", vn)

    try:
        from app.config.urls import proxy_manager, proxy_manager_us
        proxy_manager.set_proxies(getattr(settings, "PROXY_VN", []))
        proxy_manager_us.set_proxies(getattr(settings, "PROXY_US", []))
    except Exception:
        pass

    try:
        from slowapi import Limiter
        from app.middleware.rate_limit import limiter, get_identifier
        tmp = Limiter(
            key_func=get_identifier,
            default_limits=[
                getattr(settings, "RATE_LIMIT_DEFAULT"),
                getattr(settings, "RATE_LIMIT_BURST"),
            ],
        )
        limiter._default_limits = tmp._default_limits
    except Exception:
        pass
