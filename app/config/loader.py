"""Schema-driven remote config loader."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.config.proxy import load_proxy_pools

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "config" / "remote-schema.json"

RATE_LIMIT_SECTIONS = {
    "routes": "RATE_LIMITS",
    "burst": "BURST_LIMITS",
    "services": "SERVICE_RATE_LIMITS",
}


@dataclass
class RuntimeConfig:
    rate_limit: dict[str, Any] = field(default_factory=dict)
    proxy_pools: list[dict[str, Any]] = field(default_factory=list)


runtime = RuntimeConfig()


def load_schema() -> dict[str, Any]:
    with _SCHEMA_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


def parse_remote(raw: dict[str, str]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for key, value in raw.items():
        if value is None:
            continue
        try:
            parsed[key] = json.loads(value)
        except json.JSONDecodeError:
            parsed[key] = value
    return parsed


def _module(name: str):
    if name == "settings":
        return sys.modules["app.config.settings"]
    raise ValueError(f"unknown module: {name}")


def _apply_rate_limit_full(data: dict, bind: dict) -> None:
    target = _module(bind["module"])
    default = data.get("default") or {}
    if isinstance(default, dict):
        if default.get("limit"):
            target.RATE_LIMIT_DEFAULT = default["limit"]
        if default.get("burst"):
            target.RATE_LIMIT_BURST = default["burst"]
    for section, attr in RATE_LIMIT_SECTIONS.items():
        chunk = data.get(section)
        if isinstance(chunk, dict):
            current = getattr(target, attr)
            setattr(target, attr, {**current, **chunk})


def _apply_proxy_pools(data: list, bind: dict) -> None:
    load_proxy_pools(data)
    runtime.proxy_pools = data


def _store_runtime(key: str, data: Any, key_schema: dict) -> None:
    if key_schema.get("store") == "rate_limit" and isinstance(data, dict):
        runtime.rate_limit = data


_BINDERS: dict[str, Callable[..., None]] = {
    "rate_limit_full": _apply_rate_limit_full,
}


def apply_schema(parsed: dict[str, Any], schema: dict[str, Any]) -> None:
    for key, key_schema in schema.get("keys", {}).items():
        data = parsed.get(key)
        if data is None:
            continue

        bind = key_schema.get("bind") or {}
        bind_type = bind.get("type")

        if bind_type == "proxy_pools" and isinstance(data, list):
            _apply_proxy_pools(data, bind)
        elif bind_type in _BINDERS and isinstance(data, dict):
            _BINDERS[bind_type](data, bind)

        _store_runtime(key, data, key_schema)
