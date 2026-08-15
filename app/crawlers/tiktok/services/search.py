"""
TikTok Search Service
"""

from typing import Any

from .base import TikTokBaseService


class SearchService(TikTokBaseService):
    """TikTok Search Service"""

    def search(
        self,
        keyword: str,
        count: int = 20,
        use_fresh_token: bool = True,
        cursor: int = 0,
        offset: int = 0,
        proxies: dict[str, str] = None,
    ) -> dict[str, Any]:
        """
        Search TikTok videos

        Args:
            keyword: Search keyword
            count: Number of results per page (max ~30)
            use_fresh_token: Whether to use fresh msToken from homepage
            cursor: Pagination cursor (0 for first page)
            offset: Pagination offset (0 for first page)
            proxies: Proxy configuration
        Returns:
            Dict with success, data, count, has_more, cursor
        """
        # Use macOS Chrome fingerprint ; matches the validated working browser request.
        # No search_source/from_page (not present in the working curl).
        params = self._get_mac_search_params()
        params.update(
            {
                "keyword": keyword,
                "count": str(count),
                "cursor": str(cursor),
                "offset": str(offset),
                "is_non_personalized_search": "0",
            }
        )

        data = self._make_request(
            "/api/search/general/full/",
            params,
            use_fresh_token=use_fresh_token,
            user_agent=self.MAC_SEARCH_UA,
            proxies=proxies,
        )

        if data and "data" in data:
            items = data["data"]

            # Limit results to requested count
            if len(items) > count:
                items = items[:count]

            return {
                "success": True,
                "data": items,
                "count": len(items),
                "has_more": data.get("has_more", False),
                "cursor": data.get("cursor", cursor),
                "log_pb": data.get("log_pb", {}),
            }

        return {"success": False, "data": [], "count": 0, "has_more": False}
