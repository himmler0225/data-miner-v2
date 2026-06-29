"""
Pytest configuration and fixtures
"""

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def test_api_key():
    return "test_api_key_12345"


@pytest.fixture(scope="session", autouse=True)
def setup_test_env(test_api_key):
    os.environ["API_KEYS"] = test_api_key
    os.environ["LOG_LEVEL"] = "DEBUG"
    os.environ["ENABLE_SCHEDULER"] = "false"
    os.environ["REQUIRE_SERVICE_AUTH"] = "false"
    os.environ["ENABLE_IP_WHITELIST"] = "false"
    os.environ["BFF_GUARD_ENABLED"] = "false"


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(test_api_key):
    return {"X-API-Key": test_api_key}
