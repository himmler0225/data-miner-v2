from typing import Any, Dict, List, Optional

import httpx

from app.config.logger import Logger

from ..shared import build_headers

logger = Logger.get(__name__)

SEARCH_URL = "https://papi.fptshop.com.vn/gw/v1/public/fulltext-search-service/search"


def extract_products(items: List[Dict]) -> List[Dict]:
    result: List[Dict] = []

    for item in items:
        price = (
            item.get("currentPrice")
            or item.get("price")
            or item.get("originalPrice")
            or 0
        )

        original_price = item.get("originalPrice") or price
        discount_percentage = item.get("discountPercentage", 0)

        brand = (item.get("brand") or {}).get("name")
        industry = (item.get("industry") or {}).get("name")

        image = item.get("image")
        thumbnail = image.get("src") if isinstance(image, dict) else image

        variants = item.get("variants") or []
        variant_info = [
            {
                "property": variant.get("propertyName"),
                "value": variant.get("value"),
                "display": variant.get("displayValue"),
            }
            for variant in variants
        ]

        promotions = item.get("promotions") or []
        promo_texts = [
            promo.get("content") for promo in promotions if promo.get("content")
        ]

        result.append(
            {
                "code": item.get("code"),
                "sku": item.get("sku"),
                "name": item.get("name") or item.get("displayName"),
                "short_name": item.get("displayName"),
                "slug": item.get("slug"),
                "url": f"https://fptshop.com.vn/{item.get('slug', '')}",
                "thumbnail": thumbnail,
                "price": price,
                "original_price": original_price,
                "discount_percentage": discount_percentage,
                "brand": brand,
                "category": industry,
                "key_selling_points": [
                    {
                        "title": point.get("title"),
                        "description": point.get("description"),
                        "icon": point.get("icon"),
                    }
                    for point in (item.get("keySellingPoints") or [])
                ],
                "variants": variant_info,
                "promotions": promo_texts,
                "status": (item.get("statusOnWeb") or {}).get("displayName"),
                "product_status": (item.get("productStatus") or {}).get("displayName"),
                "installment": item.get("installment"),
                "stock": item.get("qtyAvailable", 0),
            }
        )

    return result


async def search_products(
    q: str,
    skip: int = 0,
    limit: int = 24,
    pipeline: str = "Normal",
    category_slug: Optional[str] = None,
    sort_method: Optional[str] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    is_filter_all_category: bool = False,
    proxy: Optional[str] = None,
) -> Dict:
    filter_payload: Dict[str, Any] = {}

    if price_min is not None or price_max is not None:
        min_p = price_min or 0
        max_p = price_max or 999999999
        filter_payload["muc-gia"] = [f"{min_p}-{max_p}"]

    payload: Dict[str, Any] = {
        "skipCount": skip,
        "maxResultCount": limit,
        "keyword": q,
        "pipeline": pipeline,
        "isFilterAllCategory": is_filter_all_category,
    }

    if category_slug:
        payload["categorySlug"] = category_slug

    if sort_method:
        payload["sortMethod"] = sort_method

    if filter_payload:
        payload["filter"] = filter_payload

    async with httpx.AsyncClient(proxy=proxy, timeout=30) as client:
        resp = await client.post(SEARCH_URL, json=payload, headers=build_headers())
        logger.info("[fptshop/search] POST %s status=%s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    return {
        "total": data.get("totalCount", 0),
        "products": extract_products(data.get("items", [])),
    }
