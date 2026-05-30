import logging
from typing import Dict, List, Optional

from ..shared import create_lazada_session, create_lazada_client, build_post_params
from .reviews_constants import REVIEWS_API, REVIEWS_VERSION

logger = logging.getLogger(__name__)


def _extract_images(media_list: List) -> List[str]:
    return [m["coverUrl"] for m in media_list if m.get("coverUrl") and m.get("mediaType") == 1]


def _extract_content(content_list: List) -> str:
    parts = [c.get("content", "") for c in content_list if c.get("content")]
    return " ".join(parts).strip() or None


def extract_review(review: Dict) -> Dict:
    return {
        "review_id":     review.get("reviewId"),
        "rating":        review.get("rating"),
        "content":       _extract_content(review.get("reviewContentList") or []),
        "created_at":    review.get("reviewTime"),
        "sku_info":      review.get("skuInfo"),
        "images":        _extract_images(review.get("mediaList") or []),
        "like_count":    review.get("likeCount", 0),
        "reviewer_name": review.get("buyerName"),
        "reply":         review.get("sellerReply"),
    }


def extract_reviews_page(data: Dict) -> Dict:
    module  = data.get("module") or {}
    paging  = data.get("paging") or {}
    reviews = module.get("reviews") or []
    tags    = module.get("impressionTags") or []

    impression_tags = [
        {
            "tag_id":   t.get("tagId"),
            "name":     t.get("tagName"),
            "count":    t.get("count"),
            "polarity": t.get("polarity"),
        }
        for t in tags
    ]

    return {
        "paging":          paging,
        "impression_tags": impression_tags,
        "reviews":         [extract_review(r) for r in reviews],
    }


async def get_reviews(
    item_id: str,
    page: int = 1,
    page_size: int = 10,
    sort: str = "default",
    filter_star: Optional[int] = None,
    proxy: Optional[str] = None,
) -> Dict:
    cookies = await create_lazada_session(proxy=proxy)

    payload: Dict = {
        "itemId":   item_id,
        "pageNo":   page,
        "pageSize": page_size,
        "sort":     sort,
    }
    if filter_star is not None:
        payload["filterStar"] = str(filter_star)

    url, params, data_str = build_post_params(
        cookies, REVIEWS_API, REVIEWS_VERSION, payload
    )

    async with create_lazada_client(cookies, proxy=proxy) as client:
        resp = await client.post(
            url,
            params=params,
            content=f"data={data_str}".encode(),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
        logger.info("POST %s -> %s", resp.url, resp.status_code)
        resp.raise_for_status()
        result = resp.json()

    ret = result.get("ret", [])
    if any("TOKEN" in r for r in ret):
        raise RuntimeError(f"Lazada token expired: {ret}")

    return extract_reviews_page(result.get("data") or {})
