"""Shared business logic for Movies — used by REST API and MCP tools."""

from app.crawlers.movies.config import MOVIE_LIST_TYPES, MovieProvider


def list_filters(
    *,
    category: str | None = None,
    country: str | None = None,
    year: int | None = None,
    sort_lang: str | None = None,
    sort_field: str | None = None,
    sort_type: str | None = None,
) -> dict:
    return {
        "category": category,
        "country": country,
        "year": year,
        "sort_lang": sort_lang,
        "sort_field": sort_field,
        "sort_type": sort_type,
    }


__all__ = ["MOVIE_LIST_TYPES", "MovieProvider", "list_filters"]
