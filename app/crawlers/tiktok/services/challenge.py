"""
TikTok Challenge/Hashtag Service
"""

import sys
from typing import Any, Dict

from .base import TikTokBaseService


class ChallengeService(TikTokBaseService):
    """TikTok Challenge/Hashtag Service"""

    def get_challenge_detail(
        self,
        challenge_id: str = "",
        challenge_name: str = "",
        use_fresh_token: bool = True,
    ) -> Dict[str, Any]:
        """
        Get TikTok challenge/hashtag detail

        Args:
            challenge_id: Challenge ID
            challenge_name: Challenge name/hashtag (without #)
            use_fresh_token: use fresh msToken

        Returns:
            Dict with success, data
        """

        sys.stderr.write(
            f"\n#️⃣ Getting challenge: {challenge_name or challenge_id}...\n"
        )
        sys.stderr.flush()

        params = self._get_mobile_params()

        if challenge_id:
            params.update({"challengeId": challenge_id})
        elif challenge_name:
            params.update({"challengeName": challenge_name})
        else:
            return {
                "success": False,
                "error": "Either challenge_id or challenge_name required",
            }

        data = self._make_request(
            "/api/challenge/detail/", params, use_fresh_token=use_fresh_token
        )

        sys.stderr.write(f"  Response keys: {list(data.keys()) if data else 'None'}\n")
        sys.stderr.flush()

        if data and "challengeInfo" in data:
            return {"success": True, "data": data["challengeInfo"]}

        return {
            "success": False,
            "data": None,
            "error": "No challengeInfo in response",
            "raw": data,
        }

    def get_challenge_videos(
        self,
        challenge_id: str,
        count: int = 20,
        cursor: int = 0,
        use_fresh_token: bool = True,
    ) -> Dict[str, Any]:
        """
        Get videos for a challenge/hashtag

        Args:
            challenge_id: Challenge ID
            count: number of videos to fetch
            cursor: pagination cursor
            use_fresh_token: use fresh msToken

        Returns:
            Dict with success, data, cursor
        """

        sys.stderr.write(f"\n📹 Getting videos for challenge ID: {challenge_id}...\n")
        sys.stderr.flush()

        params = self._get_mobile_params()

        params.update(
            {
                "challengeID": challenge_id,
                "count": str(count),
                "cursor": str(cursor),
            }
        )

        data = self._make_request(
            "/api/challenge/item_list/", params, use_fresh_token=use_fresh_token
        )

        if data and "itemList" in data:
            items = data["itemList"]

            # Limit results to requested count
            if len(items) > count:
                items = items[:count]
                sys.stderr.write(
                    f"  ⚠️ Trimmed {len(data['itemList'])} results to {count} as requested\n"
                )
                sys.stderr.flush()

            return {
                "success": True,
                "data": items,
                "count": len(items),
                "cursor": data.get("cursor", 0),
                "hasMore": data.get("hasMore", False),
            }

        return {"success": False, "data": [], "error": "No itemList in response"}
