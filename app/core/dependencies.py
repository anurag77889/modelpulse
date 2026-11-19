from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import (
    CredentialsException,
    InactiveUserException,
    UserSessionRequiredException,
)
from app.core.scopes import format_scope, parse_scope
from app.core.security import decode_access_token
from app.database import get_db
from app.models.oauth_client import OAuthClient
from app.models.user import User

# Extracts Bearer token from the Authorization header
bearer_scheme = HTTPBearer()


@dataclass(frozen=True)
class AuthContext:
    """Who is calling: the user acted for, granted scopes, and the
    machine client if the token came from the client credentials grant."""

    user: User
    scopes: frozenset[str]
    client_id: Optional[str] = None

    @property
    def is_client(self) -> bool:
        return self.client_id is not None


def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    """
    Decodes the access token, loads the user, and for machine-client
    tokens confirms the client is still active, so revoking a client
    takes effect immediately instead of when its token expires.
    Raises 401 if the token is missing, invalid, expired, or revoked.
    """
    payload = decode_access_token(credentials.credentials)
    if payload is None:
        raise CredentialsException

    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError):
        raise CredentialsException

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise CredentialsException

    if not user.is_active:
        raise InactiveUserException

    client_id = payload.get("client_id")
    if client_id is not None:
        client = (
            db.query(OAuthClient)
            .filter(
                OAuthClient.client_id == client_id,
                OAuthClient.owner_id == user.id,
                OAuthClient.is_active.is_(True),
            )
            .first()
        )
        if client is None:
            raise CredentialsException

    return AuthContext(
        user=user,
        scopes=frozenset(parse_scope(payload.get("scope"))),
        client_id=client_id,
    )


def get_current_user(auth: AuthContext = Depends(get_auth_context)) -> User:
    """
    Dependency for routes any valid access token may call.
    Use require_scopes() for routes that touch protected resources.
    """
    return auth.user


def require_scopes(*required: str):
    """
    Build a dependency that admits the caller only if its token carries
    every scope in `required`, and returns the user it acts for.
    Responds 403 insufficient_scope (RFC 6750 §3.1) otherwise.
    """
    needed = frozenset(required)

    def dependency(auth: AuthContext = Depends(get_auth_context)) -> User:
        if not needed <= auth.scopes:
            scope = format_scope(needed)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Token is missing required scope(s): {scope}",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer error="insufficient_scope", scope="{scope}"'
                    )
                },
            )
        return auth.user

    return dependency


def require_user_session(auth: AuthContext = Depends(get_auth_context)) -> User:
    """
    Admit only tokens from a user login, not machine clients.
    A pipeline's credentials must never be able to mint more credentials.
    """
    if auth.is_client:
        raise UserSessionRequiredException
    return auth.user


def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Use this dependency for admin-only routes.
    """
    if not current_user.is_superuser:
        from app.core.exceptions import ForbiddenException

        raise ForbiddenException
    return current_user
