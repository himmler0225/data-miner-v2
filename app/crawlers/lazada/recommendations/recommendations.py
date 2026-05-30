import json
import logging
from typing import Dict, List, Optional

from ..shared import create_lazada_session, create_lazada_client, build_request_params
from .recommendations_constants import (
    RECOMMENDATIONS_API,
    RECOMMENDATIONS_VERSION,
    RECOMMENDATIONS_APP_ID,
)

logger = logging.getLogger(__name__)


def extract_recommendation_item(item: Dict) -> Dict:
    url = item.get("itemUrl", "")
    if url and url.startswith("//"):
        url = "https:" + url

    tag_icons = [t.get("tagType") for t in item.get("tagIcons", []) if t.get("tagType")]

    return {
        "item_id":       item.get("itemId"),
        "sku_id":        item.get("skuId"),
        "category_id":   item.get("categoryId") or item.get("catId"),
        "brand_id":      item.get("brandId"),
        "shop_id":       item.get("shopId"),
        "seller_id":     item.get("sellerId"),
        "name":          item.get("itemTitle"),
        "url":           url,
        "thumbnail":     item.get("itemImg"),
        "price":         item.get("itemDiscountPrice"),
        "discount_rate": item.get("itemDiscount"),
        "sales":         item.get("itemSales"),
        "rating":        item.get("itemRatingScore"),
        "review_count":  item.get("itemReviews"),
        "is_ad":         item.get("isAd") == "1",
        "tags":          tag_icons,
        "match_type":    item.get("matchType"),
    }


async def get_recommendations(
    page_no: int = 0,
    page_size: int = 50,
    proxy: Optional[str] = None,
) -> Dict:
    cookies = await create_lazada_session(proxy=proxy)

    data = {
        "appId": RECOMMENDATIONS_APP_ID,
        "params": json.dumps({
            "appId":        RECOMMENDATIONS_APP_ID,
            "isbackup":     True,
            "newTileEnable": True,
            "language":     "en",
            "region_id":    "VN",
            "platform":     "pc",
            "scene":        "homepage",
            "appVersion":   "7.48.0",
            "anonymous_id": cookies.get("cna", ""),
            "pageSize":     page_size,
            "userId":       0,
            "pageNo":       page_no,
        }, separators=(",", ":")),
    }

    url, params = build_request_params(
        cookies, RECOMMENDATIONS_API, RECOMMENDATIONS_VERSION, data
    )

    async with create_lazada_client(cookies, proxy=proxy) as client:
        resp = await client.get(url, params=params)
        logger.info("GET %s -> %s", resp.url, resp.status_code)
        resp.raise_for_status()
        result = resp.json()

    # Token expired — caller should retry with fresh session
    ret = result.get("ret", [])
    if any("TOKEN" in r for r in ret):
        raise RuntimeError(f"Lazada token expired: {ret}")

    raw_items: List[Dict] = []
    data_block = result.get("data") or {}
    print("[DEBUG reco] data keys:", list(data_block.keys()))
    print("[DEBUG reco] data sample:", str(data_block)[:500])
    result_list = data_block.get("result") or []
    print("[DEBUG reco] result_list len:", len(result_list))
    if result_list:
        try:
            raw_items = result_list[0]["resultValue"][RECOMMENDATIONS_APP_ID]["data"]
        except (KeyError, IndexError, TypeError) as e:
            logger.warning("Unexpected recommendations response structure: %s | error: %s", list(data_block.keys()), e)
    else:
        logger.warning("Recommendations: empty result_list. data keys: %s", list(data_block.keys()))

    return {
        "page_no":  page_no,
        "total":    len(raw_items),
        "products": [extract_recommendation_item(i) for i in raw_items],
    }
