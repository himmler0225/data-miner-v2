from typing import Dict, List, Optional, Any

import httpx

from app.config.logger import Logger

logger = Logger.get(__name__)

DETAIL_URL = "https://papi.fptshop.com.vn/gw/v1/public/fulltext-search-service/product-by-upcs"

HEADERS = {
    "accept": "application/json",
    "content-type": "application/json",
    "origin": "https://fptshop.com.vn",
    "referer": "https://fptshop.com.vn/",
    "order-channel": "1",
}


def extract_product_detail(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not items or not isinstance(items, list):
        return {}

    item = items[0] if isinstance(items[0], dict) else {}

    image = item.get("image")
    thumbnail = image.get("src") if isinstance(image, dict) else image

    brand = (item.get("brand") or {}).get("name") if isinstance(item.get("brand"), dict) else None
    industry = (item.get("industry") or {}).get("name") if isinstance(item.get("industry"), dict) else None

    return {
        "code": item.get("code"),
        "sku": item.get("sku"),
        "name": item.get("name") or item.get("displayName"),
        "display_name": item.get("displayName"),
        "slug": item.get("slug"),
        "url": f"https://fptshop.com.vn/{item.get('slug', '')}",
        "thumbnail": thumbnail,
        "price": item.get("currentPrice"),
        "original_price": item.get("originalPrice"),
        "discount_percentage": item.get("discountPercentage"),
        "brand": brand,
        "category": industry,
        "description": item.get("description"),
        "key_selling_points": item.get("keySellingPoints") or [],
        "variants": item.get("variants") or [],
        "promotions": [
            promo.get("content")
            for promo in (item.get("promotions") or [])
            if isinstance(promo, dict) and promo.get("content")
        ],
        "installment": item.get("installment"),
    }


async def get_product_by_upcs(
    upcs: List[str],
    is_excluded_product: bool = True,
    proxy: Optional[str] = None,
) -> Dict[str, Any]:
    payload = {
        "upcs": upcs,
        "isExcludedProduct": is_excluded_product,
    }

    async with httpx.AsyncClient(proxy=proxy, timeout=30) as client:
        resp = await client.post(
            DETAIL_URL,
            json=payload,
            headers=HEADERS,
        )
        logger.info("[fptshop/detail] POST %s status=%s", resp.url, resp.status_code)
        resp.raise_for_status()
        data: Any = resp.json()

    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("data") or []
    else:
        items = []

    return {
        "product": extract_product_detail(items),
    }
