import pytest


@pytest.mark.unit
class TestConfigurationHeaders:
    def test_get_youtube_headers_returns_dict(self):
        from app.config.headers import get_youtube_headers

        headers = get_youtube_headers()
        assert isinstance(headers, dict)

    def test_headers_contain_required_fields(self):
        from app.config.headers import get_youtube_headers

        headers = get_youtube_headers()
        assert "Content-Type" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert "X-Youtube-Client-Version" in headers

    def test_headers_include_visitor_data(self):
        from app.config.headers import get_youtube_headers

        headers = get_youtube_headers(visitor_data="test-visitor")
        assert headers["X-Goog-Visitor-Id"] == "test-visitor"
