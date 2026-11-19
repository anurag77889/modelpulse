from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Returned by login and refresh."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Access token lifetime in seconds")
    refresh_token: str = Field(
        ...,
        description="Single-use; exchange at /auth/refresh for a new pair",
    )


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class ClientTokenResponse(BaseModel):
    """RFC 6749 §5.1 response for the client credentials grant."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    scope: str
