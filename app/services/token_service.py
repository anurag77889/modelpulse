import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import CredentialsException
from app.core.security import create_access_token, generate_secret, hash_secret
from app.models.refresh_token import RefreshToken
from app.models.user import User

logger = logging.getLogger(__name__)

REFRESH_TOKEN_PREFIX = "mpr_"


def _issue_refresh_token(db: Session, user_id: int, family_id: str) -> str:
    """Store a new refresh token (hashed) and return the raw value."""
    raw = generate_secret(REFRESH_TOKEN_PREFIX)
    db.add(
        RefreshToken(
            token_hash=hash_secret(raw),
            family_id=family_id,
            user_id=user_id,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    return raw


def _token_pair(access_token: str, refresh_token: str) -> dict:
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_token": refresh_token,
    }


def _revoke_family(db: Session, family_id: str, now: datetime) -> int:
    return (
        db.query(RefreshToken)
        .filter(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .update({"revoked_at": now}, synchronize_session=False)
    )


def issue_user_tokens(db: Session, user: User) -> dict:
    """Start a new session: access token plus the first refresh token."""
    refresh_token = _issue_refresh_token(db, user.id, family_id=uuid.uuid4().hex)
    db.commit()
    return _token_pair(create_access_token(subject=user.id), refresh_token)


def rotate_refresh_token(db: Session, raw_token: str) -> dict:
    """
    Exchange a refresh token for a new access + refresh token pair.

    The presented token is marked used and can never be used again.
    If an already-used token comes back, someone else holds a copy of
    it, so every token in its family is revoked and the caller must
    log in again.
    """
    token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_secret(raw_token))
        .first()
    )
    now = datetime.now(UTC)

    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise CredentialsException

    # Atomic claim: only one request can flip used_at from NULL, so two
    # concurrent refreshes with the same token can't both succeed.
    claimed = (
        db.query(RefreshToken)
        .filter(
            RefreshToken.id == token.id,
            RefreshToken.used_at.is_(None),
            RefreshToken.revoked_at.is_(None),
        )
        .update({"used_at": now}, synchronize_session=False)
    )
    if claimed == 0:
        revoked = _revoke_family(db, token.family_id, now)
        db.commit()
        logger.warning(
            "[TokenService] Refresh token reuse detected for user_id=%s; "
            "revoked %s token(s) in family %s",
            token.user_id,
            revoked,
            token.family_id,
        )
        raise CredentialsException

    user = db.query(User).filter(User.id == token.user_id).first()
    if user is None or not user.is_active:
        db.rollback()
        raise CredentialsException

    refresh_token = _issue_refresh_token(db, user.id, family_id=token.family_id)
    db.commit()
    return _token_pair(create_access_token(subject=user.id), refresh_token)


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    """
    Log out: revoke the presented token's whole family.
    Unknown tokens are ignored so logout never reveals which tokens exist.
    """
    token = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == hash_secret(raw_token))
        .first()
    )
    if token is None:
        return
    _revoke_family(db, token.family_id, datetime.now(UTC))
    db.commit()
