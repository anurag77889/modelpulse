from fastapi.testclient import TestClient
from jose import jwt

from app.config import settings


def _token(client: TestClient, creds: dict, **data):
    return client.post(
        "/oauth/token",
        data={"grant_type": "client_credentials", **data},
        auth=(creds["client_id"], creds["client_secret"]),
    )


class TestClientCredentialsGrant:
    def test_basic_auth_success(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read", "predictions:write"])
        response = _token(client, creds)

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "Bearer"
        assert body["expires_in"] == settings.CLIENT_TOKEN_EXPIRE_MINUTES * 60
        assert body["scope"] == "models:read predictions:write"
        assert "refresh_token" not in body  # RFC 6749 §4.4.3
        assert response.headers["cache-control"] == "no-store"

    def test_body_credentials_success(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read"])
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            },
        )
        assert response.status_code == 200

    def test_token_claims(self, client: TestClient, make_oauth_client, registered_user):
        creds = make_oauth_client(["predictions:write"])
        token = _token(client, creds).json()["access_token"]
        claims = jwt.get_unverified_claims(token)

        assert claims["sub"] == str(registered_user["id"])
        assert claims["client_id"] == creds["client_id"]
        assert claims["scope"] == "predictions:write"
        assert claims["iss"] == settings.JWT_ISSUER
        assert claims["aud"] == settings.JWT_AUDIENCE
        assert claims["typ"] == "access"

    def test_scope_can_be_narrowed(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read", "predictions:write"])
        response = _token(client, creds, scope="models:read")
        assert response.status_code == 200
        assert response.json()["scope"] == "models:read"

    def test_scope_beyond_grant_rejected(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read"])
        response = _token(client, creds, scope="models:read models:write")
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_scope"


class TestTokenEndpointErrors:
    def test_wrong_secret(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read"])
        response = client.post(
            "/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=(creds["client_id"], "mps_wrong"),
        )
        assert response.status_code == 401
        assert response.json() == {
            "error": "invalid_client",
            "error_description": "Client authentication failed",
        }
        assert response.headers["www-authenticate"].startswith("Basic")

    def test_unknown_client_same_error_as_wrong_secret(self, client: TestClient):
        response = client.post(
            "/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=("mpc_doesnotexist", "mps_whatever"),
        )
        assert response.status_code == 401
        assert response.json()["error_description"] == "Client authentication failed"

    def test_missing_grant_type(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read"])
        response = client.post(
            "/oauth/token", data={}, auth=(creds["client_id"], creds["client_secret"])
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"

    def test_unsupported_grant_type(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read"])
        response = client.post(
            "/oauth/token",
            data={"grant_type": "password", "username": "x", "password": "y"},
            auth=(creds["client_id"], creds["client_secret"]),
        )
        assert response.status_code == 400
        assert response.json()["error"] == "unsupported_grant_type"

    def test_two_auth_methods_rejected(self, client: TestClient, make_oauth_client):
        creds = make_oauth_client(["models:read"])
        response = client.post(
            "/oauth/token",
            data={
                "grant_type": "client_credentials",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
            },
            auth=(creds["client_id"], creds["client_secret"]),
        )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"

    def test_no_client_authentication(self, client: TestClient):
        response = client.post(
            "/oauth/token", data={"grant_type": "client_credentials"}
        )
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_client"

    def test_malformed_basic_header(self, client: TestClient):
        response = client.post(
            "/oauth/token",
            data={"grant_type": "client_credentials"},
            headers={"Authorization": "Basic !!!not-base64"},
        )
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_client"

    def test_inactive_owner_cannot_get_tokens(
        self, client: TestClient, make_oauth_client
    ):
        from app.models.user import User
        from tests.conftest import TestingSessionLocal

        creds = make_oauth_client(["models:read"])
        db = TestingSessionLocal()
        try:
            db.query(User).update({"is_active": False})
            db.commit()
        finally:
            db.close()

        assert _token(client, creds).status_code == 401


class TestScopeEnforcement:
    def test_write_only_client_can_log_predictions(
        self, client: TestClient, registered_model: dict, client_token
    ):
        headers = client_token(["predictions:write"])
        response = client.post(
            f"/models/{registered_model['id']}/predictions/",
            json={
                "input_data": {"age": 30},
                "prediction_output": {"label": "stay"},
                "confidence_score": 0.9,
            },
            headers=headers,
        )
        assert response.status_code == 201

    def test_write_only_client_cannot_read(
        self, client: TestClient, registered_model: dict, client_token
    ):
        headers = client_token(["predictions:write"])
        model_id = registered_model["id"]

        for path in (
            "/models/",
            f"/models/{model_id}",
            f"/models/{model_id}/predictions/",
            f"/models/{model_id}/alerts/",
        ):
            response = client.get(path, headers=headers)
            assert response.status_code == 403, path

        response = client.delete(f"/models/{model_id}", headers=headers)
        assert response.status_code == 403

    def test_insufficient_scope_response(
        self, client: TestClient, registered_model: dict, client_token
    ):
        headers = client_token(["predictions:write"])
        response = client.get("/models/", headers=headers)

        assert response.status_code == 403
        challenge = response.headers["www-authenticate"]
        assert 'error="insufficient_scope"' in challenge
        assert 'scope="models:read"' in challenge

    def test_every_resource_route_requires_its_scope(
        self, client: TestClient, registered_model: dict, client_token
    ):
        """A token with only an unrelated scope gets 403 on every route."""
        headers = client_token(["alerts:write"])
        model_id = registered_model["id"]
        routes = [
            ("GET", "/models/"),
            ("POST", "/models/"),
            ("GET", f"/models/{model_id}"),
            ("PATCH", f"/models/{model_id}"),
            ("DELETE", f"/models/{model_id}"),
            ("GET", f"/models/{model_id}/summary"),
            ("GET", f"/models/{model_id}/predictions/"),
            ("POST", f"/models/{model_id}/predictions/"),
            ("GET", f"/models/{model_id}/predictions/stats"),
            ("GET", f"/models/{model_id}/predictions/1"),
            ("PATCH", f"/models/{model_id}/predictions/1/label"),
            ("GET", f"/models/{model_id}/alerts/"),
            ("GET", f"/models/{model_id}/alerts/stats"),
            ("GET", f"/models/{model_id}/alerts/1"),
        ]
        for method, path in routes:
            response = client.request(method, path, headers=headers, json={})
            assert response.status_code == 403, (method, path, response.text)

    def test_client_acts_only_for_its_owner(
        self, client: TestClient, registered_model: dict
    ):
        """A client of user B can't reach user A's model even with the scope."""
        client.post(
            "/auth/register",
            json={
                "email": "b@example.com",
                "username": "userb",
                "password": "userbpassword1",
            },
        )
        login = client.post(
            "/auth/login",
            json={"email": "b@example.com", "password": "userbpassword1"},
        ).json()
        b_headers = {"Authorization": f"Bearer {login['access_token']}"}
        creds = client.post(
            "/oauth/clients",
            json={"name": "b-pipeline", "scopes": ["models:read"]},
            headers=b_headers,
        ).json()
        token = _token(client, creds).json()["access_token"]

        response = client.get(
            f"/models/{registered_model['id']}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code in (403, 404)

    def test_me_rejects_client_tokens(
        self, client: TestClient, client_token, registered_user: dict
    ):
        """A pipeline scoped to e.g. predictions:write must not be able to
        read its owner's email and username."""
        for scopes in (["models:read"], ["predictions:write"]):
            response = client.get("/auth/me", headers=client_token(scopes))
            assert response.status_code == 403
            assert registered_user["email"] not in response.text

    def test_me_still_works_for_user_logins(
        self, client: TestClient, auth_headers: dict, registered_user: dict
    ):
        response = client.get("/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == registered_user["id"]
