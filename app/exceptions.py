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

class TikTokError(CrawlerBaseError):
    pass

class NativeSearchError(TikTokError):
    pass

class TikHubError(TikTokError):
    pass
