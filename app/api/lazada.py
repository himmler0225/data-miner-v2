from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from typing import Optional
from app.middleware import verify_api_key, limiter
from app.crawlers.lazada.recommendations import get_recommendations
from app.crawlers.lazada.reviews import get_reviews
from app.crawlers.lazada.related_products import get_related_products
from app.config.urls import proxy_manager
from app.config.logging_config import get_logger
from app.utils import retry_on_failure

router = APIRouter(dependencies=[Depends(verify_api_key)])
logger = get_logger(__name__)


@router.get("/products/recommendations", summary="Lazada Homepage Recommendations")
@limiter.limit("15/minute")
async def get_recommendations_endpoint(
    request: Request,
    response: Response,
    page_no: int = Query(0, ge=0),
    page_size: int = Query(50, ge=1, le=100),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        return await get_recommendations(page_no=page_no, page_size=page_size, proxy=proxy)

    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{item_id}/reviews", summary="Lazada Product Reviews")
@limiter.limit("15/minute")
async def get_reviews_endpoint(
    request: Request,
    response: Response,
    item_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    sort: str = Query("default", enum=["default", "helpful", "recent"]),
    filter_star: Optional[int] = Query(None, ge=1, le=5),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        return await get_reviews(
            item_id=item_id, page=page, page_size=page_size,
            sort=sort, filter_star=filter_star, proxy=proxy,
        )

    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/products/{item_id}/related", summary="Lazada Related Products")
@limiter.limit("15/minute")
async def get_related_products_endpoint(
    request: Request,
    response: Response,
    item_id: str,
    sku: str = Query(..., description="SKU string, e.g. 2112156313_VNAMZ-9934111791"),
    shop_id: str = Query(...),
    seller_id: str = Query(...),
    category_id: str = Query(...),
    brand_id: Optional[str] = Query(None),
    anonymous_id: Optional[str] = Query(None),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        proxy = await proxy_manager.get_proxy()
        return await get_related_products(
            item_id=item_id, sku=sku, shop_id=shop_id,
            seller_id=seller_id, category_id=category_id,
            brand_id=brand_id, anonymous_id=anonymous_id, proxy=proxy,
        )

    try:
        return await _()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
