import asyncio
from typing import Any
from urllib.parse import quote

import httpx

from app.config.http import HTTP_MAX_ATTEMPTS, HTTP_MAX_CONNECTIONS, HTTP_MAX_KEEPALIVE, HTTP_RETRY_STATUSES
from app.config.logger import Logger
from app.crawlers.movies.config import (
    MOVIE_API_TIMEOUT,
    MOVIE_LIST_TYPES,
    PROVIDERS,
    MovieProvider,
    ProviderSpec,
)
from app.exceptions import CrawlerBaseError, CrawlNetworkError

logger = Logger.get(__name__)


class MovieValidationError(CrawlerBaseError):
    pass


class MovieUpstreamError(CrawlNetworkError):
    pass


_clients: dict[MovieProvider, httpx.AsyncClient] = {}


def normalize_provider(name: str) -> MovieProvider:
    key = (name or "kkphim").strip().lower()
    if key not in PROVIDERS:
        raise MovieValidationError(f"Unknown movie provider: {name!r} (use kkphim or ophim)")
    return key  # type: ignore[return-value]


def get_provider_spec(provider: str) -> ProviderSpec:
    return PROVIDERS[normalize_provider(provider)]


def _get_client(spec: ProviderSpec) -> httpx.AsyncClient:
    if spec.name not in _clients or _clients[spec.name].is_closed:
        _clients[spec.name] = httpx.AsyncClient(
            base_url=spec.base_url,
            timeout=MOVIE_API_TIMEOUT,
            headers={"Accept": "application/json"},
            limits=httpx.Limits(
                max_connections=HTTP_MAX_CONNECTIONS,
                max_keepalive_connections=HTTP_MAX_KEEPALIVE,
            ),
        )
    return _clients[spec.name]


async def close_clients() -> None:
    for client in _clients.values():
        if not client.is_closed:
            await client.aclose()
    _clients.clear()


def _list_query_params(
    *,
    page: int = 1,
    limit: int = 24,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"page": max(page, 1), "limit": min(max(limit, 1), 64)}
    for key, value in {
        "category": category,
        "country": country,
        "year": year,
        "sort_lang": sort_lang,
        "sort_field": sort_field,
        "sort_type": sort_type,
    }.items():
        if value is not None and value != "":
            params[key] = value
    return params


