"""Proxy pools — load từ PROXY_POOLS (Supabase) và lấy proxy theo quốc gia."""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

import httpx

from app.config.logger import Logger

logger = Logger.get(__name__)

DEFAULT_COUNTRY = "VN"
TIKTOK_COUNTRY = "US"

_API_PROXY_TTL = int(os.getenv("PROXY_API_TTL", "45"))
_DIRECT_TTL = 900


def normalize_proxy(proxy: str) -> str:
    proxy = proxy.strip()
    if proxy.startswith(("http://", "https://", "socks")):
        return proxy
    parts = proxy.split(":")
    if len(parts) == 4:
        host, port, user, passwd = parts
        return f"http://{user}:{passwd}@{host}:{port}"
    if len(parts) == 2:
        host, port = parts
        return f"http://{host}:{port}"
    return proxy


class _DirectPool:
    """Round-robin / random selection cho proxy direct (static URL)."""

    def __init__(self, proxies: List[str], ttl: int = _DIRECT_TTL) -> None:
        self._ttl = ttl
        self._meta: Dict[str, float] = {}
        self._proxies = self._clean(proxies)
        self._index = 0
        if not self._proxies:
            logger.warning("[Proxy] direct pool empty after normalize")

    def _clean(self, proxies: List[str]) -> List[str]:
        out: List[str] = []
        for raw in proxies:
            if not isinstance(raw, str):
                continue
            p = raw.strip()
            if not p:
                continue
            if "://" in p and ":" in p:
                out.append(p)
            elif p.count(":") == 1:
                out.append(p)
            else:
                logger.warning("[Proxy] dropped invalid proxy: %s", p)
        return out

    def get_random(self) -> Optional[str]:
        available = [p for p in self._proxies if self._can_use(p)] or self._proxies
        if not available:
            return None
        proxy = random.choice(available)
        self._meta[proxy] = time.time()
        return proxy

    def get_all(self) -> List[str]:
        return list(self._proxies)

    def _can_use(self, proxy: str) -> bool:
        last = self._meta.get(proxy)
        if last is None or len(self._proxies) <= 1:
            return True
        return (time.time() - last) >= self._ttl


@dataclass
class DirectProvider:
    type: Literal["direct"] = "direct"
    value: str = ""


@dataclass
class ApiProvider:
    type: Literal["api"] = "api"
    url: str = ""
    method: str = "GET"
    query: dict[str, str] = field(default_factory=dict)


@dataclass
class PoolConfig:
    key: str
    countries: list[str]
    provider: DirectProvider | ApiProvider


@dataclass
class _ApiCacheEntry:
    proxy: str
    fetched_at: float


def _parse_provider(raw: dict) -> Optional[DirectProvider | ApiProvider]:
    provider = raw.get("provider")
    if isinstance(provider, dict):
        ptype = str(provider.get("type") or "direct").lower()
        if ptype == "api":
            query = provider.get("query") or {}
            return ApiProvider(
                url=str(provider.get("url") or ""),
                method=str(provider.get("method") or "GET").upper(),
                query={str(k): str(v) for k, v in query.items()},
            )
        value = provider.get("value") or ""
        if value:
            return DirectProvider(value=str(value))
        return None
    legacy_value = raw.get("value") or ""
    if legacy_value:
        return DirectProvider(value=str(legacy_value))
    return None


def _parse_pool_entry(raw: dict) -> Optional[PoolConfig]:
    if not isinstance(raw, dict):
        return None
    provider = _parse_provider(raw)
    if provider is None:
        return None
    countries = [str(c).upper() for c in (raw.get("countries") or []) if c]
    if not countries:
        return None
    return PoolConfig(
        key=str(raw.get("key") or "_".join(countries).lower()),
        countries=countries,
        provider=provider,
    )


def _resolve_query(query: dict[str, str]) -> dict[str, str]:
    public_ip = os.getenv("PUBLIC_IP", "")
    return {
        key: value.replace("[ip]", public_ip).replace("{public_ip}", public_ip)
        for key, value in query.items()
    }


def _parse_api_proxy_body(body: str) -> Optional[str]:
    text = body.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            for key in ("proxyhttp", "proxy", "data", "message", "result"):
                val = data.get(key)
                if isinstance(val, str) and ":" in val:
                    return val.split()[0] if " " in val else val
    except json.JSONDecodeError:
        pass
    candidate = text.split()[0] if " " in text else text
    return candidate if ":" in candidate else None


