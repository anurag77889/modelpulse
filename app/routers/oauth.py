import base64
import binascii
from typing import Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import require_user_session
from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.schemas.oauth_client import (
    OAuthClientCreate,
    OAuthClientResponse,
    OAuthClientWithSecret,
)
from app.schemas.token import ClientTokenResponse
from app.services.oauth_client_service import (
    OAuthError,
    create_client,
    issue_client_token,
    list_clients,
    revoke_client,
    rotate_client_secret,
)

router = APIRouter(prefix="/oauth", tags=["OAuth 2.0"])

NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


def _oauth_error(err: OAuthError, used_basic_auth: bool) -> JSONResponse:
    """RFC 6749 §5.2 error body, not FastAPI's usual {"detail": ...}."""
    headers = dict(NO_STORE)
    if err.status_code == 401 and used_basic_auth:
        headers["WWW-Authenticate"] = 'Basic realm="modelpulse"'
    return JSONResponse(
        status_code=err.status_code,
        content={"error": err.error, "error_description": err.description},
        headers=headers,
    )


def _basic_credentials(request: Request) -> Optional[tuple[str, str]]:
    """
    Decode client_secret_basic credentials (RFC 6749 §2.3.1).
    Returns None when no Basic header is present.
    """
    header = request.headers.get("Authorization", "")
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        raise OAuthError("invalid_client", "Malformed Basic credentials", 401)
    client_id, sep, client_secret = decoded.partition(":")
    if not sep:
        raise OAuthError("invalid_client", "Malformed Basic credentials", 401)
    # Both parts are form-urlencoded before being Base64-encoded
    return unquote(client_id), unquote(client_secret)


@router.post(
    "/token",
    response_model=ClientTokenResponse,
    responses={400: {"description": "RFC 6749 error"}, 401: {"description": ""}},
)
@limiter.limit("20/minute")
def token(
    request: Request,
    grant_type: Optional[str] = Form(default=None),
    scope: Optional[str] = Form(default=None),
    client_id: Optional[str] = Form(default=None),
    client_secret: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    """
    OAuth 2.0 token endpoint: **client credentials grant** (RFC 6749 §4.4).

    Send `application/x-www-form-urlencoded` with `grant_type=client_credentials`
    and authenticate with HTTP Basic (`client_id:client_secret`) or with
    `client_id` + `client_secret` in the body. Optionally narrow the token
    with `scope` (space-delimited, must be a subset of the client's scopes).
    """
    basic = None
    try:
        basic = _basic_credentials(request)

        if grant_type is None:
            raise OAuthError("invalid_request", "Missing grant_type")
        if grant_type != "client_credentials":
            raise OAuthError(
                "unsupported_grant_type",
                "Only grant_type=client_credentials is supported here",
            )

        body_creds = client_id is not None or client_secret is not None
        if basic and body_creds:
            raise OAuthError(
                "invalid_request", "Use exactly one client authentication method"
            )
        if basic:
            cid, secret = basic
        elif client_id and client_secret:
            cid, secret = client_id, client_secret
        else:
            raise OAuthError("invalid_client", "Client authentication required", 401)

        result = issue_client_token(db, cid, secret, scope)
    except OAuthError as err:
        return _oauth_error(err, used_basic_auth=basic is not None)

    return JSONResponse(content=result, headers=NO_STORE)


@router.post("/clients", response_model=OAuthClientWithSecret, status_code=201)
def create_client_route(
    payload: OAuthClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_session),
):
    """
    Register a machine client (e.g. an ML pipeline).
    **The `client_secret` is shown only in this response.**
    """
    client, secret = create_client(db, payload, owner_id=current_user.id)
    return OAuthClientWithSecret.model_validate(
        {
            **OAuthClientResponse.model_validate(client).model_dump(),
            "client_secret": secret,
        }
    )


@router.get("/clients", response_model=list[OAuthClientResponse])
def list_clients_route(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_session),
):
    """List your machine clients, including revoked ones. Secrets are never shown."""
    return list_clients(db, owner_id=current_user.id)


@router.post("/clients/{client_id}/rotate-secret", response_model=OAuthClientWithSecret)
def rotate_secret_route(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_session),
):
    """
    Issue a new secret; the old one stops working immediately.
    **The new `client_secret` is shown only in this response.**
    """
    client, secret = rotate_client_secret(db, client_id, owner_id=current_user.id)
    return OAuthClientWithSecret.model_validate(
        {
            **OAuthClientResponse.model_validate(client).model_dump(),
            "client_secret": secret,
        }
    )


@router.delete("/clients/{client_id}", status_code=204)
def revoke_client_route(
    client_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_user_session),
):
    """
    Revoke a client. Its secret stops working and any access token it
    holds is rejected on the next request.
    """
    revoke_client(db, client_id, owner_id=current_user.id)
