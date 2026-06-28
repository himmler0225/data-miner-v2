from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.api.rate_limit_config import endpoint_limit
from app.config.proxy import get_proxy
from app.crawlers.fpt_shop.detail import get_product_by_upcs
from app.crawlers.fpt_shop.reviews import get_reviews
from app.crawlers.fpt_shop.search import search_products
from app.crawlers.youtube.utils import retry_on_failure
from app.middleware import limiter, verify_api_key
from app.schemas.response import ApiResponse

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/products/search", summary="Search FPTShop Products")
@limiter.limit(endpoint_limit("fptshop"))
async def search_products_endpoint(
    request: Request,
    response: Response,
    q: str = Query(..., description="Keyword..."),
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=50),
    sort_method: Optional[
        Literal["noi-bat", "gia-thap-dan", "gia-cao-dan", "tra-gop-0"]
    ] = Query(None),
    price_range: Optional[Literal["under_2m", "2_5m", "5_10m", "over_10m"]] = Query(
        None
    ),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        skip = (page - 1) * limit
        proxy = await get_proxy()

        price_min = price_max = None
        if price_range:
            price_min, price_max = {
                "under_2m": (0, 2_000_000),
                "2_5m": (2_000_000, 5_000_000),
                "5_10m": (5_000_000, 10_000_000),
                "over_10m": (10_000_000, 999_999_999),
            }[price_range]

        data = await search_products(
            q=q,
            skip=skip,
            limit=limit,
            sort_method=sort_method,
            price_min=price_min,
            price_max=price_max,
            proxy=proxy,
        )
        return {
            "query": q,
            "page": page,
            "limit": limit,
            "filters": {
                "sort": sort_method,
                "price_range": price_range,
            },
            **data,
        }

    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/detail/{upc}", summary="Get Product Detail (FPTShop)")
@limiter.limit(endpoint_limit("fptshop"))
async def get_product_detail_endpoint(
    request: Request,
    response: Response,
    upc: str,
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await get_proxy()
        data = await get_product_by_upcs(
            upcs=[upc],
            is_excluded_product=True,
            proxy=proxy,
        )
        return {"upc": upc, **data}

    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{product_id}/reviews", summary="Get Product Reviews (FPTShop)")
@limiter.limit(endpoint_limit("fptshop"))
async def get_reviews_endpoint(
    request: Request,
    response: Response,
    product_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(6, ge=1, le=20),
    sort_method: int = Query(1, description="1 = newest, 2 = oldest (FPT style)"),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        skip = (page - 1) * limit
        proxy = await get_proxy()
        data = await get_reviews(
            product_id=product_id,
            skip=skip,
            limit=limit,
            sort_method=sort_method,
            proxy=proxy,
        )
        return {
            "product_id": product_id,
            "page": page,
            "limit": limit,
            **data,
        }

    try:
        return ApiResponse.ok(await _())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
