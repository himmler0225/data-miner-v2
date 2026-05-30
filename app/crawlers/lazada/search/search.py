import logging
from typing import Dict, List, Optional

import httpx

from ..shared.client_constants import BASE_UA, SEC_CH_UA
from .search_constants import SEARCH_URL, SEARCH_SORT_OPTIONS

logger = logging.getLogger(__name__)

_SEARCH_HEADERS = {
    "user-agent":         BASE_UA,
    "accept":             "application/json, text/plain, */*",
    "accept-language":    "en-US,en;q=0.9,vi;q=0.8",
    "referer":            "https://www.lazada.vn/",
    "sec-ch-ua":          SEC_CH_UA,
    "sec-ch-ua-mobile":   "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest":     "empty",
    "sec-fetch-mode":     "cors",
    "sec-fetch-site":     "same-origin",
}


def extract_search_item(item: Dict) -> Dict:
    price     = item.get("price", "")
    org_price = item.get("originalPrice", "")
    url       = item.get("itemUrl", "")
    if url and not url.startswith("http"):
        url = "https:" + url

    return {
        "item_id":        item.get("itemId"),
        "sku_id":         item.get("skuId"),
        "name":           item.get("name"),
        "url":            url,
        "thumbnail":      item.get("image"),
        "price":          price,
        "original_price": org_price if org_price != price else None,
        "discount":       item.get("discount"),
        "rating":         item.get("ratingScore"),
        "review_count":   item.get("review"),
        "location":       item.get("location"),
        "brand_name":     item.get("brandName"),
        "seller_name":    item.get("sellerName"),
        "shop_id":        item.get("shopId"),
        "is_freeship":    item.get("freeShipping", False),
        "is_cod":         item.get("cod", False),
        "is_lazmall":     item.get("lazMall", False),
        "is_ad":          item.get("isAd", False),
        "badges":         item.get("badgeList", []),
    }


async def search_products(
    q: str,
    page: int = 1,
    sort: str = "relevance",
    category_id: Optional[str] = None,
    price_min: Optional[int] = None,
    price_max: Optional[int] = None,
    proxy: Optional[str] = None,
) -> Dict:
    sort_key = SEARCH_SORT_OPTIONS.get(sort, "")
    params: Dict = {
        "ajax":             "true",
        "isFirstRequest":   "true",
        "q":                q,
        "page":             page,
    }
    if sort_key:
        params["sort"] = sort_key
    if category_id:
        params["catalog_redirect_tag"] = "true"
    if price_min is not None:
        params["price"] = f"{price_min}-{price_max or ''}"

    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(
        headers=_SEARCH_HEADERS,
        follow_redirects=True,
        timeout=20,
        transport=transport,
    ) as client:
        resp = await client.get(SEARCH_URL, params=params)
        logger.info("GET %s -> %s", resp.url, resp.status_code)

        content_type = resp.headers.get("content-type", "")
        if "text/html" in content_type:
            raise RuntimeError(
                "Lazada search trả về HTML thay vì JSON — anti-bot block. "
                "Endpoint này yêu cầu session cookies từ browser thật."
            )

        resp.raise_for_status()
        data = resp.json()

    inner  = (data.get("data") or {})
    mods   = inner.get("mods") or {}
    items  = mods.get("listItems", [])
    paging = mods.get("paging") or {}

    return {
        "query":    q,
        "page":     page,
        "total":    paging.get("totalResults"),
        "pages":    paging.get("pageCount"),
        "products": [extract_search_item(i) for i in items],
    }
