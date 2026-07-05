from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.i18n.locale import resolve_locale, set_locale


class LocaleMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        set_locale(resolve_locale(request))
        return await call_next(request)
