from app.config.logger import Logger
from typing import Dict, List, Optional

from ..shared import create_tiki_client, create_tiki_session, build_cookies, build_headers
from .reviews_constants import REVIEWS_URL, REVIEWS_EXTRA_HEADERS

logger = Logger.get(__name__)


def _extract_comment(comment: Dict) -> Dict:
    return {
        "id":         comment.get("id"),
        "content":    comment.get("content"),
        "created_at": comment.get("created_at"),
        "customer": {
            "id":     comment.get("customer_id"),
            "name":   comment.get("full_name"),
            "avatar": comment.get("avatar_url"),
        },
    }


def extract_review(review: Dict) -> Dict:
    images = [
        img.get("full_path")
        for img in review.get("images", [])
        if img.get("full_path")
    ]

    # API returns comments as a direct list, not {"data": [...]}
    raw_comments = review.get("comments", [])
    if isinstance(raw_comments, dict):
        raw_comments = raw_comments.get("data", [])
    comments = [_extract_comment(c) for c in raw_comments]

    created_by      = review.get("created_by", {})
    contribute_info = created_by.get("contribute_info", {})
    summary         = contribute_info.get("summary", {})

    return {
        "id":         review.get("id"),
        "product_id": review.get("product_id"),
        "spid":       review.get("spid"),
        "title":      review.get("title"),
        "content":    review.get("content"),
        "stars":      review.get("rating"),
        "images":     images,
        "created_at": review.get("created_at"),
        "attributes": review.get("attributes", []),
        "customer": {
            "id":           review.get("customer_id"),
            "name":         created_by.get("name") or review.get("full_name"),
            "avatar":       created_by.get("avatar_url"),
            "joined_time":  summary.get("joined_time"),
            "total_review": summary.get("total_review"),
            "total_thank":  summary.get("total_thank"),
            "purchased":    created_by.get("purchased", False),
            "purchased_at": created_by.get("purchased_at"),
        },
        "thank_count":     review.get("thank_count", 0),
        "comment_count":   review.get("comment_count", 0),
        "comments":        comments,
        "timeline":        review.get("timeline"),
        "attribute_votes": review.get("vote_attributes"),
    }


def extract_reviews_page(data: Dict) -> Dict:
    rating_summary = data.get("rating_summary") or {}
    return {
        "paging": data.get("paging", {}),
        "rating_summary": {
            "average": rating_summary.get("rating_avg") or rating_summary.get("average"),
            "count":   rating_summary.get("review_count") or rating_summary.get("count"),
            "star_5":  rating_summary.get("rating_count_5") or rating_summary.get("5", 0),
            "star_4":  rating_summary.get("rating_count_4") or rating_summary.get("4", 0),
            "star_3":  rating_summary.get("rating_count_3") or rating_summary.get("3", 0),
            "star_2":  rating_summary.get("rating_count_2") or rating_summary.get("2", 0),
            "star_1":  rating_summary.get("rating_count_1") or rating_summary.get("1", 0),
        },
        "reviews": [extract_review(r) for r in data.get("data", [])],
    }


async def get_reviews(
    product_id: int,
    spid: Optional[int] = None,
    seller_id: int = 1,
    page: int = 1,
    limit: int = 5,
    sort: str = "score|desc,id|desc,stars|all",
    include: str = "comments,contribute_info,attribute_vote_summary",
    proxy: Optional[str] = None,
) -> Dict:
    trackity_id, guest_token = await create_tiki_session(proxy=proxy)
    cookies = build_cookies(trackity_id, guest_token)
    headers = build_headers(guest_token, extra=REVIEWS_EXTRA_HEADERS)

    params: Dict = {
        "product_id": product_id,
        "seller_id":  seller_id,
        "page":       page,
        "limit":      limit,
        "sort":       sort,
        "include":    include,
    }
    if spid is not None:
        params["spid"] = spid

    async with create_tiki_client(headers, cookies, proxy=proxy) as client:
        resp = await client.get(REVIEWS_URL, params=params)
        logger.info("GET %s -> %s", resp.url, resp.status_code)
        resp.raise_for_status()
        data = resp.json()

    return extract_reviews_page(data)


async def get_all_reviews(
    product_id: int,
    spid: Optional[int] = None,
    seller_id: int = 1,
    max_pages: int = 5,
    limit: int = 20,
    sort: str = "score|desc,id|desc,stars|all",
    proxy: Optional[str] = None,
) -> Dict:
    all_reviews: List[Dict] = []
    rating_summary: Dict = {}

    for page in range(1, max_pages + 1):
        result = await get_reviews(
            product_id=product_id, spid=spid, seller_id=seller_id,
            page=page, limit=limit, sort=sort, proxy=proxy,
        )

        if page == 1:
            rating_summary = result.get("rating_summary", {})

        reviews = result.get("reviews", [])
        all_reviews.extend(reviews)

        paging = result.get("paging", {})
        total  = paging.get("total", 0)
        if len(all_reviews) >= total or not reviews:
            break

    return {
        "total_collected": len(all_reviews),
        "rating_summary":  rating_summary,
        "reviews":         all_reviews,
    }
