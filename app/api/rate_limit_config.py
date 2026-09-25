from collections.abc import Callable

from app.config import rate_limits


def endpoint_limit(endpoint_type: str) -> Callable[[str], str]:
    """Per-route limit resolved at request time, so remote-config updates (which
    replace the dicts in app.config.rate_limits) take effect without a restart."""

    def _resolve(key: str) -> str:
        if key.startswith("service:"):
            service = key.split(":", 1)[1]
            svc_limit = rate_limits.SERVICE_RATE_LIMITS.get(service)
            if svc_limit:
                return svc_limit
        return rate_limits.RATE_LIMITS.get(endpoint_type, rate_limits.DEFAULT_ENDPOINT_LIMIT)

    return _resolve
