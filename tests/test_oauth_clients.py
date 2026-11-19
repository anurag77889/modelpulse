from fastapi.testclient import TestClient


def _token(client: TestClient, client_id: str, client_secret: str):
    return client.post(
        "/oauth/token",
        data={"grant_type": "client_credentials"},
        auth=(client_id, client_secret),
    )


def _second_user_headers(client: TestClient) -> dict:
    client.post(
        "/auth/register",
        json={
            "email": "other@example.com",
            "username": "otheruser",
            "password": "otherpassword123",
        },
    )
    response = client.post(
        "/auth/login",
        json={"email": "other@example.com", "password": "otherpassword123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


class TestCreateClient:
    def test_create_returns_secret_once(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/oauth/clients",
            json={"name": "churn-pipeline", "scopes": ["predictions:write"]},
            headers=auth_headers,
        )
        assert response.status_code == 201
        body = response.json()
        assert body["client_id"].startswith("mpc_")
        assert body["client_secret"].startswith("mps_")
        assert body["scopes"] == ["predictions:write"]
        assert body["is_active"] is True

        listed = client.get("/oauth/clients", headers=auth_headers).json()
        assert len(listed) == 1
        assert "client_secret" not in listed[0]
        assert "secret_hash" not in listed[0]

    def test_scopes_deduplicated_and_sorted(
        self, client: TestClient, auth_headers: dict
    ):
        response = client.post(
            "/oauth/clients",
            json={
                "name": "p",
                "scopes": ["predictions:write", "models:read", "models:read"],
            },
            headers=auth_headers,
        )
        assert response.json()["scopes"] == ["models:read", "predictions:write"]

    def test_unknown_scope_rejected(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/oauth/clients",
            json={"name": "p", "scopes": ["admin:everything"]},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_empty_scopes_rejected(self, client: TestClient, auth_headers: dict):
        response = client.post(
            "/oauth/clients",
            json={"name": "p", "scopes": []},
            headers=auth_headers,
        )
        assert response.status_code == 422

    def test_requires_authentication(self, client: TestClient):
        response = client.post(
            "/oauth/clients", json={"name": "p", "scopes": ["models:read"]}
        )
        assert response.status_code == 403


class TestClientIsolation:
    def test_other_users_clients_hidden(
        self, client: TestClient, auth_headers: dict, make_oauth_client
    ):
        creds = make_oauth_client(["models:read"])
        other = _second_user_headers(client)

        assert client.get("/oauth/clients", headers=other).json() == []
        response = client.delete(f"/oauth/clients/{creds['client_id']}", headers=other)
        assert response.status_code == 404
        response = client.post(
            f"/oauth/clients/{creds['client_id']}/rotate-secret", headers=other
        )
        assert response.status_code == 404

    def test_client_token_cannot_manage_clients(self, client: TestClient, client_token):
        """A pipeline's credentials must not be able to mint more credentials."""
        headers = client_token(["models:read", "models:write"])

        response = client.post(
            "/oauth/clients",
            json={"name": "escalate", "scopes": ["models:write"]},
            headers=headers,
        )
        assert response.status_code == 403
        assert client.get("/oauth/clients", headers=headers).status_code == 403


class TestRotateSecret:
    def test_old_secret_stops_working(
        self, client: TestClient, auth_headers: dict, make_oauth_client
    ):
        creds = make_oauth_client(["models:read"])
        response = client.post(
            f"/oauth/clients/{creds['client_id']}/rotate-secret", headers=auth_headers
        )
        assert response.status_code == 200
        new_secret = response.json()["client_secret"]
        assert new_secret != creds["client_secret"]

        assert (
            _token(client, creds["client_id"], creds["client_secret"]).status_code
            == 401
        )
        assert _token(client, creds["client_id"], new_secret).status_code == 200


class TestRevokeClient:
    def test_revoked_client_cannot_get_tokens(
        self, client: TestClient, auth_headers: dict, make_oauth_client
    ):
        creds = make_oauth_client(["models:read"])
        response = client.delete(
            f"/oauth/clients/{creds['client_id']}", headers=auth_headers
        )
        assert response.status_code == 204

        response = _token(client, creds["client_id"], creds["client_secret"])
        assert response.status_code == 401
        assert response.json()["error"] == "invalid_client"

    def test_revocation_rejects_already_issued_token(
        self, client: TestClient, auth_headers: dict, make_oauth_client
    ):
        creds = make_oauth_client(["models:read"])
        token = _token(client, creds["client_id"], creds["client_secret"]).json()
        headers = {"Authorization": f"Bearer {token['access_token']}"}
        assert client.get("/models/", headers=headers).status_code == 200

        client.delete(f"/oauth/clients/{creds['client_id']}", headers=auth_headers)

        assert client.get("/models/", headers=headers).status_code == 401

    def test_revoke_is_idempotent_and_kept_for_audit(
        self, client: TestClient, auth_headers: dict, make_oauth_client
    ):
        creds = make_oauth_client(["models:read"])
        path = f"/oauth/clients/{creds['client_id']}"
        assert client.delete(path, headers=auth_headers).status_code == 204
        assert client.delete(path, headers=auth_headers).status_code == 204

        listed = client.get("/oauth/clients", headers=auth_headers).json()
        assert listed[0]["is_active"] is False
        assert listed[0]["revoked_at"] is not None

    def test_cannot_rotate_revoked_client(
        self, client: TestClient, auth_headers: dict, make_oauth_client
    ):
        creds = make_oauth_client(["models:read"])
        client.delete(f"/oauth/clients/{creds['client_id']}", headers=auth_headers)
        response = client.post(
            f"/oauth/clients/{creds['client_id']}/rotate-secret", headers=auth_headers
        )
        assert response.status_code == 404
