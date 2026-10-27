from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings


def client_ip(request) -> str:
    """
    Rate-limit key: the caller's IP.

    Behind a reverse proxy (e.g. the AWS ALB) every request arrives from
    the proxy IP, so get_remote_address alone would lump all users into
    one bucket. Each trusted proxy appends the address it saw to
    X-Forwarded-For, so the real client is the Nth entry from the right.
    Entries further left are client-supplied and must never be trusted,
    or anyone could dodge the limit by sending a fake header.
    """
    hops = settings.TRUSTED_PROXY_COUNT
    forwarded_for = request.headers.get("X-Forwarded-For")
    if hops and forwarded_for:
        addresses = [a.strip() for a in forwarded_for.split(",") if a.strip()]
        if len(addresses) >= hops:
            return addresses[-hops]
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
