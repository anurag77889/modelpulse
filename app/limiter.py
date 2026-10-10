from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def client_ip(request) -> str:
    """
    Rate-limit key: the caller's IP.

    Behind a platform proxy (e.g. Railway) every request arrives from
    the proxy IP, so get_remote_address alone would lump all users
    into one bucket. Trust the platform-injected X-Forwarded-For
    header when present.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


default_limits = [] if settings.TESTING else ["100/minute"]
limiter = Limiter(
    key_func=client_ip,
    default_limits=default_limits,
    # Shared storage so limits hold across workers/processes,
    # with in-memory fallback if Redis is briefly unavailable.
    storage_uri=settings.REDIS_URL,
    swallow_errors=True,
    in_memory_fallback_enabled=True,
)
