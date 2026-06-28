"""
TikTok Trending Service
"""

from typing import Any, Dict

from .base import TikTokBaseService


class TrendingService(TikTokBaseService):
    """TikTok Trending Service"""

    def get_trending(
        self, count: int = 20, proxies: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        Get trending videos (fake msToken works)

        Args:
            count: Number of videos
            proxies: Proxy configuration

        Returns:
            Dict with success, data, count
        """
        params = self._get_mobile_params()
        params.update(
            {
                "count": str(count),
                "cursor": "0",
            }
        )

        data = self._make_request(
            "/api/recommend/item_list/",
            params,
            use_fresh_token=False,  # Fake token works for trending
            proxies=proxies,
        )

        if data and "itemList" in data:
            items = data["itemList"]

            # Limit results to requested count
            if len(items) > count:
                items = items[:count]

            return {
                "success": True,
                "data": items,
                "count": len(items),
                "has_more": data.get("hasMore", False),
            }

        return {"success": False, "data": [], "count": 0}
