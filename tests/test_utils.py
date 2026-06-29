import os

import pytest

from app.api_key_generator import generate_api_key


@pytest.mark.unit
class TestAPIKeyGenerator:
    def test_generate_api_key_default_length(self):
        api_key = generate_api_key()
        assert len(api_key) == 32
        assert isinstance(api_key, str)

    def test_generate_api_key_custom_length(self):
        for length in (16, 32, 64, 128):
            api_key = generate_api_key(length=length)
            assert len(api_key) == length

    def test_generate_api_key_uniqueness(self):
        keys = [generate_api_key() for _ in range(100)]
        assert len(keys) == len(set(keys))

    def test_generate_api_key_characters(self):
        api_key = generate_api_key()
        assert api_key.isalnum()


@pytest.mark.unit
class TestAuthMiddleware:
    def test_get_api_keys(self):
        from app.middleware.auth_middleware import get_api_keys

        keys = get_api_keys()
        assert isinstance(keys, set)
        assert len(keys) > 0

    def test_multiple_api_keys(self, monkeypatch):
        from app.middleware.auth_middleware import get_api_keys

        monkeypatch.setenv("API_KEYS", "key1,key2,key3")
        keys = get_api_keys()
        assert len(keys) == 3
        assert keys == {"key1", "key2", "key3"}
