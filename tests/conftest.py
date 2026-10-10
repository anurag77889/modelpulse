import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from alembic import command
from alembic.config import Config

env_file = Path(".env.test")

if env_file.exists():
    load_dotenv(".env.test", override=True)

# Configuration validation requires an explicit environment.
os.environ.setdefault("ENVIRONMENT", "test")

from app.config import settings
from app.core.celery import celery_app
from app.core.redis import redis_client

# Create engine ONCE — shared across everything
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# Create session for testing
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def override_get_db():
    """Injects test DB session into every route."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def setup_database():
    """
    Creates the schema using Alembic migrations before
    each test and drops everything afterwards.
    """
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")

    # Start every test with a clean cache/limiter/broker state so
    # assertions never pass because of leftovers from a prior test.
    redis_client.flushdb()

    yield
    command.downgrade(alembic_cfg, "base")


@pytest.fixture(scope="function")
def client(setup_database):
    """
    Provides TestClient with test DB injected.
    Overrides both the DB dependency AND the engine
    used by the lifespan startup.
    """
    from app.database import get_db
    from app.main import get_application

    app = get_application()

    # Override get_db so all routes use test DB session
    app.dependency_overrides[get_db] = override_get_db

    # CRITICAL: Also patch the engine used by lifespan
    # so create_all() in main.py uses the test engine too
    import app.database as db_module

    original_engine = db_module.engine
    db_module.engine = engine  # 👈 point app at test engine

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    # Restore original engine after test
    db_module.engine = original_engine
    app.dependency_overrides.clear()


# ── Reusable fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def registered_user(client: TestClient) -> dict:
    response = client.post(
        "/auth/register",
        json={
            "email": "test@example.com",
            "username": "testuser",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def auth_headers(client: TestClient, registered_user: dict) -> dict:
    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpassword123",
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def registered_model(client: TestClient, auth_headers: dict) -> dict:
    response = client.post(
        "/models/",
        json={
            "name": "Test Churn Model",
            "version": "1.0.0",
            "description": "Test model for unit tests",
            "model_type": "classification",
            "drift_threshold": 0.05,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def logged_prediction(
    client: TestClient,
    auth_headers: dict,
    registered_model: dict,
) -> dict:
    model_id = registered_model["id"]
    response = client.post(
        f"/models/{model_id}/predictions/",
        json={
            "input_data": {"age": 34, "tenure_months": 12},
            "prediction_output": {"label": "churn", "probability": 0.87},
            "confidence_score": 0.87,
            "latency_ms": 42.5,
        },
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


@pytest.fixture(autouse=True)
def disable_rate_limiting():
    from app.limiter import limiter

    original = limiter.enabled
    limiter.enabled = False
    yield
    limiter.enabled = original


@pytest.fixture
def enable_rate_limiting():
    from app.limiter import limiter

    original = limiter.enabled
    limiter.enabled = True

    # Reset the rate limiter state
    limiter._storage.reset()

    yield

    limiter.enabled = original
    limiter._storage.reset()


@pytest.fixture
def clear_redis():
    redis_client.flushdb()
    yield
    redis_client.flushdb()


@pytest.fixture
def celery_eager():
    old = celery_app.conf.task_always_eager
    old_propagates = celery_app.conf.task_eager_propagates

    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True

    yield

    celery_app.conf.task_always_eager = old
    celery_app.conf.task_eager_propagates = old_propagates
