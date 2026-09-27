import pytest
from pydantic import ValidationError

from app.config import Settings


SETTINGS_ENV_VARS = (
    "APP_NAME",
    "ENVIRONMENT",
    "DEBUG",
    "TESTING",
    "SECRET_KEY",
    "ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "DATABASE_URL",
    "REDIS_URL",
    "REDIS_CACHE_TTL_SECONDS",
    "CORS_ORIGINS",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "CELERY_TASK_SERIALIZER",
    "CELERY_RESULT_SERIALIZER",
    "CELERY_ACCEPT_CONTENT",
)


@pytest.fixture(autouse=True)
def isolate_settings_environment(monkeypatch):
    for variable in SETTINGS_ENV_VARS:
        monkeypatch.delenv(variable, raising=False)


BASE_SETTINGS = {
    "ENVIRONMENT": "test",
    "SECRET_KEY": "test-secret-key",
    "DATABASE_URL": "postgresql+psycopg://postgres:postgres@localhost:5432/modelpulse_test",
    "REDIS_URL": "redis://localhost:6379/15",
    "DEBUG": False,
    "TESTING": False,
}


def make_settings(**values):
    return Settings(_env_file=None, **values)


def test_valid_test_settings():
    settings = make_settings(**BASE_SETTINGS)

    assert settings.ENVIRONMENT == "test"
    assert settings.DEBUG is False
    assert settings.TESTING is False


def test_test_settings_use_safe_cors_defaults():
    settings = make_settings(**BASE_SETTINGS)

    assert settings.CORS_ORIGINS == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_cors_origins_parse_json_list():
    settings = make_settings(
        **BASE_SETTINGS,
        CORS_ORIGINS=["https://app.example.com", "https://admin.example.com"],
    )

    assert settings.CORS_ORIGINS == [
        "https://app.example.com",
        "https://admin.example.com",
    ]


def test_cors_origins_parse_from_environment(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["https://app.example.com", "https://admin.example.com"]',
    )

    settings = Settings(
        _env_file=None,
        **BASE_SETTINGS,
    )

    assert settings.CORS_ORIGINS == [
        "https://app.example.com",
        "https://admin.example.com",
    ]

def test_missing_secret_key_fails():
    config = {**BASE_SETTINGS}
    config.pop("SECRET_KEY")

    with pytest.raises(ValidationError):
        make_settings(**config)


def test_missing_database_url_fails():
    config = {**BASE_SETTINGS}
    config.pop("DATABASE_URL")

    with pytest.raises(ValidationError):
        make_settings(**config)


def test_missing_redis_url_fails():
    config = {**BASE_SETTINGS}
    config.pop("REDIS_URL")

    with pytest.raises(ValidationError):
        make_settings(**config)


def test_empty_secret_key_fails():
    config = {**BASE_SETTINGS, "SECRET_KEY": "   "}

    with pytest.raises(ValidationError):
        make_settings(**config)


def test_invalid_environment_fails():
    config = {**BASE_SETTINGS, "ENVIRONMENT": "staging"}

    with pytest.raises(ValidationError):
        make_settings(**config)


def test_production_requires_celery_broker():
    config = {**BASE_SETTINGS, "ENVIRONMENT": "production"}

    with pytest.raises(ValidationError, match="CELERY_BROKER_URL"):
        make_settings(**config)


def test_production_requires_cors_origins():
    config = {**BASE_SETTINGS, "ENVIRONMENT": "production", "CELERY_BROKER_URL": "redis://localhost:6379/0"}

    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        make_settings(**config)


def test_production_rejects_cors_wildcard():
    config = {
        **BASE_SETTINGS,
        "ENVIRONMENT": "production",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "CORS_ORIGINS": ["*"],
    }

    with pytest.raises(ValidationError, match="wildcard"):
        make_settings(**config)


def test_production_rejects_debug():
    config = {
        **BASE_SETTINGS,
        "ENVIRONMENT": "production",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "CORS_ORIGINS": ["https://app.example.com"],
        "DEBUG": True,
    }

    with pytest.raises(ValidationError, match="DEBUG"):
        make_settings(**config)


def test_production_rejects_testing():
    config = {
        **BASE_SETTINGS,
        "ENVIRONMENT": "production",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "CORS_ORIGINS": "https://app.example.com",
        "TESTING": True,
    }

    with pytest.raises(ValidationError, match="TESTING"):
        make_settings(**config)


def test_valid_production_settings():
    config = {
        **BASE_SETTINGS,
        "ENVIRONMENT": "production",
        "CELERY_BROKER_URL": "redis://localhost:6379/0",
        "CORS_ORIGINS": "https://app.example.com",
    }

    settings = make_settings(**config)

    assert settings.ENVIRONMENT == "production"
    assert settings.DEBUG is False
    assert settings.TESTING is False
    assert settings.CORS_ORIGINS == ["https://app.example.com"]
