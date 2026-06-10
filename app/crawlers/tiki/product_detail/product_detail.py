from app.config.logger import Logger
from typing import Dict, List, Optional

from ..shared import create_tiki_client, create_tiki_session, build_cookies, build_headers
from .product_detail_constants import PRODUCT_DETAIL_URL, PRODUCT_DETAIL_EXTRA_HEADERS

logger = Logger.get(__name__)


def extract_product_detail(data: Dict) -> Dict:
    specifications = []
    for spec_group in data.get("specifications", []):
        group_name = spec_group.get("name", "")
        attrs = [
            {"name": a.get("name"), "value": a.get("value")}
            for a in spec_group.get("attributes", [])
        ]
        specifications.append({"group": group_name, "attributes": attrs})

    inventory       = data.get("inventory", {})
    current_seller  = data.get("current_seller", {})
    brand           = data.get("brand", {})

    images = [
        img.get("base_url")
        for img in data.get("images", [])
        if img.get("base_url")
    ]

    badges = [b.get("code") for b in data.get("badges", []) if b.get("code")]

    return {
        "id":               data.get("id"),
        "sku":              data.get("sku"),
        "master_id":        data.get("master_id"),
        "spid":             data.get("spid"),
        "name":             data.get("name"),
        "url":              f"https://tiki.vn/{data.get('url_path', '')}",
        "thumbnail":        data.get("thumbnail_url"),
        "images":           images,
        "short_description": data.get("short_description"),
        "description":      data.get("description"),
        "price":            data.get("price"),
        "original_price":   data.get("original_price"),
        "discount":         data.get("discount"),
        "discount_rate":    data.get("discount_rate"),
        "rating":           data.get("rating_average"),
        "review_count":     data.get("review_count"),
        "brand": {
            "id":   brand.get("id"),
            "name": brand.get("name"),
            "slug": brand.get("slug"),
        },
        "seller": {
            "id":   current_seller.get("id"),
            "name": current_seller.get("name"),
            "url":  current_seller.get("store_url"),
            "logo": current_seller.get("logo"),
        },
        "stock_status":  inventory.get("fulfillment_type"),
        "quantity":      inventory.get("quantity"),
        "is_authentic":  "authentic" in badges,
        "is_freeship":   data.get("freeship_campaign") is not None,
        "badges":        badges,
        "specifications": specifications,
        "categories": [
            {"id": c.get("id"), "name": c.get("name")}
            for c in data.get("breadcrumbs", [])
        ],
    }


async def get_product_detail(
    product_id: int,
    spid: Optional[int] = None,
    platform: str = "web",
    version: int = 3,
    proxy: Optional[str] = None,
) -> Dict:
    trackity_id, guest_token = await create_tiki_session(proxy=proxy)
    cookies = build_cookies(trackity_id, guest_token)
    headers = build_headers(guest_token, extra=PRODUCT_DETAIL_EXTRA_HEADERS)

    url = PRODUCT_DETAIL_URL.format(product_id=product_id)
    params: Dict = {
        "platform":    platform,
        "version":     version,
        "trackity_id": trackity_id,
    }
    if spid is not None:
        params["spid"] = spid

    async with create_tiki_client(headers, cookies, proxy=proxy) as client:
        resp = await client.get(url, params=params)
        logger.info("GET %s -> %s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    return extract_product_detail(data)