class ProxyRegistry:
    """Single registry — load once at startup, get_proxy() reads from memory."""

    def __init__(self) -> None:
        self._by_country: dict[str, list[PoolConfig]] = {}
        self._direct: dict[str, _DirectPool] = {}
        self._api_cache: dict[str, _ApiCacheEntry] = {}
        self._round_robin: dict[str, int] = {}

    def load(self, pools: list[Any]) -> None:
        self._by_country.clear()
        self._direct.clear()
        self._api_cache.clear()
        self._round_robin.clear()

        for raw in pools:
            entry = _parse_pool_entry(raw)
            if entry is None:
                continue
            for country in entry.countries:
                self._by_country.setdefault(country, []).append(entry)

        for country, entries in self._by_country.items():
            urls: list[str] = []
            for entry in entries:
                if isinstance(entry.provider, DirectProvider):
                    for item in entry.provider.value.split(","):
                        item = item.strip()
                        if item:
                            urls.append(normalize_proxy(item))
            self._direct[country] = _DirectPool(urls)

        logger.info(
            "[Proxy] loaded countries=%s direct=%s api=%s",
            sorted(self._by_country),
            {c: len(p.get_all()) for c, p in self._direct.items()},
            {
                c: sum(1 for e in es if isinstance(e.provider, ApiProvider))
                for c, es in self._by_country.items()
            },
        )

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for country, entries in sorted(self._by_country.items()):
            pool = self._direct.get(country)
            out[country] = {
                "pools": [
                    {
                        "key": e.key,
                        "type": e.provider.type,
                        "direct_count": (
                            len(pool.get_all())
                            if isinstance(e.provider, DirectProvider) and pool
                            else 0
                        ),
                        "api_cached": (
                            e.key in self._api_cache
                            if isinstance(e.provider, ApiProvider)
                            else False
                        ),
                    }
                    for e in entries
                ],
                "direct_total": len(pool.get_all()) if pool else 0,
            }
        return out

    def rotate(self, country: Optional[str] = None) -> None:
        if country:
            code = country.upper()
            prefix = f"{code}:"
            self._api_cache = {
                k: v for k, v in self._api_cache.items() if not k.startswith(prefix)
            }
            self._round_robin[code] = 0
            return
        self._api_cache.clear()
        self._round_robin.clear()

    async def get(self, country: str = DEFAULT_COUNTRY) -> Optional[str]:
        code = country.upper()
        entries = self._by_country.get(code) or []
        if not entries:
            logger.warning("[Proxy] no pool for country=%s", code)
            return None

        start = self._round_robin.get(code, 0)
        for offset in range(len(entries)):
            entry = entries[(start + offset) % len(entries)]
            proxy: Optional[str] = None
            if isinstance(entry.provider, DirectProvider):
                pool = self._direct.get(code)
                proxy = pool.get_random() if pool else None
            elif isinstance(entry.provider, ApiProvider):
                proxy = await self._fetch_api(entry)

            if proxy:
                self._round_robin[code] = (start + offset + 1) % len(entries)
                return proxy
        return None

    async def _fetch_api(self, entry: PoolConfig) -> Optional[str]:
        assert isinstance(entry.provider, ApiProvider)
        provider = entry.provider
        cached = self._api_cache.get(entry.key)
        if cached and (time.time() - cached.fetched_at) < _API_PROXY_TTL:
            return cached.proxy

        if not provider.url:
            logger.warning("[Proxy] api pool=%s missing url", entry.key)
            return None

        params = _resolve_query(provider.query)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                if provider.method == "POST":
                    response = await client.post(provider.url, params=params)
                else:
                    response = await client.get(provider.url, params=params)
                response.raise_for_status()
                raw = _parse_api_proxy_body(response.text)
        except Exception as exc:
            logger.warning("[Proxy] api pool=%s fetch failed: %s", entry.key, exc)
            return None

        if not raw:
            logger.warning("[Proxy] api pool=%s empty response", entry.key)
            return None

        proxy = normalize_proxy(raw)
        self._api_cache[entry.key] = _ApiCacheEntry(proxy=proxy, fetched_at=time.time())
        logger.info("[Proxy] api pool=%s resolved", entry.key)
        return proxy


registry = ProxyRegistry()


def load_proxy_pools(pools: list[Any]) -> None:
    registry.load(pools)


async def get_proxy(country: str = DEFAULT_COUNTRY) -> Optional[str]:
    return await registry.get(country)
