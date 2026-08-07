from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.errors import api_ok
from app.api.rate_limit_config import endpoint_limit
from app.crawlers.google import format_search, search
from app.crawlers.youtube.utils import retry_on_failure
from app.middleware.auth_middleware import verify_api_key
from app.middleware.rate_limit import limiter

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.get("/search", summary="Web Search (Tavily)")
@limiter.limit(endpoint_limit("search"))
async def search_web(
    request: Request,
    response: Response,
    q: str = Query(...),
    num_results: int = Query(10, ge=1, le=20),
):
    @retry_on_failure(max_retries=3, delay=1)
    async def _():
        raw = await search(q, max_results=num_results)
        return format_search(raw)

    return await api_ok(_())
