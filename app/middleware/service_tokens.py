from __future__ import annotations

import os
from typing import Optional

from app.config.settings import WHITELISTED_SERVICES


def expected_service_token(service_name: str) -> Optional[str]:
    if not service_name:
        return None
    env_key = f"SERVICE_TOKEN_{service_name.upper().replace('-', '_')}"
    return os.getenv(env_key)


def is_whitelisted_service(service_name: Optional[str]) -> bool:
    if not service_name:
        return False
    allowed = set(WHITELISTED_SERVICES)
    return not allowed or service_name in allowed


def validate_service_identity(
    service_name: Optional[str],
    service_token: Optional[str],
) -> bool:
    if not service_name or not service_token:
        return False
    if not is_whitelisted_service(service_name):
        return False
    expected = expected_service_token(service_name)
    return bool(expected and service_token == expected)
