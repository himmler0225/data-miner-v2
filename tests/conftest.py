"""
Pytest configuration and fixtures
"""

import os

import pytest
from fastapi.testclient import TestClient

TEST_API_KEY = "test_api_key_12345"

# Set at import time, before any test module imports `app` (settings are read
# when app modules are first imported, which happens during collection).
os.environ["API_KEYS"] = TEST_API_KEY
os.environ["LOG_LEVEL"] = "DEBUG"
os.environ["ENABLE_SCHEDULER"] = "false"
os.environ["REQUIRE_SERVICE_AUTH"] = "false"
os.environ["ENABLE_IP_WHITELIST"] = "false"


@pytest.fixture(scope="session")
def test_api_key():
    return TEST_API_KEY


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(test_api_key):
    return {"X-API-Key": test_api_key}
