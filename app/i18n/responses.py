"""Map message keys to localized client text."""

from app.i18n import get_locale, localize


def localize_detail(detail: str, locale: str | None = None) -> str:
    return localize(str(detail), locale or get_locale())
