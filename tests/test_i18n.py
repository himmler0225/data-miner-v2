from app.i18n import t
from app.i18n.locale import normalize_locale, resolve_locale_from_scope


def test_t_vi_en():
    assert t("errors.invalid_api_key", "vi") == "API key không hợp lệ"
    assert t("errors.missing_api_key", "en") == "Missing API key"


def test_normalize_locale():
    assert normalize_locale("vi") == "vi"
    assert normalize_locale("en-GB") == "en"


def test_resolve_locale_from_scope():
    scope = {"headers": [(b"x-locale", b"vi")]}
    assert resolve_locale_from_scope(scope) == "vi"
