from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.errors import api_ok
from app.api.rate_limit_config import endpoint_limit
from app.crawlers.movies import client as movie_client
from app.crawlers.movies.config import MovieProvider
from app.middleware.auth_middleware import verify_api_key
from app.middleware.rate_limit import limiter
from app.services.movies import list_filters

router = APIRouter(dependencies=[Depends(verify_api_key)])

MovieType = Literal[
    "phim-bo",
    "phim-le",
    "tv-shows",
    "hoat-hinh",
    "phim-vietsub",
    "phim-thuyet-minh",
    "phim-long-tieng",
]


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
    return await api_ok(movie_client.search(provider, keyword=keyword, page=page, limit=limit))


@router.get("/new")
@limiter.limit(endpoint_limit("movies"))
async def list_new_movies(
    request: Request,
    response: Response,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
):
    return await api_ok(movie_client.get_new(provider, page=page))


@router.get("/meta/genres")
@limiter.limit(endpoint_limit("movies"))
async def meta_genres(request: Request, response: Response, provider: MovieProvider = "kkphim"):
    return await api_ok(movie_client.get_genres(provider))


@router.get("/meta/countries")
@limiter.limit(endpoint_limit("movies"))
async def meta_countries(request: Request, response: Response, provider: MovieProvider = "kkphim"):
    return await api_ok(movie_client.get_countries(provider))


@router.get("/meta/image-proxy")
@limiter.limit(endpoint_limit("movies"))
async def image_proxy(
    request: Request,
    response: Response,
    url: str = Query(..., min_length=1, description="URL ảnh phimimg.com (KKPhim only)"),
    provider: MovieProvider = "kkphim",
):
    return await api_ok(movie_client.proxy_webp(provider, image_url=url))


@router.get("/image/webp")
@limiter.limit(endpoint_limit("movies"))
async def image_webp_alias(
    request: Request,
    response: Response,
    url: str = Query(..., min_length=1),
    provider: MovieProvider = "kkphim",
):
    return await api_ok(movie_client.proxy_webp(provider, image_url=url))


@router.get("/types/{movie_type}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_type(
    request: Request,
    response: Response,
    movie_type: MovieType,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: str | None = None,
    country: str | None = None,
    year: int | None = Query(None, ge=1900, le=2100),
    sort_lang: Literal["vietsub", "thuyet-minh", "long-tieng"] | None = None,
    sort_field: Literal["modified.time", "_id", "year"] | None = None,
    sort_type: Literal["desc", "asc"] | None = None,
):
    return await api_ok(
        movie_client.list_by_type(
            provider,
            movie_type,
            page=page,
            limit=limit,
            **list_filters(
                category=category,
                country=country,
                year=year,
                sort_lang=sort_lang,
                sort_field=sort_field,
                sort_type=sort_type,
            ),
        )
    )


@router.get("/type/{movie_type}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_type_alias(
    request: Request,
    response: Response,
    movie_type: MovieType,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: str | None = None,
    country: str | None = None,
    year: int | None = Query(None, ge=1900, le=2100),
    sort_lang: Literal["vietsub", "thuyet-minh", "long-tieng"] | None = None,
    sort_field: Literal["modified.time", "_id", "year"] | None = None,
    sort_type: Literal["desc", "asc"] | None = None,
):
    return await list_by_type(
        request,
        response,
        movie_type,
        provider,
        page,
        limit,
        category,
        country,
        year,
        sort_lang,
        sort_field,
        sort_type,
    )


@router.get("/genres/{slug}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_genre(
    request: Request,
    response: Response,
    slug: str,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: str | None = None,
    country: str | None = None,
    year: int | None = Query(None, ge=1900, le=2100),
    sort_lang: Literal["vietsub", "thuyet-minh", "long-tieng"] | None = None,
    sort_field: Literal["modified.time", "_id", "year"] | None = None,
    sort_type: Literal["desc", "asc"] | None = None,
):
    return await api_ok(
        movie_client.list_by_genre(
            provider,
            slug,
            page=page,
            limit=limit,
            **list_filters(
                category=category,
                country=country,
                year=year,
                sort_lang=sort_lang,
                sort_field=sort_field,
                sort_type=sort_type,
            ),
        )
    )


@router.get("/countries/{slug}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_country(
    request: Request,
    response: Response,
    slug: str,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: str | None = None,
    country: str | None = None,
    year: int | None = Query(None, ge=1900, le=2100),
    sort_lang: Literal["vietsub", "thuyet-minh", "long-tieng"] | None = None,
    sort_field: Literal["modified.time", "_id", "year"] | None = None,
    sort_type: Literal["desc", "asc"] | None = None,
):
    return await api_ok(
        movie_client.list_by_country(
            provider,
            slug,
            page=page,
            limit=limit,
            **list_filters(
                category=category,
                country=country,
                year=year,
                sort_lang=sort_lang,
                sort_field=sort_field,
                sort_type=sort_type,
            ),
        )
    )


@router.get("/years/{year}")
@limiter.limit(endpoint_limit("movies"))
async def list_by_year(
    request: Request,
    response: Response,
    year: int,
    provider: MovieProvider = "kkphim",
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=64),
    category: str | None = None,
    country: str | None = None,
    sort_lang: Literal["vietsub", "thuyet-minh", "long-tieng"] | None = None,
    sort_field: Literal["modified.time", "_id", "year"] | None = None,
    sort_type: Literal["desc", "asc"] | None = None,
):
    return await api_ok(
        movie_client.list_by_year(
            provider,
            year,
            page=page,
            limit=limit,
            **list_filters(
                category=category,
                country=country,
                sort_lang=sort_lang,
                sort_field=sort_field,
                sort_type=sort_type,
            ),
        )
    )


@router.get("/{slug}")
@limiter.limit(endpoint_limit("movies"))
async def get_movie(
    request: Request,
    response: Response,
    slug: str,
    provider: MovieProvider = "kkphim",
):
    return await api_ok(movie_client.get_detail(provider, slug))
