import re
import json
import time
import hashlib
import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional, Tuple

import httpx

from .client_constants import LAZADA_ACS_URL, APP_KEY, JSV, BASE_UA, SEC_CH_UA

logger = logging.getLogger(__name__)

_BASE_HEADERS = {
    "user-agent":         BASE_UA,
    "accept":             "application/json",
    "accept-language":    "en-US,en;q=0.9,vi;q=0.8",
    "origin":             "https://www.lazada.vn",
    "referer":            "https://www.lazada.vn/",
    "sec-ch-ua":          SEC_CH_UA,
    "sec-ch-ua-mobile":   "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest":     "empty",
    "sec-fetch-mode":     "cors",
    "sec-fetch-site":     "same-site",
    "x-i18n-language":    "en",
    "x-i18n-regionid":    "VN",
}

# Probe uses the reviews API with a dummy item — it always returns _m_h5_tk in Set-Cookie
# when the token is invalid, which is exactly what we want on first call.
_PROBE_API      = "mtop.lazada.review.item.getPcReviewList"
_PROBE_VERSION  = "1.0"
_PROBE_PAYLOAD  = json.dumps(
    {"itemId": "1", "pageNo": 1, "pageSize": 1, "sort": "default"},
    separators=(",", ":"),
)


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _get_h5_token(cookies: dict) -> Optional[str]:
    raw = cookies.get("_m_h5_tk", "")
    return raw.split("_")[0] if raw else None


def _calc_sign(token: str, timestamp: str, data_str: str) -> str:
    return _md5(f"{token}&{timestamp}&{APP_KEY}&{data_str}")


def _extract_cookies_from_headers(headers) -> Dict:
    cookies: Dict = {}
    for k, v in headers.multi_items():
        if k.lower() != "set-cookie":
            continue
        for name in ("_m_h5_tk", "_m_h5_tk_enc", "cna", "t_uid", "t_fv", "lzd_sid"):
            if f"{name}=" in v:
                match = re.search(rf"{name}=([^;]+)", v)
                if match:
                    cookies[name] = match.group(1)
    return cookies


_session_cache: Dict = {}
_session_cache_ts: float = 0.0
_SESSION_TTL = 240  # seconds — refresh before Lazada's token window expires


async def create_lazada_session(proxy: Optional[str] = None) -> Dict:
    global _session_cache, _session_cache_ts
    if _session_cache and (time.time() - _session_cache_ts) < _SESSION_TTL:
        return dict(_session_cache)

    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None

    # Send probe with dummy token — Lazada always returns a fresh _m_h5_tk in Set-Cookie
    dummy = _md5(str(time.time()))
    ts    = str(int(time.time() * 1000))
    sign  = _calc_sign(dummy, ts, _PROBE_PAYLOAD)

    probe_params = {
        "jsv": JSV, "appKey": APP_KEY, "t": ts, "sign": sign,
        "api": _PROBE_API, "v": _PROBE_VERSION,
        "type": "originaljson", "isSec": "1", "AntiCreep": "true",
        "timeout": "20000", "dataType": "json", "sessionOption": "AutoLoginOnly",
        "x-i18n-language": "en", "x-i18n-regionID": "VN", "appkey": APP_KEY,
    }
    probe_cookies = {
        "_m_h5_tk":     f"{dummy}_{ts}",
        "_m_h5_tk_enc": _md5(f"{dummy}_{ts}"),
        "hng":          "VN|en|VND|704",
    }

    async with httpx.AsyncClient(headers=_BASE_HEADERS, timeout=15, transport=transport) as client:
        for k, v in probe_cookies.items():
            client.cookies.set(k, v, domain="lazada.vn")
        resp = await client.post(
            f"{LAZADA_ACS_URL}/h5/{_PROBE_API.lower()}/{_PROBE_VERSION}/",
            params=probe_params,
            content=f"data={_PROBE_PAYLOAD}".encode(),
            headers={"content-type": "application/x-www-form-urlencoded"},
        )

    cookies = {"hng": "VN|en|VND|704"}
    cookies.update(_extract_cookies_from_headers(resp.headers))

    if "_m_h5_tk" not in cookies:
        raise RuntimeError("Lazada did not return _m_h5_tk in probe response")

    logger.info("Lazada session acquired, token: %s...", cookies["_m_h5_tk"][:8])
    _session_cache    = dict(cookies)
    _session_cache_ts = time.time()
    return cookies


@asynccontextmanager
async def create_lazada_client(
    cookies: Dict,
    proxy: Optional[str] = None,
):
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    async with httpx.AsyncClient(
        cookies=cookies,
        headers=_BASE_HEADERS,
        follow_redirects=True,
        timeout=20,
        transport=transport,
    ) as client:
        yield client


def build_request_params(cookies: Dict, api: str, version: str, data: Dict) -> Tuple[str, Dict]:
    token     = _get_h5_token(cookies)
    timestamp = str(int(time.time() * 1000))
    data_str  = json.dumps(data, separators=(",", ":"))
    sign      = _calc_sign(token, timestamp, data_str)

    url = f"{LAZADA_ACS_URL}/h5/{api.lower()}/{version}/"
    params = {
        "jsv":             JSV,
        "appKey":          APP_KEY,
        "t":               timestamp,
        "sign":            sign,
        "api":             api,
        "v":               version,
        "type":            "originaljson",
        "isSec":           "0",
        "AntiCreep":       "false",
        "timeout":         "20000",
        "dataType":        "json",
        "sessionOption":   "AutoLoginOnly",
        "x-i18n-language": "en",
        "x-i18n-regionID": "VN",
        "data":            data_str,
    }
    return url, params


def build_post_params(cookies: Dict, api: str, version: str, data: Dict) -> Tuple[str, Dict, str]:
    token     = _get_h5_token(cookies)
    timestamp = str(int(time.time() * 1000))
    data_str  = json.dumps(data, separators=(",", ":"))
    sign      = _calc_sign(token, timestamp, data_str)

    url = f"{LAZADA_ACS_URL}/h5/{api.lower()}/{version}/"
    params = {
        "jsv":             JSV,
        "appKey":          APP_KEY,
        "t":               timestamp,
        "sign":            sign,
        "api":             api,
        "v":               version,
        "type":            "originaljson",
        "isSec":           "1",
        "AntiCreep":       "true",
        "timeout":         "20000",
        "dataType":        "json",
        "sessionOption":   "AutoLoginOnly",
        "x-i18n-language": "en",
        "x-i18n-regionID": "VN",
        "appkey":          APP_KEY,
    }
    return url, params, data_str
