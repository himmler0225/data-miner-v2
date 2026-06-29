import json
import random
import string
import time
from typing import Any, Dict
from urllib.parse import urlencode, urlparse

import requests
from app.crawlers.tiktok.lib.signatures.bogus import Signer
from app.crawlers.tiktok.lib.signatures.gnarly import get_X_Gnarly


class TikTokBaseService:

    BASE_URL = "https://www.tiktok.com"
    MOBILE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
    PC_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"

    def __init__(
        self,
        region: str = "VN",
        language: str = "vi",
        proxies: dict = None,
        session: "requests.Session" = None,
    ):
        self.region = region
        self.language = language
        self.proxies = proxies
        # Reuse a pre-warmed session (with a trusted ttwid cookie) when provided.
        self.session = session if session is not None else requests.Session()
        self._session_mstoken = None
        self._search_id = None

        if proxies:
            self.session.proxies.update(proxies)

    def _generate_fake_mstoken(self, length: int = 107) -> str:
        chars = string.ascii_letters + string.digits + "_-"
        return "".join(random.choice(chars) for _ in range(length))

    def _generate_device_id(self) -> str:
        if not hasattr(self, "_device_id"):
            first_digit = "7"
            rest_digits = "".join(random.choice(string.digits) for _ in range(18))
            self._device_id = first_digit + rest_digits
        return self._device_id

    def _generate_odin_id(self) -> str:
        if not hasattr(self, "_odin_id"):
            first_digit = "7"
            rest_digits = "".join(random.choice(string.digits) for _ in range(18))
            self._odin_id = first_digit + rest_digits
        return self._odin_id

    def _get_webid_last_time(self) -> str:
        return str(int(time.time()))

    def _get_timezone_name(self) -> str:
        tz_map = {
            "VN": "Asia/Ho_Chi_Minh",
            "US": "America/New_York",
            "GB": "Europe/London",
            "JP": "Asia/Tokyo",
            "KR": "Asia/Seoul",
            "TH": "Asia/Bangkok",
            "SG": "Asia/Singapore",
            "PH": "Asia/Manila",
            "ID": "Asia/Jakarta",
        }
        return tz_map.get(self.region, "Etc/GMT-7")

    def _get_client_ab_versions(self) -> str:
        return "70508271,73720541,75294820,75638231,75650499,75694226,75747657,75843653,76034423,76036860,76040716,76053881,76054348,76055827,76065197,76088344,76135110,76145855,76146172,76184863,76187552,76212861,76217122,70405643,71057832,71200802,73004916,73171280,73208420,74276218,74844724,75330961"

    def _get_web_search_code(self) -> str:
        search_code = {
            "tiktok": {
                "client_params_x": {
                    "search_engine": {
                        "ies_mt_user_live_video_card_use_libra": 1,
                        "mt_search_general_user_live_card": 1,
                    }
                },
                "search_server": {},
            }
        }
        return json.dumps(search_code, separators=(",", ":"))

    def get_fresh_mstoken(self) -> str:
        try:
            headers = {
                "User-Agent": self.MOBILE_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": f"{self.language}-{self.region},{self.language};q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }

            response = self.session.get(
                self.BASE_URL, headers=headers, timeout=10, allow_redirects=True
            )

            if "Set-Cookie" in response.headers:
                set_cookie = response.headers["Set-Cookie"]
                for cookie_part in set_cookie.split(";"):
                    if "msToken=" in cookie_part:
                        ms_token = (
                            cookie_part.split("msToken=")[1].split(";")[0].strip()
                        )
                        return ms_token

            if "msToken" in self.session.cookies:
                ms_token = self.session.cookies["msToken"]
                return ms_token

            return self._generate_fake_mstoken()

        except Exception:
            return self._generate_fake_mstoken()

    def _get_mobile_params(self) -> Dict[str, str]:
        return {
            "aid": "1988",
            "app_name": "tiktok_web",
            "channel": "tiktok_web",
            "device_id": self._generate_device_id(),
            "odinId": self._generate_odin_id(),
            "device_platform": "web_mobile",
            "device_type": "web_h265",
            "os": "ios",
            "WebIdLastTime": self._get_webid_last_time(),
            "region": self.region,
            "priority_region": "",
            "language": self.language,
            "app_language": self.language,
            "webcast_language": self.language,
            "browser_language": f"{self.language}-{self.region}",
            "browser_name": "Mozilla",
            "browser_online": "true",
            "browser_platform": "iPhone",
            "browser_version": "5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "cookie_enabled": "true",
            "focus_state": "true",
            "is_fullscreen": "false",
            "is_page_visible": "true",
            "screen_width": "390",
            "screen_height": "844",
            "data_collection_enabled": "true",
            "user_is_login": "false",
            "history_len": "3",
            "referer": "",
            "tz_name": self._get_timezone_name(),
            "client_ab_versions": self._get_client_ab_versions(),
            "web_search_code": self._get_web_search_code(),
        }

    def _get_pc_params(self) -> Dict[str, str]:
        return {
            "aid": "1988",
            "app_name": "tiktok_web",
            "channel": "tiktok_web",
            "device_id": self._generate_device_id(),
            "odinId": self._generate_odin_id(),
            "device_platform": "web_pc",
            "os": "windows",
            "WebIdLastTime": self._get_webid_last_time(),
            "region": self.region,
            "priority_region": "",
            "language": "en",
            "app_language": "en",
            "webcast_language": "en",
            "browser_language": "en-US",
            "browser_name": "Mozilla",
            "browser_online": "true",
            "browser_platform": "Win32",
            "browser_version": "5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "cookie_enabled": "true",
            "focus_state": "true",
            "is_fullscreen": "false",
            "is_page_visible": "true",
            "screen_width": "1920",
            "screen_height": "1080",
            "data_collection_enabled": "true",
            "user_is_login": "false",
            "history_len": "3",
            "referer": "https://www.tiktok.com/",
            "root_referer": "https://www.tiktok.com/",
            "tz_name": self._get_timezone_name(),
        }

    def _get_mac_search_params(self) -> Dict[str, str]:
        """Fingerprint matching the working browser curl: macOS Chrome, web_pc,
        web_search_code included. No search_source/from_page."""
        return {
            "aid": "1988",
            "app_name": "tiktok_web",
            "channel": "tiktok_web",
            "device_id": self._generate_device_id(),
            "odinId": self._generate_odin_id(),
            "device_platform": "web_pc",
            "device_type": "web_h265",
            "os": "mac",
            "WebIdLastTime": self._get_webid_last_time(),
            "region": self.region,
            "priority_region": "",
            "language": "en",
            "app_language": "en",
            "webcast_language": "en",
            "browser_language": "en-US",
            "browser_name": "Mozilla",
            "browser_online": "true",
            "browser_platform": "MacIntel",
            "browser_version": "5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36",
            "cookie_enabled": "true",
            "focus_state": "true",
            "is_fullscreen": "true",
            "is_page_visible": "true",
            "screen_width": "1512",
            "screen_height": "982",
            "data_collection_enabled": "true",
            "user_is_login": "false",
            "history_len": "2",
            "referer": "",
            "tz_name": "Asia/Saigon",
            "client_ab_versions": self._get_client_ab_versions(),
            "web_search_code": self._get_web_search_code(),
        }

    MAC_SEARCH_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"

    def _sign_url(self, url: str, user_agent: str = None) -> Dict[str, str]:
        if user_agent is None:
            user_agent = self.MOBILE_UA

        parsed = urlparse(url)
        query_string = parsed.query

        signed_params = Signer.sign(query_string, user_agent)
        xbogus = (
            signed_params.split("X-Bogus=")[-1] if "X-Bogus=" in signed_params else ""
        )

        xgnarly = get_X_Gnarly(
            query_string=query_string, request_body="", user_agent=user_agent
        )

        if xgnarly:
            xgnarly = xgnarly.strip()

        return {"xbogus": xbogus, "xgnarly": xgnarly}

    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        use_fresh_token: bool = True,
        delay_before_request: float = 1.5,
        user_agent: str = None,
        proxies: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        if user_agent is None:
            user_agent = self.MOBILE_UA

        if use_fresh_token:
            ms_token = self.get_fresh_mstoken()
            if not self._session_mstoken:
                self._session_mstoken = ms_token
            time.sleep(delay_before_request)
        else:
            ms_token = self._generate_fake_mstoken()
            if not self._session_mstoken:
                self._session_mstoken = ms_token

        params["msToken"] = ms_token

        base_url = f"{self.BASE_URL}{endpoint}"
        url = f"{base_url}?{urlencode(params)}"

        signatures = self._sign_url(url, user_agent=user_agent)
        params["X-Bogus"] = signatures["xbogus"]
        params["X-Gnarly"] = signatures["xgnarly"]

        signed_url = f"{base_url}?{urlencode(params)}"

        headers = {
            "User-Agent": user_agent,
            "Referer": f"{self.BASE_URL}/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": f"{self.language}-{self.region},{self.language};q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Connection": "keep-alive",
        }

        try:
            response = self.session.get(
                signed_url, headers=headers, proxies=proxies, timeout=15
            )

            if response.status_code != 200 or len(response.content) == 0:
                return {}

            try:
                data = response.json()
            except Exception:
                try:
                    import brotli

                    decompressed = brotli.decompress(response.content)
                    data = json.loads(decompressed.decode("utf-8"))
                except Exception:
                    return {}

            status_code = data.get("statusCode", data.get("status_code", -1))

            if status_code != 0:
                return {}

            return data

        except Exception:
            return {}
