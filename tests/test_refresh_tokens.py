import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings
from app.core.scopes import ALL_SCOPES
from app.core.security import create_access_token
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.token_service import rotate_refresh_token
from tests.conftest import TestingSessionLocal

LOGIN = {"email": "test@example.com", "password": "testpassword123"}


def _login(client: TestClient) -> dict:
    response = client.post("/auth/login", json=LOGIN)
    assert response.status_code == 200
    return response.json()


def _refresh(client: TestClient, refresh_token: str):
    return client.post("/auth/refresh", json={"refresh_token": refresh_token})


def _age_used_tokens(seconds: float) -> None:
    """Pretend every used refresh token was used `seconds` ago, to step
    past the reuse grace window without sleeping."""
    db = TestingSessionLocal()
    try:
        db.query(RefreshToken).filter(RefreshToken.used_at.is_not(None)).update(
            {"used_at": datetime.now(UTC) - timedelta(seconds=seconds)}
        )
        db.commit()
    finally:
        db.close()


PAST_GRACE = settings.REFRESH_REUSE_GRACE_SECONDS + 5


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
        _age_used_tokens(PAST_GRACE)
        assert _refresh(client, first["refresh_token"]).status_code == 401

    def test_reuse_revokes_whole_family(
        self, client: TestClient, registered_user: dict
    ):
        """Regression guard for stolen tokens: once an old token is replayed,
        the legitimate holder's newer token must stop working too."""
        first = _login(client)
        second = _refresh(client, first["refresh_token"]).json()
        _age_used_tokens(PAST_GRACE)

        assert _refresh(client, first["refresh_token"]).status_code == 401  # replay
        assert _refresh(client, second["refresh_token"]).status_code == 401

    def test_reuse_does_not_affect_other_sessions(
        self, client: TestClient, registered_user: dict
    ):
        session_a = _login(client)
        session_b = _login(client)
        _refresh(client, session_a["refresh_token"])
        _age_used_tokens(PAST_GRACE)
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


class TestReuseGraceWindow:
    def test_replay_within_grace_gets_a_sibling_token(
        self, client: TestClient, registered_user: dict
    ):
        """A retry after a lost response must not log the user out."""
        first = _login(client)
        a = _refresh(client, first["refresh_token"])
        b = _refresh(client, first["refresh_token"])  # immediate retry

        assert a.status_code == 200 and b.status_code == 200
        assert a.json()["refresh_token"] != b.json()["refresh_token"]
        for pair in (a.json(), b.json()):
            me = client.get(
                "/auth/me",
                headers={"Authorization": f"Bearer {pair['access_token']}"},
            )
            assert me.status_code == 200

    def test_both_branches_stay_usable(self, client: TestClient, registered_user: dict):
        first = _login(client)
        a = _refresh(client, first["refresh_token"]).json()
        b = _refresh(client, first["refresh_token"]).json()

        assert _refresh(client, a["refresh_token"]).status_code == 200
        assert _refresh(client, b["refresh_token"]).status_code == 200

    def test_grace_window_expires(self, client: TestClient, registered_user: dict):
        first = _login(client)
        a = _refresh(client, first["refresh_token"]).json()
        _age_used_tokens(PAST_GRACE)

        assert _refresh(client, first["refresh_token"]).status_code == 401
        # reuse after the window is theft: the whole family dies
        assert _refresh(client, a["refresh_token"]).status_code == 401

    def test_zero_grace_makes_reuse_strict(
        self, client: TestClient, registered_user: dict, monkeypatch
    ):
        monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", 0)
        first = _login(client)
        a = _refresh(client, first["refresh_token"]).json()

        assert _refresh(client, first["refresh_token"]).status_code == 401
        assert _refresh(client, a["refresh_token"]).status_code == 401

    def test_grace_never_revives_a_revoked_session(
        self, client: TestClient, registered_user: dict
    ):
        first = _login(client)
        second = _refresh(client, first["refresh_token"]).json()
        client.post("/auth/logout", json={"refresh_token": second["refresh_token"]})

        # `first` was used moments ago, but its session has been logged out
        assert _refresh(client, first["refresh_token"]).status_code == 401


class TestConcurrentRotation:
    """Two requests presenting the same refresh token at the same instant,
    each on its own database session (as separate workers would be)."""

    def _race(self, raw_token: str) -> list:
        barrier = threading.Barrier(2)

        def attempt():
            db = TestingSessionLocal()
            try:
                barrier.wait(timeout=10)
                return rotate_refresh_token(db, raw_token)
            except HTTPException as exc:
                return exc
            finally:
                db.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(attempt), pool.submit(attempt)]
            return [f.result(timeout=30) for f in futures]

    def test_strict_mode_lets_exactly_one_request_win(
        self, client: TestClient, registered_user: dict, monkeypatch
    ):
        monkeypatch.setattr(settings, "REFRESH_REUSE_GRACE_SECONDS", 0)
        results = self._race(_login(client)["refresh_token"])

        winners = [r for r in results if isinstance(r, dict)]
        losers = [r for r in results if isinstance(r, HTTPException)]
        assert len(winners) == 1
        assert len(losers) == 1
        assert losers[0].status_code == 401

    def test_grace_mode_serves_both_with_distinct_tokens(
        self, client: TestClient, registered_user: dict
    ):
        results = self._race(_login(client)["refresh_token"])

        assert all(isinstance(r, dict) for r in results)
        assert results[0]["refresh_token"] != results[1]["refresh_token"]


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
