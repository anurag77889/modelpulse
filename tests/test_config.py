import pytest
from pydantic import ValidationError

from app.config import Settings


BASE_SETTINGS = {
    "ENVIRONMENT": "test",
    "SECRET_KEY": "test-secret-key",
    "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/modelpulse_test",
    "REDIS_URL": "redis://localhost:6379/15",
    "DEBUG": False,
    "TESTING": False,
}


def test_valid_test_settings():
    settings = Settings(**BASE_SETTINGS)

    assert settings.ENVIRONMENT == "test"
    assert settings.DEBUG is False
    assert settings.TESTING is False


def test_missing_secret_key_fails():
    config = {**BASE_SETTINGS}
    config.pop("SECRET_KEY")

    with pytest.raises(ValidationError):
        Settings(**config)


def test_missing_database_url_fails():
    config = {**BASE_SETTINGS}
    config.pop("DATABASE_URL")

    with pytest.raises(ValidationError):
        Settings(**config)


def test_missing_redis_url_fails():
    config = {**BASE_SETTINGS}
    config.pop("REDIS_URL")

    with pytest.raises(ValidationError):
        Settings(**config)


def test_empty_secret_key_fails():
    config = {**BASE_SETTINGS, "SECRET_KEY": "   "}

    with pytest.raises(ValidationError):
        Settings(**config)


def test_invalid_environment_fails():
    config = {**BASE_SETTINGS, "ENVIRONMENT": "staging"}

    with pytest.raises(ValidationError):
        Settings(**config)


def test_production_requires_celery_broker():
    config = {**BASE_SETTINGS, "ENVIRONMENT": "production"}

    with pytest.raises(ValidationError, match="CELERY_BROKER_URL"):
        Settings(**config)


def test_production_rejects_debug():
    config = {
        **BASE_SETTINGS,
        "ENVIRONMENT": "production",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "DEBUG": True,
    }

    with pytest.raises(ValidationError, match="DEBUG"):
        Settings(**config)


def test_production_rejects_testing():
    config = {
        **BASE_SETTINGS,
        "ENVIRONMENT": "production",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "TESTING": True,
    }

    with pytest.raises(ValidationError, match="TESTING"):
        Settings(**config)


def test_valid_production_settings():
    config = {
        **BASE_SETTINGS,
        "ENVIRONMENT": "production",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
    }

    settings = Settings(**config)

    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is False
    assert settings.TESTING is False
