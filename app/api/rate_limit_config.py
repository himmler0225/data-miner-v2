from __future__ import annotations

from typing import Callable

import app.config.settings as settings

_DEFAULT_ENDPOINT = "30/minute"


def endpoint_limit(endpoint_type: str) -> Callable[[str], str]:
    def _resolve(key: str) -> str:
        if key.startswith("service:"):
            service = key.split(":", 1)[1]
            svc_limit = settings.SERVICE_RATE_LIMITS.get(service)
            if svc_limit:
                return svc_limit
        return settings.RATE_LIMITS.get(endpoint_type, _DEFAULT_ENDPOINT)

    return _resolve
