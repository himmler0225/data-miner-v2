import os

from app.config.settings import WHITELISTED_SERVICES


def expected_service_token(service_name: str) -> str | None:
    if not service_name:
        return None
    env_key = f"SERVICE_TOKEN_{service_name.upper().replace('-', '_')}"
    return os.getenv(env_key)


def is_whitelisted_service(service_name: str | None) -> bool:
    if not service_name:
        return False
    allowed = set(WHITELISTED_SERVICES)
    return not allowed or service_name in allowed


def validate_service_identity(
    service_name: str | None,
    service_token: str | None,
) -> bool:
    if not service_name or not service_token:
        return False
    if not is_whitelisted_service(service_name):
        return False
    expected = expected_service_token(service_name)
    return bool(expected and service_token == expected)
