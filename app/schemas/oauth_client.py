from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.core.scopes import ALL_SCOPES, parse_scope


class OAuthClientCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, examples=["churn-pipeline"])
    scopes: list[str] = Field(
        ...,
        min_length=1,
        description="Least privilege: grant only what the client needs",
        examples=[["predictions:write"]],
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, value: list[str]) -> list[str]:
        unknown = set(value) - ALL_SCOPES
        if unknown:
            raise ValueError(
                f"unknown scope(s): {', '.join(sorted(unknown))}; "
                f"allowed: {', '.join(sorted(ALL_SCOPES))}"
            )
        return sorted(set(value))


class OAuthClientResponse(BaseModel):
    """A client as listed later on: never includes the secret."""

    client_id: str
    name: str
    scopes: list[str]
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]
    revoked_at: Optional[datetime]

    model_config = {"from_attributes": True}

    @field_validator("scopes", mode="before")
    @classmethod
    def split_scopes(cls, value):
        return sorted(parse_scope(value)) if isinstance(value, str) else value


class OAuthClientWithSecret(OAuthClientResponse):
    """Returned once, on create and on secret rotation."""

    client_secret: str = Field(
        ..., description="Shown only now. Store it in a secret manager."
    )
