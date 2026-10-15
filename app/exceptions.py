class CrawlerBaseError(Exception):
    pass


class CrawlNetworkError(CrawlerBaseError):
    pass


class CrawlTimeoutError(CrawlNetworkError):
    pass


class YouTubeStructureChangedError(CrawlerBaseError):
    def __init__(self, message: str, context: dict = None):
        super().__init__(message)
        self.context = context or {}

    def __str__(self):
        base = super().__str__()
        if self.context:
            return f"{base} | context={self.context}"
        return base


class YouTubeNotFoundError(CrawlerBaseError):
    """The requested video/channel/playlist doesn't exist or isn't available."""


class InvalidInputError(ValueError):
    """Caller input failed validation (bad id format, empty batch, ...).

    Carries an i18n message key (see app/i18n/messages.py) plus its params, so
    the API can localize it; str() renders the English text (used by MCP)."""

    def __init__(self, key: str, **params):
        self.key = key
        self.params = params
        super().__init__(key)

    def __str__(self) -> str:
        from app.i18n.messages import t

        return t(self.key, "en", **self.params)


class TikTokError(CrawlerBaseError):
    pass


class NativeSearchError(TikTokError):
    pass


class TikHubError(TikTokError):
    pass


class TavilyError(CrawlNetworkError):
    pass
