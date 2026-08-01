import pytest

from app.core.config import Settings, _validate_production_settings


def _settings(**overrides) -> Settings:
    defaults = {
        "database_url": "postgresql+asyncpg://u:p@localhost/db",
        "database_url_sync": "postgresql+psycopg://u:p@localhost/db",
        "jwt_secret": "a-real-random-secret-that-is-long-enough-1234",
        "environment": "production",
    }
    return Settings(**{**defaults, **overrides})


def test_development_settings_never_validated():
    settings = _settings(environment="development", jwt_secret="dev-only-secret-not-for-production-abc123")
    _validate_production_settings(settings)  # should not raise


def test_production_rejects_known_dev_secret():
    settings = _settings(jwt_secret="dev-only-secret-not-for-production-abc123")
    with pytest.raises(RuntimeError):
        _validate_production_settings(settings)


def test_production_rejects_short_secret():
    settings = _settings(jwt_secret="short")
    with pytest.raises(RuntimeError):
        _validate_production_settings(settings)


def test_production_accepts_real_secret():
    settings = _settings()
    _validate_production_settings(settings)  # should not raise
