from __future__ import annotations

from typing import Callable

import app.config.settings as settings

_DEFAULT_ENDPOINT = "30/minute"


def endpoint_limit(endpoint_type: str) -> Callable[[], str]:
    """Return a callable for slowapi — resolves limit at request time."""

    def _resolve() -> str:
        return settings.RATE_LIMITS.get(endpoint_type, _DEFAULT_ENDPOINT)

    return _resolve


def get_rate_limit(endpoint_type: str) -> str:
    return settings.RATE_LIMITS.get(endpoint_type, _DEFAULT_ENDPOINT)


def get_burst_limit(endpoint_type: str) -> str:
    return settings.BURST_LIMITS.get(endpoint_type, "3/10seconds")


def get_service_rate_limit(service_name: str) -> str:
    return settings.SERVICE_RATE_LIMITS.get(
        service_name,
        settings.SERVICE_RATE_LIMITS.get("default", "50/minute"),
    )
