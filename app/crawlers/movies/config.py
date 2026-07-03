"""Movies crawler constants (providers, types, timeouts)."""

from dataclasses import dataclass
from typing import Literal

from app.config.http import HTTP_MAX_ATTEMPTS, HTTP_MAX_CONNECTIONS, HTTP_MAX_KEEPALIVE, HTTP_RETRY_STATUSES

MovieProvider = Literal["kkphim", "ophim"]

MOVIE_API_TIMEOUT = 15

MOVIE_LIST_TYPES = frozenset(
    {
        "phim-bo",
        "phim-le",
        "tv-shows",
        "hoat-hinh",
        "phim-vietsub",
        "phim-thuyet-minh",
        "phim-long-tieng",
    }
)


@dataclass(frozen=True)
class ProviderSpec:
    name: MovieProvider
    base_url: str
    image_cdn: str
    new_movies_path: str
    type_list_full_filters: bool
    has_webp_proxy: bool


PROVIDERS: dict[MovieProvider, ProviderSpec] = {
    "kkphim": ProviderSpec(
        name="kkphim",
        base_url="https://phimapi.com",
        image_cdn="https://phimimg.com/",
        new_movies_path="/danh-sach/phim-moi-cap-nhat-v3",
        type_list_full_filters=True,
        has_webp_proxy=True,
    ),
    "ophim": ProviderSpec(
        name="ophim",
        base_url="https://ophim1.com",
        image_cdn="https://img.ophim.live/uploads/movies/",
        new_movies_path="/danh-sach/phim-moi-cap-nhat",
        type_list_full_filters=False,
        has_webp_proxy=False,
    ),
}

# Re-export for client module
__all__ = [
    "HTTP_MAX_ATTEMPTS",
    "HTTP_MAX_CONNECTIONS",
    "HTTP_MAX_KEEPALIVE",
    "HTTP_RETRY_STATUSES",
    "MOVIE_API_TIMEOUT",
    "MOVIE_LIST_TYPES",
    "MovieProvider",
    "PROVIDERS",
    "ProviderSpec",
]
