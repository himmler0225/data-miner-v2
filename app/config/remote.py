from __future__ import annotations
import httpx
import app.config.settings as settings
from app.config.constants import REMOTE_CONFIG_TIMEOUT
from app.config.headers import get_supabase_rest_headers
from app.config.loader import apply_schema, load_schema, parse_remote

async def load_and_apply() -> None:
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
        return
    schema = load_schema()
    try:
        async with httpx.AsyncClient(timeout=REMOTE_CONFIG_TIMEOUT) as client:
            response = await client.get(f'{settings.SUPABASE_URL}/rest/v1/config', params={'select': 'key,value'}, headers=get_supabase_rest_headers(settings.SUPABASE_SERVICE_KEY))
            if not response.is_success:
                return
            remote = {row['key']: row['value'] for row in response.json() if row.get('value')}
    except Exception:
        return
    apply_schema(parse_remote(remote), schema)
    try:
        from slowapi import Limiter
        from app.middleware.rate_limit import get_identifier, limiter
        tmp = Limiter(key_func=get_identifier, default_limits=[settings.RATE_LIMIT_DEFAULT, settings.RATE_LIMIT_BURST])
        limiter._default_limits = tmp._default_limits
    except Exception:
        pass
