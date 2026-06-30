from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.rate_limit_config import endpoint_limit
from app.crawlers.movies import client as movie_client
from app.middleware.auth_middleware import verify_api_key
from app.middleware.rate_limit import limiter
from app.schemas.response import ApiResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])

MovieProvider = Literal["kkphim", "ophim"]
MovieType = Literal[
    "phim-bo",
    "phim-le",
    "tv-shows",
    "hoat-hinh",
    "phim-vietsub",
    "phim-thuyet-minh",
    "phim-long-tieng",
]


def _filters(
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = None,
    sort_lang: Optional[str] = None,
    sort_field: Optional[str] = None,
    sort_type: Optional[str] = None,
) -> dict:
    return {
        "category": category,
        "country": country,
        "year": year,
        "sort_lang": sort_lang,
        "sort_field": sort_field,
        "sort_type": sort_type,
    }


def _handle_movie_error(exc: Exception) -> None:
    if isinstance(exc, movie_client.MovieValidationError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, movie_client.MovieUpstreamError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


@router.get("/search")
@limiter.limit(endpoint_limit("movies"))
async def search_movies(
    request: Request,
    response: Response,
    keyword: str = Query(..., min_length=1),
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
):
    try:
        return ApiResponse.ok(
            await movie_client.search(provider, keyword=keyword, page=page, limit=limit)
        )
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/new")
@limiter.limit(endpoint_limit("movies"))
async def list_new_movies(
    request: Request,
    response: Response,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
):
    try:
        return ApiResponse.ok(await movie_client.get_new(provider, page=page))
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/meta/genres")
@limiter.limit(endpoint_limit("movies"))
async def meta_genres(request: Request, response: Response, provider: MovieProvider = "kkphim"):
    try:
        return ApiResponse.ok(await movie_client.get_genres(provider))
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/meta/countries")
@limiter.limit(endpoint_limit("movies"))
async def meta_countries(request: Request, response: Response, provider: MovieProvider = "kkphim"):
    try:
        return ApiResponse.ok(await movie_client.get_countries(provider))
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/meta/image-proxy")
@limiter.limit(endpoint_limit("movies"))
async def image_proxy(
    request: Request,
    response: Response,
    url: str = Query(..., min_length=1, description="URL ảnh phimimg.com (KKPhim only)"),
    provider: MovieProvider = "kkphim",
):
    try:
        return ApiResponse.ok(await movie_client.proxy_webp(provider, image_url=url))
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/image/webp")
@limiter.limit(endpoint_limit("movies"))
async def image_webp_alias(
    request: Request,
    response: Response,
    url: str = Query(..., min_length=1),
    provider: MovieProvider = "kkphim",
):
    try:
        return ApiResponse.ok(await movie_client.proxy_webp(provider, image_url=url))
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/types/{movie_type}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_type(
    request: Request,
    response: Response,
    movie_type: MovieType,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = Query(None, ge=1900, le=2100),
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    try:
        return ApiResponse.ok(
            await movie_client.list_by_type(
                provider,
                movie_type,
                page=page,
                limit=limit,
                **_filters(category, country, year, sort_lang, sort_field, sort_type),
            )
        )
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/type/{movie_type}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_type_alias(
    request: Request,
    response: Response,
    movie_type: MovieType,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = Query(None, ge=1900, le=2100),
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    try:
        return ApiResponse.ok(
            await movie_client.list_by_type(
                provider,
                movie_type,
                page=page,
                limit=limit,
                **_filters(category, country, year, sort_lang, sort_field, sort_type),
            )
        )
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/genres/{slug}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_genre(
    request: Request,
    response: Response,
    slug: str,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = Query(None, ge=1900, le=2100),
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    try:
        return ApiResponse.ok(
            await movie_client.list_by_genre(
                provider,
                slug,
                page=page,
                limit=limit,
                **_filters(category, country, year, sort_lang, sort_field, sort_type),
            )
        )
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/countries/{slug}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_country(
    request: Request,
    response: Response,
    slug: str,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    year: Optional[int] = Query(None, ge=1900, le=2100),
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    try:
        return ApiResponse.ok(
            await movie_client.list_by_country(
                provider,
                slug,
                page=page,
                limit=limit,
                **_filters(category, country, year, sort_lang, sort_field, sort_type),
            )
        )
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/years/{year}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_year(
    request: Request,
    response: Response,
    year: int,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: Optional[str] = None,
    country: Optional[str] = None,
    sort_lang: Optional[Literal["vietsub", "thuyet-minh", "long-tieng"]] = None,
    sort_field: Optional[Literal["modified.time", "_id", "year"]] = None,
    sort_type: Optional[Literal["desc", "asc"]] = None,
):
    try:
        return ApiResponse.ok(
            await movie_client.list_by_year(
                provider,
                year,
                page=page,
                limit=limit,
                **_filters(category, country, None, sort_lang, sort_field, sort_type),
            )
        )
    except Exception as exc:
        _handle_movie_error(exc)


@router.get("/{slug}")
@limiter.limit(endpoint_limit("movies"))
async def get_movie(
    request: Request,
    response: Response,
    slug: str,
    provider: MovieProvider = "kkphim",
):
    try:
        return ApiResponse.ok(await movie_client.get_detail(provider, slug))
    except Exception as exc:
        _handle_movie_error(exc)
