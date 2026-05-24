class CrawlerBaseError(Exception):
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


class CrawlNetworkError(CrawlerBaseError):
    pass
