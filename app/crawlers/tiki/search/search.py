from typing import Dict, List, Optional

from app.config.logger import Logger

from ..shared import (build_cookies, build_headers, create_tiki_client,
                      create_tiki_session)
from .search_constants import SEARCH_EXTRA_HEADERS, SEARCH_URL

logger = Logger.get(__name__)


def extract_products(items: List[Dict]) -> List[Dict]:
    result = []
    for item in items:
        badges = []
        variant_info = []

        for badge in item.get("badges_new", []):
            code = badge.get("code")
            if code:
                badges.append(code)
            if badge.get("code") == "variant_count":
                variant_info = [
                    x.get("value") for x in badge.get("arr_text", []) if x.get("value")
                ]
                break

        quantity_sold = item.get("quantity_sold")
        if isinstance(quantity_sold, dict):
            sold_count = quantity_sold.get("value", 0)
        else:
            sold_count = quantity_sold or 0

        result.append(
            {
                "id": item.get("id"),
                "sku": item.get("sku"),
                "name": item.get("name"),
                "short_name": item.get("short_name") or item.get("name"),
                "url": f"https://tiki.vn/{item.get('url_path', '')}",
                "thumbnail": item.get("thumbnail_url"),
                "price": item.get("price"),
                "original_price": item.get("original_price"),
                "discount_rate": item.get("discount_rate"),
                "rating": item.get("rating_average"),
                "review_count": item.get("review_count"),
                "sold_count": sold_count,
                "brand": item.get("brand_name"),
                "seller": item.get("seller_name"),
                "badges": badges,
                "is_authentic": (
                    item.get("is_authentic") == 1 or "authentic_brand" in badges
                ),
                "is_tikinow": item.get("is_tikinow_delivery", False),
                "category": item.get("primary_category_name"),
                "variant": variant_info,
                "seller_product_id": item.get("seller_product_id"),
            }
        )
    return result


async def search_products(
    q: str,
    limit: int = 40,
    page: Optional[int] = None,
    sort: Optional[str] = None,
    category_id: Optional[int] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    include: str = "advertisement",
    aggregations: int = 2,
    proxy: Optional[str] = None,
) -> Dict:
    trackity_id, guest_token = await create_tiki_session(proxy=proxy)
    cookies = build_cookies(trackity_id, guest_token)
    headers = build_headers(guest_token, extra=SEARCH_EXTRA_HEADERS)

    params: Dict = {
        "q": q,
        "limit": limit,
        "include": include,
        "aggregations": aggregations,
        "trackity_id": trackity_id,
    }
    if page is not None:
        params["page"] = page
    if sort:
        params["sort"] = sort
    if category_id:
        params["category"] = category_id
    if price_min is not None:
        params["price_min"] = price_min
    if price_max is not None:
        params["price_max"] = price_max

    async with create_tiki_client(headers, cookies, proxy=proxy) as client:
        resp = await client.get(SEARCH_URL, params=params)
        logger.info("🟢 [tiki/search] GET %s → %s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    return {
        "paging": data.get("paging", {}),
        "products": extract_products(data.get("data", [])),
    }
