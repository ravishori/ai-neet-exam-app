import structlog

from app.core.config import get_settings
from app.modules.identity.services import email_service


def _set_environment(monkeypatch, value: str):
    monkeypatch.setenv("ENVIRONMENT", value)
    if value == "production":
        # A real-looking secret so this test exercises email_service's own
        # production gate, not the separate fail-fast check in test_config.py.
        monkeypatch.setenv("JWT_SECRET", "a-real-random-secret-that-is-long-enough-1234")
    get_settings.cache_clear()


def test_dev_mode_logs_the_link_for_testability(monkeypatch):
    _set_environment(monkeypatch, "development")
    with structlog.testing.capture_logs() as logs:
        email_service.send_password_reset_email(to="user@example.com", token="secret-token-123")

    assert any("secret-token-123" in str(entry) for entry in logs)
    get_settings.cache_clear()


def test_production_never_logs_the_raw_token(monkeypatch):
    _set_environment(monkeypatch, "production")
    with structlog.testing.capture_logs() as logs:
        email_service.send_password_reset_email(to="user@example.com", token="secret-token-123")
        email_service.send_verification_email(to="user@example.com", token="another-secret-456")

    combined = str(logs)
    assert "secret-token-123" not in combined
    assert "another-secret-456" not in combined
    get_settings.cache_clear()
