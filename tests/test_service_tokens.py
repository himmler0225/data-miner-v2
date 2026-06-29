import pytest


@pytest.mark.unit
class TestServiceTokens:
    def test_validate_service_identity_missing(self):
        from app.middleware.service_tokens import validate_service_identity

        assert validate_service_identity(None, None) is False
        assert validate_service_identity("ai-layer", None) is False

    def test_expected_service_token(self, monkeypatch):
        from app.middleware.service_tokens import expected_service_token

        monkeypatch.setenv("SERVICE_TOKEN_AI_LAYER", "secret")
        assert expected_service_token("ai-layer") == "secret"
        assert expected_service_token("") is None

    def test_whitelisted_service_when_list_empty(self):
        from app.middleware.service_tokens import is_whitelisted_service

        assert is_whitelisted_service("ai-layer") is True
