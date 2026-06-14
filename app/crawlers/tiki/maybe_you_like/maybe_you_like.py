from app.config.logger import Logger
from typing import Dict, List, Optional

from ..shared import create_tiki_client, create_tiki_session, build_cookies, build_headers
from .maybe_you_like_constants import MAYBE_YOU_LIKE_URL, MAYBE_YOU_LIKE_EXTRA_HEADERS

logger = Logger.get(__name__)

def extract_maybe_you_like_items(items: List[Dict]) -> List[Dict]:
    result = []
    for item in items:
        badges = item.get("badges_new") or item.get("badges_v3") or []
        badge_labels = [
            b.get("text") if isinstance(b.get("text"), str) else (b.get("text") or {}).get("value", "")
            for b in badges
            if b.get("text")
        ]
        quantity_sold = item.get("quantity_sold", {})

        result.append({
            "id":                 item.get("id"),
            "sku":                item.get("sku"),
            "master_product_sku": item.get("master_product_sku"),
            "name":               item.get("name"),
            "url":                f"https://tiki.vn/{item.get('url_path', '')}",
            "thumbnail":          item.get("thumbnail_url"),
            "price":              item.get("price"),
            "original_price":     item.get("original_price"),
            "discount":           item.get("discount"),
            "discount_rate":      item.get("discount_rate"),
            "rating":             item.get("rating_average"),
            "review_count":       item.get("review_count"),
            "brand_id":           item.get("brand_id"),
            "brand_name":         item.get("brand_name"),
            "sold_count": (
                quantity_sold.get("value")
                if isinstance(quantity_sold, dict)
                else quantity_sold
            ),
            "is_authentic":        item.get("is_authentic", False),
            "is_tikinow_delivery": item.get("is_tikinow_delivery", False),
            "is_nextday_delivery": item.get("is_nextday_delivery", False),
            "freeship_campaign":   item.get("freeship_campaign", ""),
            "badge_labels":        badge_labels,
            "category_ids":        item.get("category_ids", []),
            "impression_info":     item.get("impression_info"),
        })
    return result

async def get_maybe_you_like(
    rf: str = "rotate_by_ctr",
    proxy: Optional[str] = None,
) -> Dict:
    trackity_id, guest_token = await create_tiki_session(proxy=proxy)
    cookies = build_cookies(trackity_id, guest_token)
    headers = build_headers(guest_token, extra=MAYBE_YOU_LIKE_EXTRA_HEADERS)

    params: Dict = {
        "version":     2,
        "_rf":         rf,
        "trackity_id": trackity_id,
    }

    async with create_tiki_client(headers, cookies, proxy=proxy) as client:
        resp = await client.get(MAYBE_YOU_LIKE_URL, params=params)
        logger.info("🟢 [tiki/maybe_you_like] GET %s → %s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    raw_items = data.get("items", [])
    header    = data.get("header", {})

    return {
        "code":      data.get("code"),
        "title":     header.get("title") if header else data.get("title"),
        "more_link": header.get("more_link") if header else None,
        "total":     len(raw_items),
        "products":  extract_maybe_you_like_items(raw_items),
    }