async def _request(provider: str, method: str, path: str, *, params: dict[str, Any] | None = None) -> Any:
    spec = get_provider_spec(provider)
    last_exc: Exception | None = None
    for attempt in range(1, HTTP_MAX_ATTEMPTS + 1):
        try:
            response = await _get_client(spec).request(method, path, params=params or {})
            if response.status_code in HTTP_RETRY_STATUSES:
                raise httpx.HTTPStatusError(
                    f"{response.status_code} from {spec.name}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response.json()
        except (httpx.NetworkError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in HTTP_RETRY_STATUSES:
                break
        if attempt < HTTP_MAX_ATTEMPTS:
            delay = 2 ** (attempt - 1)
            logger.warning("[%s] %s %s retry=%d delay=%ds", spec.name, method, path, attempt, delay)
            await asyncio.sleep(delay)
    logger.error("[%s] %s %s failed", spec.name, method, path)
    raise MovieUpstreamError(f"{spec.name} request failed: {last_exc}") from last_exc


def _with_meta(data: Any, *, provider: str) -> dict[str, Any]:
    spec = get_provider_spec(provider)
    return {
        "provider": spec.name,
        "source": spec.name,
        "image_cdn": spec.image_cdn,
        "data": data,
    }


async def get_new(provider: str, *, page: int = 1) -> dict[str, Any]:
    spec = get_provider_spec(provider)
    data = await _request(provider, "GET", spec.new_movies_path, params={"page": max(page, 1)})
    return _with_meta(data, provider=provider)


async def list_by_type(
    provider: str,
    movie_type: str,
    *,
    page: int = 1,
    limit: int = 24,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict[str, Any]:
    if movie_type not in MOVIE_LIST_TYPES:
        raise MovieValidationError(f"Invalid movie type: {movie_type!r}")
    spec = get_provider_spec(provider)
    params = _list_query_params(
        page=page,
        limit=limit,
        category=category if spec.type_list_full_filters else None,
        country=country if spec.type_list_full_filters else None,
        year=year if spec.type_list_full_filters else None,
        sort_lang=sort_lang if spec.type_list_full_filters else None,
        sort_field=sort_field if spec.type_list_full_filters else None,
        sort_type=sort_type if spec.type_list_full_filters else None,
    )
    if not spec.type_list_full_filters:
        params = {"page": params["page"], "limit": params["limit"]}
    data = await _request(provider, "GET", f"/v1/api/danh-sach/{movie_type}", params=params)
    return _with_meta(data, provider=provider)


async def get_detail(provider: str, slug: str) -> dict[str, Any]:
    slug = (slug or "").strip().strip("/")
    if not slug:
        raise MovieValidationError("slug is required")
    data = await _request(provider, "GET", f"/phim/{slug}")
    return _with_meta(data, provider=provider)


async def search(
    provider: str,
    *,
    keyword: str,
    page: int = 1,
    limit: int = 24,
) -> dict[str, Any]:
    keyword = (keyword or "").strip()
    if not keyword:
        raise MovieValidationError("keyword is required")
    data = await _request(
        provider,
        "GET",
        "/v1/api/tim-kiem",
        params={"keyword": keyword, "page": max(page, 1), "limit": min(max(limit, 1), 64)},
    )
    return _with_meta(data, provider=provider)


async def list_by_genre(
    provider: str,
    slug: str,
    *,
    page: int = 1,
    limit: int = 24,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict[str, Any]:
    slug = (slug or "").strip().strip("/")
    if not slug:
        raise MovieValidationError("genre slug is required")
    params = _list_query_params(
        page=page,
        limit=limit,
        category=category,
        country=country,
        year=year,
        sort_lang=sort_lang,
        sort_field=sort_field,
        sort_type=sort_type,
    )
    data = await _request(provider, "GET", f"/v1/api/the-loai/{slug}", params=params)
    return _with_meta(data, provider=provider)


async def list_by_country(
    provider: str,
    slug: str,
    *,
    page: int = 1,
    limit: int = 24,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict[str, Any]:
    slug = (slug or "").strip().strip("/")
    if not slug:
        raise MovieValidationError("country slug is required")
    params = _list_query_params(
        page=page,
        limit=limit,
        category=category,
        country=country,
        year=year,
        sort_lang=sort_lang,
        sort_field=sort_field,
        sort_type=sort_type,
    )
    data = await _request(provider, "GET", f"/v1/api/quoc-gia/{slug}", params=params)
    return _with_meta(data, provider=provider)


async def list_by_year(
    provider: str,
    year: int,
    *,
    page: int = 1,
    limit: int = 24,
    category: str | None = None,
    country: str | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict[str, Any]:
    if year < 1900 or year > 2100:
        raise MovieValidationError("year must be a 4-digit year")
    params = _list_query_params(
        page=page,
        limit=limit,
        category=category,
        country=country,
        year=year,
        sort_lang=sort_lang,
        sort_field=sort_field,
        sort_type=sort_type,
    )
    data = await _request(provider, "GET", f"/v1/api/nam/{year}", params=params)
    return _with_meta(data, provider=provider)


async def get_genres(provider: str) -> dict[str, Any]:
    data = await _request(provider, "GET", "/the-loai")
    return _with_meta(data, provider=provider)


async def get_countries(provider: str) -> dict[str, Any]:
    data = await _request(provider, "GET", "/quoc-gia")
    return _with_meta(data, provider=provider)


async def proxy_webp(provider: str, *, image_url: str) -> dict[str, Any]:
    spec = get_provider_spec(provider)
    if not spec.has_webp_proxy:
        raise MovieValidationError(f"{spec.name} does not support WebP image proxy")
    image_url = (image_url or "").strip()
    if not image_url:
        raise MovieValidationError("image_url is required")
    proxy_url = f"{spec.base_url}/image.php?url={quote(image_url, safe='')}"
    return {
        "provider": spec.name,
        "proxy_url": proxy_url,
        "original_url": image_url,
    }
