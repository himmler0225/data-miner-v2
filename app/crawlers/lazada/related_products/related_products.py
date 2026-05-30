import json
import logging
from typing import Dict, List, Optional

from ..shared import create_lazada_session, create_lazada_client, build_request_params
from ..recommendations.recommendations import extract_recommendation_item
from ..recommendations.recommendations_constants import (
    RECOMMENDATIONS_API,
    RECOMMENDATIONS_VERSION,
    RECOMMENDATIONS_APP_ID,
)

logger = logging.getLogger(__name__)


async def get_related_products(
    item_id: str,
    sku: str,
    shop_id: str,
    seller_id: str,
    category_id: str,
    brand_id: Optional[str] = None,
    anonymous_id: Optional[str] = None,
    proxy: Optional[str] = None,
) -> Dict:
    cookies = await create_lazada_session(proxy=proxy)

    inner_params: Dict = {
        "appId":        RECOMMENDATIONS_APP_ID,
        "language":     "en",
        "region_id":    "VN",
        "platform":     "pc",
        "scene":        "pdp_jfy",
        "appVersion":   "7.48.0",
        "pageSize":     20,
        "pageNo":       0,
        "itemId":       item_id,
        "skuId":        sku,
        "shopId":       shop_id,
        "sellerId":     seller_id,
        "categoryId":   category_id,
        "isbackup":     True,
        "newTileEnable": True,
        "userId":       0,
    }
    if brand_id:
        inner_params["brandId"] = brand_id
    if anonymous_id:
        inner_params["anonymous_id"] = anonymous_id

    data = {
        "appId":  RECOMMENDATIONS_APP_ID,
        "params": json.dumps(inner_params, separators=(",", ":")),
    }

    url, params = build_request_params(
        cookies, RECOMMENDATIONS_API, RECOMMENDATIONS_VERSION, data
    )

    async with create_lazada_client(cookies, proxy=proxy) as client:
        resp = await client.get(url, params=params)
        logger.info("GET %s -> %s", resp.url, resp.status_code)
        resp.raise_for_status()
        result = resp.json()

    ret = result.get("ret", [])
    if any("TOKEN" in r for r in ret):
        raise RuntimeError(f"Lazada token expired: {ret}")

    raw_items: List[Dict] = []
    data_block = result.get("data") or {}
    result_val = data_block.get("result") or []
    print("[DEBUG related] scene=pdp_jfy result len:", len(result_val))
    if result_val:
        try:
            raw_items = result_val[0]["resultValue"][RECOMMENDATIONS_APP_ID]["data"]
            print("[DEBUG related] got items:", len(raw_items))
        except (KeyError, IndexError, TypeError) as e:
            print("[DEBUG related] parse error:", e, "result[0] keys:", list(result_val[0].keys()) if isinstance(result_val[0], dict) else type(result_val[0]))

    return {
        "item_id":  item_id,
        "total":    len(raw_items),
        "products": [extract_recommendation_item(i) for i in raw_items],
    }
