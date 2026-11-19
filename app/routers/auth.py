from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.dependencies import require_user_session
from app.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.schemas.token import RefreshRequest, TokenResponse
from app.schemas.user import UserCreate, UserLogin, UserResponse
from app.services.auth_service import authenticate_user, create_user
from app.services.token_service import (
    issue_user_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _no_store(response: Response) -> None:
    """Tokens must never be cached by browsers or proxies (RFC 6749 §5.1)."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


@router.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("3/minute")
def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    """Register a new user account."""
    user = create_user(db, payload)
    return user


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/minute")
def login(
    request: Request,
    response: Response,
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    """
    Login and receive a short-lived access token plus a refresh token.
    The access token carries every scope.
    """
    user = authenticate_user(db, payload.email, payload.password)
    _no_store(response)
    return issue_user_tokens(db, user)


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Exchange a refresh token for a new access + refresh token pair.
    Each refresh token works once; reusing one logs the session out.
    """
    _no_store(response)
    return rotate_refresh_token(db, payload.refresh_token)


@router.post("/logout", status_code=204)
@limiter.limit("10/minute")
def logout(request: Request, payload: RefreshRequest, db: Session = Depends(get_db)):
    """
    Revoke the session the refresh token belongs to.
    Access tokens already issued stay valid until they expire (max 15 min).
    """
    revoke_refresh_token(db, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(require_user_session)):
    """
    Get the logged-in user's profile.
    Machine client tokens are refused: a pipeline scoped to e.g.
    predictions:write has no business reading its owner's email.
    """
    return current_user
