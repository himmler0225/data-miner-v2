"""Low-level helpers for navigating InnerTube JSON."""


def join_runs(node: dict) -> str:
    """Concatenate all `runs[].text` ; YouTube splits text at styled/bolded spans."""
    runs = node.get("runs") if isinstance(node, dict) else None
    if runs:
        return "".join(r.get("text", "") for r in runs)
    return node.get("simpleText", "") if isinstance(node, dict) else ""


def extract_continuation_token(item: dict) -> str | None:
    return (
        item.get("continuationItemRenderer", {})
        .get("continuationEndpoint", {})
        .get("continuationCommand", {})
        .get("token")
    )


def first_continuation_token(items: list[dict]) -> str | None:
    return next((extract_continuation_token(i) for i in items if "continuationItemRenderer" in i), None)


def get_continuation_items(data: dict) -> list[dict]:
    commands = data.get("onResponseReceivedCommands") or data.get("onResponseReceivedActions") or []
    return (commands[0].get("appendContinuationItemsAction", {}).get("continuationItems", [])) if commands else []


def find_tab_by_url_suffix(tabs: list[dict], suffix: str) -> dict | None:
    """Find a channel-page tab whose target URL ends with `suffix` (e.g. "/videos",
    "/playlists", "/featured" for Home). Tab titles are localized to the request's
    hl/gl (e.g. "Video"/"Danh sách phát" for hl=vi) so they can't be matched by
    text; the URL path segment stays stable across locales.

    Returns the tab's `tabRenderer` (or `expandableTabRenderer`) dict, or None."""
    for tab in tabs:
        renderer = tab.get("tabRenderer") or tab.get("expandableTabRenderer") or {}
        url = renderer.get("endpoint", {}).get("commandMetadata", {}).get("webCommandMetadata", {}).get("url", "")
        if url.endswith(suffix):
            return renderer
    return None


def get_browse_tabs(data: dict) -> list[dict]:
    return data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])


def get_first_badge_text(overlays: list[dict]) -> str:
    """First thumbnail badge text (video duration, playlist video count) from a
    `thumbnailViewModel.overlays` list. YouTube serves the badge under either
    `thumbnailBottomOverlayViewModel.badges` or `thumbnailOverlayBadgeViewModel.thumbnailBadges`."""
    for overlay in overlays:
        badges = overlay.get("thumbnailBottomOverlayViewModel", {}).get("badges") or overlay.get(
            "thumbnailOverlayBadgeViewModel", {}
        ).get("thumbnailBadges", [])
        for badge in badges:
            text = badge.get("thumbnailBadgeViewModel", {}).get("text", "")
            if text:
                return text
    return ""
