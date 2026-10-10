from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.config import settings
from app.core.logging import logger
from app.core.redis import redis_client
from app.database import Base, engine
from app.limiter import limiter
from app.models import Alert, MLModel, Prediction, User  # noqa: F401
from app.routers import alerts, auth, models, predictions


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info(f"DEBUG={settings.DEBUG}")
    try:
        redis_client.ping()
        logger.info("Redis connected successfully.")
    except Exception as e:
        logger.warning(f"Redis unavailable: {e}. Continuing without cache.")

    if settings.DEBUG:
        Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")
    yield
    # Shutdown
    redis_client.close()
    logger.info("Redis connection closed.")
    logger.info(f"Shutting down {settings.APP_NAME}")


def get_application() -> FastAPI:
    application = FastAPI(
        title=settings.APP_NAME,
        debug=settings.DEBUG,
        docs_url="/docs" if settings.DEBUG else None,
        # hide docs in production
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS: only origins explicitly listed in settings are allowed.
    # Wildcard + credentials is rejected by browsers and forbidden
    # by config validation in production.
    origins = settings.CORS_ORIGINS

    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=bool(origins) and "*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.add_middleware(
        SlowAPIMiddleware,
    )

    application.state.limiter = limiter

    application.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    application.include_router(auth.router)
    application.include_router(models.router)
    application.include_router(predictions.router)
    application.include_router(alerts.router)

    return application


app = get_application()


@app.get("/", tags=["Health"])
@limiter.exempt
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "debug": settings.DEBUG,
    }


@app.get("/health", tags=["Health"])
@limiter.exempt
def health():
    """
    Dedicated health check endpoint.
    Railway pings this to verify the service is alive.
    """
    return {"status": "healthy"}


@app.get("/health/redis", tags=["Redis"])
@limiter.exempt
def redis_health():
    """
    Dedicated Redis health check endpoint.
    Railway pings this to verify the redis service is alive.
    """
    try:
        redis_client.ping()

        return {"status": "healthy", "service": "redis"}
    except Exception as e:
        logger.warning(f"Redis health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "service": "redis",
            },
        )
