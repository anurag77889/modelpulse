from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.core.scopes import ALL_SCOPES
from app.core.security import create_access_token
from app.models.refresh_token import RefreshToken
from app.models.user import User
from tests.conftest import TestingSessionLocal

LOGIN = {"email": "test@example.com", "password": "testpassword123"}


def _login(client: TestClient) -> dict:
    response = client.post("/auth/login", json=LOGIN)
    assert response.status_code == 200
    return response.json()


def _refresh(client: TestClient, refresh_token: str):
    return client.post("/auth/refresh", json={"refresh_token": refresh_token})


class TestLoginTokens:
    def test_login_returns_access_and_refresh(
        self, client: TestClient, registered_user: dict
    ):
        response = client.post("/auth/login", json=LOGIN)
        body = response.json()

        assert body["token_type"] == "bearer"
        assert body["expires_in"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        assert body["refresh_token"].startswith("mpr_")
        assert response.headers["cache-control"] == "no-store"

    def test_user_access_token_claims(self, client: TestClient, registered_user: dict):
        claims = jwt.get_unverified_claims(_login(client)["access_token"])

        assert claims["sub"] == str(registered_user["id"])
        assert claims["iss"] == settings.JWT_ISSUER
        assert claims["aud"] == settings.JWT_AUDIENCE
        assert claims["typ"] == "access"
        assert claims["jti"]
        assert set(claims["scope"].split()) == ALL_SCOPES
        assert "client_id" not in claims

    def test_refresh_token_stored_only_as_hash(
        self, client: TestClient, registered_user: dict
    ):
        raw = _login(client)["refresh_token"]
        db = TestingSessionLocal()
        try:
            stored = db.query(RefreshToken).one()
            assert stored.token_hash != raw
            assert raw not in stored.token_hash
        finally:
            db.close()


class TestRefreshRotation:
    def test_refresh_issues_new_pair(self, client: TestClient, registered_user: dict):
        first = _login(client)
        response = _refresh(client, first["refresh_token"])

        assert response.status_code == 200
        second = response.json()
        assert second["refresh_token"] != first["refresh_token"]
        assert second["access_token"] != first["access_token"]
        assert response.headers["cache-control"] == "no-store"

        me = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {second['access_token']}"}
        )
        assert me.status_code == 200

    def test_refresh_token_is_single_use(
        self, client: TestClient, registered_user: dict
    ):
        first = _login(client)
        assert _refresh(client, first["refresh_token"]).status_code == 200
        assert _refresh(client, first["refresh_token"]).status_code == 401

    def test_reuse_revokes_whole_family(
        self, client: TestClient, registered_user: dict
    ):
        """Regression guard for stolen tokens: once an old token is replayed,
        the legitimate holder's newer token must stop working too."""
        first = _login(client)
        second = _refresh(client, first["refresh_token"]).json()

        assert _refresh(client, first["refresh_token"]).status_code == 401  # replay
        assert _refresh(client, second["refresh_token"]).status_code == 401

    def test_reuse_does_not_affect_other_sessions(
        self, client: TestClient, registered_user: dict
    ):
        session_a = _login(client)
        session_b = _login(client)
        _refresh(client, session_a["refresh_token"])
        _refresh(client, session_a["refresh_token"])  # replay kills session A

        assert _refresh(client, session_b["refresh_token"]).status_code == 200

    def test_unknown_token_rejected(self, client: TestClient):
        assert _refresh(client, "mpr_not-a-real-token").status_code == 401

    def test_expired_token_rejected(self, client: TestClient, registered_user: dict):
        raw = _login(client)["refresh_token"]
        db = TestingSessionLocal()
        try:
            db.query(RefreshToken).update(
                {"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
            )
            db.commit()
        finally:
            db.close()

        assert _refresh(client, raw).status_code == 401

    def test_inactive_user_cannot_refresh(
        self, client: TestClient, registered_user: dict
    ):
        raw = _login(client)["refresh_token"]
        db = TestingSessionLocal()
        try:
            db.query(User).update({"is_active": False})
            db.commit()
        finally:
            db.close()

        assert _refresh(client, raw).status_code == 401

    def test_empty_body_rejected(self, client: TestClient):
        assert client.post("/auth/refresh", json={}).status_code == 422


class TestLogout:
    def test_logout_revokes_session(self, client: TestClient, registered_user: dict):
        first = _login(client)
        second = _refresh(client, first["refresh_token"]).json()

        response = client.post(
            "/auth/logout", json={"refresh_token": second["refresh_token"]}
        )
        assert response.status_code == 204
        assert _refresh(client, second["refresh_token"]).status_code == 401

    def test_logout_unknown_token_is_silent(self, client: TestClient):
        response = client.post("/auth/logout", json={"refresh_token": "mpr_nope"})
        assert response.status_code == 204


class TestTokenTypeConfusion:
    def test_refresh_token_is_not_an_access_token(
        self, client: TestClient, registered_user: dict
    ):
        raw = _login(client)["refresh_token"]
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {raw}"})
        assert response.status_code == 401

    def test_access_token_is_not_a_refresh_token(
        self, client: TestClient, registered_user: dict
    ):
        access = _login(client)["access_token"]
        assert _refresh(client, access).status_code == 401

    def test_wrong_audience_rejected(self, client: TestClient, registered_user: dict):
        token = jwt.encode(
            {
                "iss": settings.JWT_ISSUER,
                "aud": "some-other-api",
                "sub": str(registered_user["id"]),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
                "jti": "x",
                "typ": "access",
                "scope": "models:read",
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        response = client.get("/models/", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_legacy_token_without_claims_rejected(
        self, client: TestClient, registered_user: dict
    ):
        """Tokens minted before this change (only sub/exp/iat) are refused."""
        token = jwt.encode(
            {
                "sub": str(registered_user["id"]),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401

    def test_non_numeric_subject_rejected(self, client: TestClient):
        token = create_access_token(subject="not-a-number")
        response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
