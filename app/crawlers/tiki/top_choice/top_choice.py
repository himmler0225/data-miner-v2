import logging
from typing import Dict, List, Optional

from ..shared import create_tiki_client, create_tiki_session, build_cookies, build_headers
from .top_choice_constants import TOP_CHOICE_URL, TOP_CHOICE_EXTRA_HEADERS

logger = logging.getLogger(__name__)


def extract_top_choice_items(items: List[Dict]) -> List[Dict]:
    result = []
    for item in items:
        badges_new = item.get("badges_new") or item.get("badges_v3") or []
        badge_labels = [
            b.get("text") if isinstance(b.get("text"), str) else (b.get("text") or {}).get("value", "")
            for b in badges_new
            if b.get("text")
        ]
        quantity_sold = item.get("quantity_sold", {})

        result.append({
            "id":                    item.get("id"),
            "sku":                   item.get("sku"),
            "seller_product_id":     item.get("seller_product_id"),
            "seller_product_sku":    item.get("seller_product_sku"),
            "master_product_sku":    item.get("master_product_sku"),
            "productset_id":         item.get("productset_id"),
            "name":                  item.get("name"),
            "url_key":               item.get("url_key"),
            "url":                   f"https://tiki.vn/{item.get('url_path', '')}",
            "thumbnail":             item.get("thumbnail_url"),
            "price":                 item.get("price"),
            "original_price":        item.get("original_price"),
            "discount":              item.get("discount"),
            "discount_rate":         item.get("discount_rate"),
            "rating":                item.get("rating_average"),
            "review_count":          item.get("review_count"),
            "brand_id":              item.get("brand_id"),
            "brand_name":            item.get("brand_name"),
            "seller_id":             item.get("seller_id"),
            "seller_name":           item.get("seller_name"),
            "primary_category_name": item.get("primary_category_name"),
            "primary_category_path": item.get("primary_category_path"),
            "origin":                item.get("origin"),
            "availability":          item.get("availability"),
            "sold_count": (
                quantity_sold.get("value")
                if isinstance(quantity_sold, dict)
                else quantity_sold
            ),
            "is_authentic":            bool(item.get("is_authentic", 0)),
            "tiki_verified":           bool(item.get("tiki_verified", 0)),
            "tiki_hero":               bool(item.get("tiki_hero", 0)),
            "is_from_official_store":  item.get("is_from_official_store", False),
            "is_gift_available":       item.get("isGiftAvailable", False),
            "is_tikinow_delivery":     item.get("is_tikinow_delivery", False),
            "is_nextday_delivery":     item.get("is_nextday_delivery", False),
            "is_top_brand":            item.get("is_top_brand", False),
            "freeship_campaign":       item.get("freeship_campaign", ""),
            "applied_vip_price_badge": item.get("applied_vip_price_badge", ""),
            "badge_labels":            badge_labels,
            "category_ids":            item.get("category_ids", []),
            "impression_info":         item.get("impression_info"),
        })
    return result


async def get_top_choice(
    version: int = 2,
    v: int = 2,
    clear: int = 1,
    proxy: Optional[str] = None,
) -> Dict:
    trackity_id, guest_token = await create_tiki_session(proxy=proxy)
    cookies = build_cookies(trackity_id, guest_token)
    headers = build_headers(guest_token, extra=TOP_CHOICE_EXTRA_HEADERS)

    params: Dict = {
        "version":     version,
        "_v":          v,
        "clear":       clear,
        "trackity_id": trackity_id,
    }

    async with create_tiki_client(headers, cookies, proxy=proxy) as client:
        resp = await client.get(TOP_CHOICE_URL, params=params)
        logger.info("GET %s -> %s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    raw_items = data.get("items", [])
    header    = data.get("header", {})

    return {
        "code":      data.get("code"),
        "title":     header.get("title") if header else data.get("title"),
        "more_link": header.get("more_link") if header else None,
        "total":     len(raw_items),
        "products":  extract_top_choice_items(raw_items),
    }
