from collections.abc import Callable

from app.config.rate_limits import DEFAULT_ENDPOINT_LIMIT, RATE_LIMITS, SERVICE_RATE_LIMITS


def endpoint_limit(endpoint_type: str) -> Callable[[str], str]:
    def _resolve(key: str) -> str:
        if key.startswith("service:"):
            service = key.split(":", 1)[1]
            svc_limit = SERVICE_RATE_LIMITS.get(service)
            if svc_limit:
                return svc_limit
        return RATE_LIMITS.get(endpoint_type, DEFAULT_ENDPOINT_LIMIT)

    return _resolve
