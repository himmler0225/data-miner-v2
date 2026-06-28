from typing import Dict, Optional

from .client_constants import BASE_HEADERS


def build_headers(extra: Optional[Dict] = None) -> Dict:
    headers = dict(BASE_HEADERS)
    if extra:
        headers.update(extra)
    return headers
