import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse

from ..shared import create_lazada_session, create_lazada_client, build_post_params
from .product_detail_constants import PRODUCT_DETAIL_API, PRODUCT_DETAIL_VERSION
from ..shared.client_constants import BASE_UA

logger = logging.getLogger(__name__)


def _parse_uri(item_id: str, sku_id: Optional[str]) -> str:
    if sku_id:
        return f"pdp-i{item_id}-s{sku_id}"
    return f"pdp-i{item_id}"


def extract_product_detail(data: Dict) -> Dict:
    result = data.get("result", {})
    if not result:
        return data

    product = result.get("product", {})
    price   = result.get("price", {})
    seller  = result.get("seller", {})
    rating  = result.get("review", {})

    attributes = [
        {"name": a.get("name"), "value": a.get("value")}
        for a in product.get("attributes", [])
    ]

    images = [
        img.get("image", "")
        for img in product.get("images", [])
        if img.get("image")
    ]

    return {
        "item_id":        product.get("itemId"),
        "sku_id":         product.get("skuId"),
        "name":           product.get("name"),
        "brand":          product.get("brandName"),
        "description":    product.get("description"),
        "images":         images,
        "price":          price.get("salePrice"),
        "original_price": price.get("originalPrice"),
        "discount_rate":  price.get("discount"),
        "currency":       price.get("currency", "VND"),
        "rating":         rating.get("rating"),
        "review_count":   rating.get("reviewCount"),
        "seller": {
            "id":   seller.get("sellerId"),
            "name": seller.get("name"),
            "url":  seller.get("url"),
        },
        "attributes":     attributes,
        "category_path":  product.get("categoryPath"),
    }


async def get_product_detail(
    item_id: str,
    sku_id: Optional[str] = None,
    proxy: Optional[str] = None,
) -> Dict:
    cookies = await create_lazada_session(proxy=proxy)

    uri      = _parse_uri(item_id, sku_id)
    path_url = f"https://www.lazada.vn/products/{uri}.html"

    payload = {
        "deviceType":    "pc",
        "path":          path_url,
        "uri":           uri,
        "headerParams":  json.dumps({"user-agent": BASE_UA}),
        "cookieParams":  json.dumps(cookies),
        "requestParams": "{}",
    }

    url, params, data_str = build_post_params(
        cookies, PRODUCT_DETAIL_API, PRODUCT_DETAIL_VERSION, payload
    )

    post_headers = {"content-type": "application/x-www-form-urlencoded"}

    async with create_lazada_client(cookies, proxy=proxy) as client:
        resp = await client.post(
            url,
            params=params,
            content=f"data={data_str}".encode(),
            headers=post_headers,
        )
        logger.info("POST %s -> %s", resp.url, resp.status_code)
        resp.raise_for_status()
        result = resp.json()
        print("[DEBUG product_detail] ret:", result.get("ret"))
        print("[DEBUG product_detail] data keys:", list((result.get("data") or {}).keys()))

    ret = result.get("ret", [])
    if any("TOKEN" in r for r in ret):
        raise RuntimeError(f"Lazada token expired: {ret}")

    return extract_product_detail(result.get("data", {}))
