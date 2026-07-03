from typing import TypedDict


class ThumbnailItem(TypedDict):
    url: str
    width: int | None
    height: int | None


class ChannelInfo(TypedDict):
    channel_id: str
    channel_name: str
    handle: str | None
    avatar: str | None
    banner: str | None
    subscriber_count: str | None
    description: str


class TrendingVideo(TypedDict):
    video_id: str
    title: str
    thumbnail: list[ThumbnailItem]
    channel_name: str
    views: str
    published_time: str
    url: str


class SearchVideo(TypedDict):
    video_id: str
    title: str
    url: str
    duration: str
    views: str
    channel: str
    channel_id: str
    published_time: str
    description_snippet: str
    thumbnails: list[ThumbnailItem]


class VideoDetail(TypedDict):
    video_id: str
    title: str
    author: str
    length_seconds: str
    views: str
    is_live_content: bool


class VideoDetailError(TypedDict):
    error: bool
    reason: str
    status: str


class CommentReply(TypedDict):
    comment_id: str
    author: str
    avatar: str | None
    content: str
    published_time: str
    likes: int


class Comment(TypedDict):
    comment_id: str
    author: str
    avatar: str | None
    content: str
    published_time: str
    likes: int
    replies_count: int
    replies: list[CommentReply]
