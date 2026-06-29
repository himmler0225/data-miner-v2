from __future__ import annotations
import random
from typing import Dict, Optional
from .constants import CLIENT_VERSION, DEFAULT_USER_AGENT, YOUTUBE_BASE_URL
_IMPERSONATE_POOL = ['chrome131', 'chrome130', 'chrome129', 'edge131']
_DEFAULT_ACCEPT_LANGUAGE = 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7'

def get_youtube_headers(visitor_data: str | None=None, client_version: str | None=None) -> Dict:
    ua_profile = random.choice(_IMPERSONATE_POOL)
    headers = {'Content-Type': 'application/json', 'Accept': '*/*', 'Accept-Language': _DEFAULT_ACCEPT_LANGUAGE, 'Origin': YOUTUBE_BASE_URL, 'Referer': f'{YOUTUBE_BASE_URL}/', 'Connection': 'keep-alive', 'X-Youtube-Client-Name': '1', 'X-Youtube-Client-Version': client_version or CLIENT_VERSION}
    if visitor_data:
        headers['X-Goog-Visitor-Id'] = visitor_data
    headers['_impersonate'] = ua_profile
    return headers

def get_youtube_html_headers(hl: str, gl: str, user_agent: str | None=None) -> Dict:
    return {'User-Agent': user_agent or DEFAULT_USER_AGENT, 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8', 'Accept-Language': f'{hl}-{gl},{hl};q=0.9,en;q=0.8', 'Connection': 'keep-alive', 'Upgrade-Insecure-Requests': '1', 'Sec-Fetch-Dest': 'document', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'none', 'Sec-Fetch-User': '?1'}

def get_tikhub_headers(api_key: str) -> Dict:
    return {'Authorization': f'Bearer {api_key}'}

def get_supabase_rest_headers(service_key: str) -> Dict:
    return {'apikey': service_key, 'Authorization': f'Bearer {service_key}'}
