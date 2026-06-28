from typing import Dict, List, Optional

import httpx

from app.config.logger import Logger

from ..shared import build_headers

logger = Logger.get(__name__)

REVIEW_URL = "https://papi.fptshop.com.vn/gw/v1/public/bff-before-order/comment/list"


def extract_reviews(data: Dict) -> List[Dict]:
    items = data.get("data", {}).get("items", []) or []
    result = []

    for review in items:
        user = review.get("createdBy") or {}
        result.append(
            {
                "id": review.get("id"),
                "content": review.get("content"),
                "rating": review.get("rating"),
                "created_at": review.get("createdAt"),
                "user": {
                    "id": user.get("id"),
                    "name": user.get("fullName") or user.get("name"),
                    "avatar": user.get("avatar"),
                },
                "images": review.get("images") or [],
                "likes": review.get("likeCount", 0),
                "replies": review.get("replyCount", 0),
            }
        )

    return result


async def get_reviews(
    product_id: str,
    skip: int = 0,
    limit: int = 6,
    sort_method: int = 1,
    proxy: Optional[str] = None,
) -> Dict:
    payload = {
        "content": {
            "id": product_id,
            "type": "PRODUCT",
        },
        "state": ["ACTIVE"],
        "skipCount": skip,
        "maxResultCount": limit,
        "sortMethod": sort_method,
    }

    async with httpx.AsyncClient(proxy=proxy, timeout=30) as client:
        resp = await client.post(REVIEW_URL, json=payload, headers=build_headers())
        logger.info("[fptshop/reviews] POST %s status=%s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    return {
        "total": data.get("data", {}).get("totalCount", 0),
        "reviews": extract_reviews(data),
    }
