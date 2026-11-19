import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import NotFoundException
from app.core.scopes import format_scope, parse_scope
from app.core.security import (
    create_access_token,
    generate_secret,
    hash_secret,
    verify_secret,
)
from app.models.oauth_client import OAuthClient
from app.models.user import User
from app.schemas.oauth_client import OAuthClientCreate

logger = logging.getLogger(__name__)

CLIENT_ID_PREFIX = "mpc_"
CLIENT_SECRET_PREFIX = "mps_"


class OAuthError(Exception):
    """An RFC 6749 §5.2 token endpoint error."""

    def __init__(self, error: str, description: str, status_code: int = 400):
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(description)


def create_client(db: Session, payload: OAuthClientCreate, owner_id: int):
    """
    Register a machine client. Returns (client, raw_secret); the raw
    secret is never stored and can't be retrieved again.
    """
    raw_secret = generate_secret(CLIENT_SECRET_PREFIX)
    client = OAuthClient(
        client_id=f"{CLIENT_ID_PREFIX}{secrets.token_hex(12)}",
        secret_hash=hash_secret(raw_secret),
        name=payload.name,
        scopes=format_scope(set(payload.scopes)),
        owner_id=owner_id,
    )
    db.add(client)
    db.commit()
    db.refresh(client)
    logger.info(
        "[OAuthClient] Created %s for user_id=%s scopes=%s",
        client.client_id,
        owner_id,
        client.scopes,
    )
    return client, raw_secret


def list_clients(db: Session, owner_id: int) -> list[OAuthClient]:
    return (
        db.query(OAuthClient)
        .filter(OAuthClient.owner_id == owner_id)
        .order_by(OAuthClient.created_at.desc())
        .all()
    )


def get_client_for_owner(db: Session, client_id: str, owner_id: int) -> OAuthClient:
    """404 for clients that don't exist or belong to someone else, so
    client ids can't be probed across accounts."""
    client = (
        db.query(OAuthClient)
        .filter(OAuthClient.client_id == client_id, OAuthClient.owner_id == owner_id)
        .first()
    )
    if client is None:
        raise NotFoundException
    return client


def rotate_client_secret(db: Session, client_id: str, owner_id: int):
    """
    Replace a client's secret. The old secret stops working at once;
    tokens already issued remain valid until they expire.
    """
    client = get_client_for_owner(db, client_id, owner_id)
    if not client.is_active:
        raise NotFoundException
    raw_secret = generate_secret(CLIENT_SECRET_PREFIX)
    client.secret_hash = hash_secret(raw_secret)
    db.commit()
    db.refresh(client)
    logger.info("[OAuthClient] Rotated secret for %s", client.client_id)
    return client, raw_secret


def revoke_client(db: Session, client_id: str, owner_id: int) -> None:
    """
    Deactivate a client. Its secret stops working and every token it
    already holds is rejected on the next request. The row is kept for
    auditing. Idempotent.
    """
    client = get_client_for_owner(db, client_id, owner_id)
    if client.is_active:
        client.is_active = False
        client.revoked_at = datetime.now(UTC)
        db.commit()
        logger.info("[OAuthClient] Revoked %s", client.client_id)


def issue_client_token(
    db: Session,
    client_id: str,
    client_secret: str,
    requested_scope: str | None,
) -> dict:
    """
    Client credentials grant (RFC 6749 §4.4): authenticate the client
    and issue an access token carrying the granted scopes.
    No refresh token is issued; the client simply requests a new token.
    """
    client = (
        db.query(OAuthClient)
        .join(User, User.id == OAuthClient.owner_id)
        .filter(
            OAuthClient.client_id == client_id,
            OAuthClient.is_active.is_(True),
            User.is_active.is_(True),
        )
        .first()
    )
    # Same error for unknown, revoked, and wrong-secret, so nothing
    # reveals which client ids exist.
    if client is None or not verify_secret(client_secret, client.secret_hash):
        raise OAuthError("invalid_client", "Client authentication failed", 401)

    allowed = parse_scope(client.scopes)
    requested = parse_scope(requested_scope)
    if requested and not requested <= allowed:
        raise OAuthError(
            "invalid_scope",
            "Requested scope exceeds the scopes granted to this client",
        )
    granted = requested or allowed

    client.last_used_at = datetime.now(UTC)
    db.commit()

    expires = timedelta(minutes=settings.CLIENT_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(
            subject=client.owner_id,
            expires_delta=expires,
            scopes=granted,
            client_id=client.client_id,
        ),
        "token_type": "Bearer",
        "expires_in": int(expires.total_seconds()),
        "scope": format_scope(granted),
    }
