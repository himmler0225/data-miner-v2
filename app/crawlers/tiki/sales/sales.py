from app.config.logger import Logger
from typing import Dict, List, Optional

from ..shared import create_tiki_client, create_tiki_session, build_cookies, build_headers
from .sales_constants import FLASH_SALE_URL, FLASH_SALE_EXTRA_HEADERS

logger = Logger.get(__name__)

def extract_flash_sale_items(items: List[Dict]) -> List[Dict]:
    result = []
    for item in items:
        product = item.get("product", {})
        result.append({
            "deal_id":             item.get("deal_id"),
            "id":                  product.get("id"),
            "master_id":           product.get("master_id"),
            "seller_product_id":   product.get("seller_product_id"),
            "name":                product.get("name"),
            "short_name":          product.get("short_name") or product.get("name"),
            "url": (
                f"https://tiki.vn/{product.get('url_path')}"
                if product.get("url_path") else None
            ),
            "thumbnail":           product.get("thumbnail_url"),
            "price":               product.get("price"),
            "original_price":      product.get("original_price"),
            "discount":            product.get("discount"),
            "discount_rate":       product.get("discount_rate"),
            "rating":              product.get("rating_average"),
            "review_count":        product.get("review_count"),
            "special_price":       item.get("special_price"),
            "flash_sale_discount": item.get("discount_percent"),
            "sold_count":          item.get("progress", {}).get("qty_ordered"),
            "remain_count":        item.get("progress", {}).get("qty_remain"),
            "brand":               product.get("brand_name"),
        })
    return result

async def get_flash_sale(
    per_page: int = 20,
    rf: str = "rotate_by_ctr",
    clear: int = 2,
    proxy: Optional[str] = None,
) -> List[Dict]:
    trackity_id, guest_token = await create_tiki_session(proxy=proxy)
    cookies = build_cookies(trackity_id, guest_token)
    headers = build_headers(guest_token, extra=FLASH_SALE_EXTRA_HEADERS)

    params = {
        "per_page":    per_page,
        "_rf":         rf,
        "clear":       clear,
        "trackity_id": trackity_id,
    }

    async with create_tiki_client(headers, cookies, proxy=proxy) as client:
        resp = await client.get(FLASH_SALE_URL, params=params)
        logger.info("🟢 [tiki/sales] GET %s → %s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    raw_items = data.get("data", [])
    if not isinstance(raw_items, list):
        raw_items = []

    return extract_flash_sale_items(raw_items)
