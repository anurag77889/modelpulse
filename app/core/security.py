import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.core.scopes import ALL_SCOPES, format_scope

ACCESS_TOKEN_TYPE = "access"


def hash_password(plain_password: str) -> str:
    """Hash a plain text password using bcrypt directly."""
    pwd_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a stored bcrypt hash."""
    pwd_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hashed_bytes)


def generate_secret(prefix: str, nbytes: int = 32) -> str:
    """
    High-entropy random credential (client secret, refresh token).
    The prefix makes leaked values easy to recognise in logs and scanners.
    """
    return f"{prefix}{secrets.token_urlsafe(nbytes)}"


def hash_secret(secret: str) -> str:
    """
    SHA-256 digest for storing random, high-entropy secrets.

    bcrypt's deliberate slowness protects low-entropy human passwords
    from brute force. A 256-bit random secret can't be brute-forced, so
    a fast hash is safe here and keeps the token endpoint quick.
    """
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def verify_secret(secret: str, secret_hash: str) -> bool:
    """Constant-time comparison so response timing leaks nothing."""
    return hmac.compare_digest(hash_secret(secret), secret_hash)


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    *,
    scopes: frozenset[str] | set[str] = ALL_SCOPES,
    client_id: Optional[str] = None,
) -> str:
    """
    Issue a signed access token.

    `subject` is always the user the token acts for. Machine-client
    tokens also carry `client_id` and only the scopes they were granted.
    """
    now = datetime.now(UTC)
    expire = now + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "sub": str(subject),
        "iat": now,
        "exp": expire,
        "jti": uuid.uuid4().hex,
        "typ": ACCESS_TOKEN_TYPE,
        "scope": format_scope(scopes),
    }
    if client_id is not None:
        payload["client_id"] = client_id
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
    """
    Validate an access token and return its claims, or None if it is
    malformed, expired, issued for another audience/issuer, or not an
    access token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            audience=settings.JWT_AUDIENCE,
            issuer=settings.JWT_ISSUER,
            options={
                "require_aud": True,
                "require_iss": True,
                "require_exp": True,
                "require_sub": True,
                "require_jti": True,
            },
        )
    except JWTError:
        return None

    if payload.get("typ") != ACCESS_TOKEN_TYPE:
        return None
    return payload
