import httpx

import app.config.settings as settings
from app.config.http import HTTP_MAX_CONNECTIONS, HTTP_MAX_KEEPALIVE
from app.config.logger import Logger
from app.exceptions import TavilyError

logger = Logger.get(__name__)

_TAVILY_BASE_URL = "https://api.tavily.com"
_TAVILY_TIMEOUT = 15

_http: httpx.AsyncClient | None = None


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(
            base_url=_TAVILY_BASE_URL,
            timeout=_TAVILY_TIMEOUT,
            limits=httpx.Limits(
                max_connections=HTTP_MAX_CONNECTIONS,
                max_keepalive_connections=HTTP_MAX_KEEPALIVE,
            ),
        )
    return _http


async def search(query: str, *, max_results: int = 10, search_depth: str = "basic") -> dict:
    """Call the Tavily Search API and return the raw JSON response.

    Args:
        query: Search query string.
        max_results: Maximum number of results Tavily should return.
        search_depth: Tavily search depth, e.g. "basic" or "advanced".

    Returns:
        The raw decoded JSON response from Tavily, containing a
        ``results`` list of objects with ``url``/``title``/``content``/``score``.

    Raises:
        TavilyError: If the API key is not configured, or the request
            fails (HTTP error status, timeout, or network error).
    """
    if not settings.TAVILY_API_KEY:
        raise TavilyError("TAVILY_API_KEY chưa cấu hình")
    try:
        response = await _client().post(
            "/search",
            headers={"Authorization": f"Bearer {settings.TAVILY_API_KEY}"},
            json={"query": query, "max_results": max_results, "search_depth": search_depth},
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        raise TavilyError(f"Tavily {e.response.status_code}: {e.response.text[:200]}") from e
    except httpx.TimeoutException as e:
        raise TavilyError("Tavily timeout") from e
    except httpx.NetworkError as e:
        raise TavilyError(f"Tavily network error: {e}") from e


def format_search(raw: dict) -> dict:
    """Normalize a raw Tavily search response into a compact shape for callers (ai-layer).

    Args:
        raw: Raw JSON response as returned by ``search()``.

    Returns:
        dict with ``query``, ``answer``, ``count``, ``results`` (list of
        ``title``/``url``/``content``/``score``), and ``source`` set to "tavily".
    """
    results = raw.get("results") or []
    return {
        "query": raw.get("query", ""),
        "answer": raw.get("answer"),
        "count": len(results),
        "results": [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "content": r.get("content", ""),
                "score": r.get("score"),
            }
            for r in results
        ],
        "source": "tavily",
    }
