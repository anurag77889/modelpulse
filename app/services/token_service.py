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


def _within_reuse_grace(token: RefreshToken, now: datetime) -> bool:
    """True if `token` was used so recently that a second presentation is
    most likely a client retry or double-submit, not a stolen copy."""
    if settings.REFRESH_REUSE_GRACE_SECONDS <= 0:
        # Strict mode. Checked first: two racing requests read the clock a
        # few microseconds apart, so the loser's "age" can come out negative
        # and would otherwise slip under a grace of zero.
        return False
    grace = timedelta(seconds=settings.REFRESH_REUSE_GRACE_SECONDS)
    return token.used_at is not None and now - token.used_at <= grace


def issue_user_tokens(db: Session, user: User) -> dict:
    """Start a new session: access token plus the first refresh token."""
    refresh_token = _issue_refresh_token(db, user.id, family_id=uuid.uuid4().hex)
    db.commit()
    return _token_pair(create_access_token(subject=user.id), refresh_token)


def rotate_refresh_token(db: Session, raw_token: str) -> dict:
    """
    Exchange a refresh token for a new access + refresh token pair.

    The presented token is marked used. If it comes back after the grace
    window (REFRESH_REUSE_GRACE_SECONDS), someone else holds a copy, so
    every token in its family is revoked and the caller must log in again.

    Inside the grace window a repeat is treated as a retry (a lost
    response, two tabs refreshing together): it is given its own new
    token in the same family. Tradeoff: for those few seconds a stolen
    copy of the old token also works, but after that the usual reuse
    detection applies to every token in the family.
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
        # Lost the race, or the token was used or revoked earlier. Re-read
        # it: our copy was loaded before the competing request committed.
        db.refresh(token)
        if token.revoked_at is not None:
            raise CredentialsException

        if not _within_reuse_grace(token, now):
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

        logger.info(
            "[TokenService] Refresh token re-presented within %ss grace for "
            "user_id=%s; issuing a sibling token in family %s",
            settings.REFRESH_REUSE_GRACE_SECONDS,
            token.user_id,
            token.family_id,
        )

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
