import httpx

from app.crawlers.youtube.client import get_context

from .parsers import find_tab_by_url_suffix, get_browse_tabs


async def post_browse(client: httpx.AsyncClient, browse_url: str, browse_id: str, params: str | None = None) -> dict:
    payload = {"context": get_context(), "browseId": browse_id}
    if params:
        payload["params"] = params
    resp = await client.post(browse_url, json=payload)
    resp.raise_for_status()
    return resp.json()


async def fetch_channel_tab(
    client: httpx.AsyncClient, browse_url: str, channel_id: str, params: str, url_suffix: str
) -> tuple[list[dict], dict | None]:
    """Fetch one channel tab (Videos, Playlists, ...) and return `(tabs, tab)`.

    Asks for the tab directly via `params`, so it normally comes back selected
    (with `content`) in a single request. If YouTube serves another tab instead
    (params ignored), follows the target tab's own browseEndpoint; if it rejects
    the params (400), falls back to a plain channel browse.

    `tab` is the tabRenderer with its `content`, or None when the channel has no
    such tab. `tabs` is the last response's tab list, for callers that fall back
    to another tab (e.g. Home)."""
    try:
        data = await post_browse(client, browse_url, channel_id, params)
    except httpx.HTTPStatusError as e:
        if e.response.status_code != 400:
            raise
        data = await post_browse(client, browse_url, channel_id)
    tabs = get_browse_tabs(data)
    tab = find_tab_by_url_suffix(tabs, url_suffix)

    if tab and "content" not in tab:
        endpoint = tab.get("endpoint", {}).get("browseEndpoint", {})
        if endpoint.get("browseId"):
            data = await post_browse(client, browse_url, endpoint["browseId"], endpoint.get("params"))
            tabs = get_browse_tabs(data)
            tab = find_tab_by_url_suffix(tabs, url_suffix)

    if tab and "content" not in tab:
        tab = None
    return tabs, tab
