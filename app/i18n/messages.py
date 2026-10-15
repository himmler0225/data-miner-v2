"""User-facing API messages — vi / en (logs stay Vietnamese on server)."""

from typing import Any

Locale = str

MESSAGES: dict[str, dict[str, str]] = {
    "errors.invalid_api_key": {
        "vi": "API key không hợp lệ",
        "en": "Invalid API key",
    },
    "errors.missing_api_key": {
        "vi": "Thiếu API Key",
        "en": "Missing API key",
    },
    "errors.api_auth_not_configured": {
        "vi": "Xác thực API chưa được cấu hình",
        "en": "API authentication not configured",
    },
    "errors.service_identity_required": {
        "vi": "Yêu cầu xác thực service (X-Service-Name / X-Service-Token)",
        "en": "Service identity required",
    },
    "errors.invalid_service_token": {
        "vi": "Service token không hợp lệ",
        "en": "Invalid service token",
    },
    "errors.ip_not_whitelisted": {
        "vi": "Truy cập bị từ chối: IP hoặc service không nằm trong whitelist",
        "en": "Access denied: IP address or service not whitelisted",
    },
    "errors.invalid_mcp_token": {
        "vi": "MCP auth token không hợp lệ",
        "en": "Invalid MCP auth token",
    },
    "errors.video_ids_empty": {
        "vi": "Danh sách video_ids trống",
        "en": "video_ids is empty",
    },
    "errors.too_many_video_ids": {
        "vi": "Tối đa {max} video_ids mỗi lần gọi",
        "en": "At most {max} video_ids per call",
    },
    "errors.invalid_id": {
        "vi": "{kind} không hợp lệ: {value}",
        "en": "Invalid {kind}: {value}",
    },
    "errors.invalid_param": {
        "vi": "Tham số {name} không hợp lệ: {value}",
        "en": "Invalid {name}: {value}",
    },
    "errors.invalid_cursor": {
        "vi": "Cursor không hợp lệ",
        "en": "Invalid cursor",
    },
    "errors.not_found": {
        "vi": "Không tìm thấy: {detail}",
        "en": "Not found: {detail}",
    },
    "errors.upstream_rate_limited": {
        "vi": "YouTube đang giới hạn request — vui lòng thử lại sau",
        "en": "Upstream is rate limiting requests — please retry later",
    },
    "errors.unknown_topic": {
        "vi": "Topic không hợp lệ: {topic}. Có sẵn: {available}",
        "en": "Unknown topic '{topic}'. Available: {available}",
    },
    "errors.youtube_structure_changed": {
        "vi": "Cấu trúc YouTube thay đổi: {detail}",
        "en": "YouTube structure changed: {detail}",
    },
    "errors.upstream": {
        "vi": "Lỗi upstream — vui lòng thử lại",
        "en": "Upstream error — please retry",
    },
    "errors.generic": {
        "vi": "Đã xảy ra lỗi — vui lòng thử lại",
        "en": "Something went wrong — please retry",
    },
}


def t(key: str, locale: Locale, **params: Any) -> str:
    entry = MESSAGES.get(key)
    if not entry:
        return key
    text = entry.get(locale) or entry.get("en") or key
    if params:
        return text.format(**params)
    return text


def localize(text: str, locale: Locale, **params: Any) -> str:
    if text in MESSAGES:
        return t(text, locale, **params)
    return text
