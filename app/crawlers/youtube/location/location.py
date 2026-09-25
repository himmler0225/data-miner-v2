import random

from app.config.constants import CLIENT_NAME
from app.crawlers.youtube.client import get_client_version, get_visitor_data

from .location_constants import _GL_TIMEZONE


def get_region_context(gl: str, hl: str) -> dict:
    """InnerTube context with overridden gl/hl, for searching as a viewer in that
    country (pass it to `fetch_search_page(context=...)`)."""
    client: dict = {
        "hl": hl,
        "gl": gl,
        "clientName": CLIENT_NAME,
        "clientVersion": get_client_version(),
        "platform": "DESKTOP",
        "clientFormFactor": "UNKNOWN_FORM_FACTOR",
        "timeZone": _GL_TIMEZONE.get(gl, "America/New_York"),
        "screenWidthPoints": random.choice([1280, 1366, 1440, 1920]),
        "screenHeightPoints": random.choice([720, 768, 900, 1080]),
        "screenPixelDensity": random.choice([1, 2]),
    }
    visitor_data = get_visitor_data()
    if visitor_data:
        client["visitorData"] = visitor_data
    return {
        "client": client,
        "user": {"lockedSafetyMode": False},
        "request": {
            "useSsl": True,
            "internalExperimentFlags": [],
            "consistencyTokenJars": [],
        },
    }
