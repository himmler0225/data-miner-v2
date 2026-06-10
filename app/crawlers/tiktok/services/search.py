"""
TikTok Search Service
"""

import time
from typing import Dict, Any
from .base import TikTokBaseService


class SearchService(TikTokBaseService):
    """TikTok Search Service"""

    def search(self, keyword: str, count: int = 20, use_fresh_token: bool = True,
               cursor: int = 0, offset: int = 0, proxies: Dict[str, str] = None) -> Dict[str, Any]:
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
        params = self._get_mobile_params()
        params.update({
            "keyword": keyword,
            "count": str(count),
            "cursor": str(cursor),
            "offset": str(offset),
            "search_source": "normal_search",
            "from_page": "search",
            "is_non_personalized_search": "0",
        })

        data = self._make_request(
            "/api/search/general/full/",
            params,
            use_fresh_token=use_fresh_token,
            proxies=proxies
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
                "log_pb": data.get("log_pb", {})
            }

        return {"success": False, "data": [], "count": 0, "has_more": False}

    def search_multiple_pages(self, keyword: str, total_items: int = 100,
                             per_page: int = 20, max_pages: int = 10,
                             use_fresh_token: bool = True, delay: float = 1.0, proxies: Dict[str, str] = None) -> Dict[str, Any]:
        """
        Search TikTok videos with pagination to get more results

        Args:
            keyword: Search keyword
            total_items: Target total number of items to fetch
            per_page: Items per page (10-30 recommended)
            max_pages: Maximum pages to fetch (safety limit)
            use_fresh_token: Use fresh token for first request only
            delay: Delay between pages in seconds
            proxies: Proxy configuration
        Returns:
            Dict with success, data (all items), count, pages_fetched
        """
        if use_fresh_token and not self._session_mstoken:
            self._session_mstoken = self.get_fresh_mstoken()
        elif not self._session_mstoken:
            self._session_mstoken = self._generate_fake_mstoken()

        all_items = []
        cursor = 0
        offset = 0
        pages_fetched = 0

        for page in range(max_pages):
            params = self._get_mobile_params()
            params.update({
                "keyword": keyword,
                "count": str(per_page),
                "cursor": str(cursor),
                "offset": str(offset),
                "search_source": "normal_search",
                "from_page": "search",
                "is_non_personalized_search": "0",
            })

            if page == 0:
                params["focus_state"] = "true"
            else:
                params["focus_state"] = "false"
                if self._search_id:
                    params["search_id"] = self._search_id

            params["msToken"] = self._session_mstoken

            data = self._make_request(
                "/api/search/general/full/",
                params,
                use_fresh_token=False,
                delay_before_request=0.5 if page > 0 else 1.5,
                proxies=proxies
            )

            if not data or "data" not in data:
                break

            items = data["data"]
            pages_fetched += 1

            if page == 0 and "log_pb" in data:
                log_pb = data.get("log_pb", {})
                if "impr_id" in log_pb:
                    self._search_id = log_pb["impr_id"]

            all_items.extend(items)

            if len(all_items) >= total_items:
                break

            has_more = data.get("has_more", False)
            if not has_more:
                break

            new_cursor = data.get("cursor", cursor)
            if new_cursor == cursor:
                break

            cursor = new_cursor
            offset = new_cursor

            if page < max_pages - 1:
                time.sleep(delay)

        return {
            "success": True,
            "data": all_items,
            "count": len(all_items),
            "pages_fetched": pages_fetched
        }
