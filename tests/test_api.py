import pytest
from fastapi import status


@pytest.mark.api
class TestHealthEndpoint:
    def test_health_check(self, client):
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["service"] == "data-miner"
        assert data["data"]["version"] == "1.0.0"


@pytest.mark.api
class TestAuthentication:
    def test_search_without_api_key(self, client):
        response = client.get("/api/videos/search?q=python")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_with_invalid_api_key(self, client):
        headers = {"X-API-Key": "invalid_key"}
        response = client.get("/api/videos/search?q=python", headers=headers)
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_search_with_valid_api_key(self, client, auth_headers):
        response = client.get("/api/videos/search?q=python", headers=auth_headers)
        assert response.status_code not in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )


@pytest.mark.api
class TestSearchEndpoint:
    def test_search_missing_query_parameter(self, client, auth_headers):
        response = client.get("/api/videos/search", headers=auth_headers)
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_search_invalid_page_parameter(self, client, auth_headers):
        response = client.get(
            "/api/videos/search?q=python&page=0",
            headers=auth_headers,
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.api
class TestVideoDetailEndpoint:
    def test_video_detail_requires_auth(self, client):
        response = client.get("/api/videos/dQw4w9WgXcQ")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_video_detail_route_exists(self, client, auth_headers):
        response = client.get("/api/videos/dQw4w9WgXcQ", headers=auth_headers)
        assert response.status_code in (
            status.HTTP_200_OK,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
