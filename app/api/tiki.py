from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.rate_limit_config import endpoint_limit
from app.config.logger import Logger
from app.config.proxy import get_proxy
from app.crawlers.tiki.maybe_you_like import get_maybe_you_like
from app.crawlers.tiki.product_detail import get_product_detail
from app.crawlers.tiki.reviews import get_all_reviews, get_reviews
from app.crawlers.tiki.sales import get_flash_sale
from app.crawlers.tiki.search import search_products
from app.crawlers.tiki.top_choice import get_top_choice
from app.crawlers.youtube.utils import retry_on_failure
from app.middleware import limiter, verify_api_key
from app.schemas.response import ApiResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = Logger.get(__name__)


def _raise_tiki_error(e: Exception) -> None:
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 404:
            raise HTTPException(status_code=404, detail="Not found")
        if 400 <= code < 500:
            raise HTTPException(status_code=code, detail="Tiki API client error")
    raise HTTPException(status_code=502, detail=str(e))


@router.get("/products/search", summary="Search For Products")
@limiter.limit(endpoint_limit("tiki"))
async def search_products_endpoint(
    request: Request,
    response: Response,
    q: str = Query(..., description="Keyword..."),
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=50),
    sort: str = Query(
        "relevance",
        enum=["relevance", "top_seller", "newest", "price_asc", "price_desc"],
    ),
    category_id: int = Query(None),
    price_min: int = Query(None),
    price_max: int = Query(None),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await get_proxy()
        data = await search_products(
            q=q,
            limit=limit,
            page=page,
            sort=sort,
            category_id=category_id,
            price_min=price_min,
            price_max=price_max,
            proxy=proxy,
        )
        return ApiResponse.ok({"query": q, "page": page, "limit": limit, **data})

    try:
        return ApiResponse.ok(await _())
    except HTTPException:
        raise
    except Exception as e:
        _raise_tiki_error(e)


@router.get("/products/sales", summary="Flash Sale Tiki")
@limiter.limit(endpoint_limit("tiki"))
async def get_flash_sales_endpoint(
    request: Request,
    response: Response,
    per_page: int = Query(20, ge=1, le=100),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await get_proxy()
        products = await get_flash_sale(per_page=per_page, proxy=proxy)
        return ApiResponse.ok({"total": len(products), "products": products})

    try:
        return ApiResponse.ok(await _())
    except HTTPException:
        raise
    except Exception as e:
        _raise_tiki_error(e)


@router.get("/products/top-choice", summary="Top Deals Tiki")
@limiter.limit(endpoint_limit("tiki"))
async def get_top_choice_endpoint(
    request: Request,
    response: Response,
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await get_proxy()
        return await get_top_choice(proxy=proxy)

    try:
        return ApiResponse.ok(await _())
    except HTTPException:
        raise
    except Exception as e:
        _raise_tiki_error(e)


@router.get("/products/maybe-you-like", summary="Tiki Recommend")
@limiter.limit(endpoint_limit("tiki"))
async def get_maybe_you_like_endpoint(
    request: Request,
    response: Response,
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await get_proxy()
        return await get_maybe_you_like(proxy=proxy)

    try:
        return ApiResponse.ok(await _())
    except HTTPException:
        raise
    except Exception as e:
        _raise_tiki_error(e)


@router.get("/products/{product_id}", summary="Tiki Product Detail")
@limiter.limit(endpoint_limit("tiki"))
async def get_product_detail_endpoint(
    request: Request,
    response: Response,
    product_id: int,
    spid: Optional[int] = Query(None, description="Seller product ID"),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await get_proxy()
        return await get_product_detail(product_id=product_id, spid=spid, proxy=proxy)

    try:
        return ApiResponse.ok(await _())
    except HTTPException:
        raise
    except Exception as e:
        _raise_tiki_error(e)


@router.get("/products/{product_id}/reviews", summary="Tiki Product Reviews")
@limiter.limit(endpoint_limit("tiki"))
async def get_reviews_endpoint(
    request: Request,
    response: Response,
    product_id: int,
    spid: Optional[int] = Query(None, description="Seller product ID"),
    seller_id: int = Query(1),
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=20),
    all_pages: bool = Query(False, description="Fetch all pages (max 5)"),
    max_pages: int = Query(5, ge=1, le=20),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await get_proxy()
        if all_pages:
            return await get_all_reviews(
                product_id=product_id,
                spid=spid,
                seller_id=seller_id,
                max_pages=max_pages,
                limit=limit,
                proxy=proxy,
            )
        return await get_reviews(
            product_id=product_id,
            spid=spid,
            seller_id=seller_id,
            page=page,
            limit=limit,
            proxy=proxy,
        )

    try:
        return ApiResponse.ok(await _())
    except HTTPException:
        raise
    except Exception as e:
        _raise_tiki_error(e)
