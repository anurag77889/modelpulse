import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.config import settings
from app.limiter import client_ip


def make_request(forwarded_for: str | None = None) -> Request:
    headers = []
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": ("10.0.0.99", 12345),
        }
    )


class TestClientIp:
    @pytest.fixture(autouse=True)
    def one_trusted_proxy(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 1)

    def test_uses_address_appended_by_proxy(self):
        assert client_ip(make_request("203.0.113.7")) == "203.0.113.7"

    def test_ignores_client_supplied_entries(self):
        """Regression: the leftmost entry is attacker-controlled."""
        request = make_request("6.6.6.6, 1.2.3.4, 203.0.113.7")
        assert client_ip(request) == "203.0.113.7"

    def test_falls_back_to_peer_without_header(self):
        assert client_ip(make_request()) == "10.0.0.99"

    def test_two_proxies_take_second_from_right(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 2)
        request = make_request("6.6.6.6, 203.0.113.7, 10.1.1.1")
        assert client_ip(request) == "203.0.113.7"

    def test_falls_back_when_fewer_entries_than_proxies(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 2)
        assert client_ip(make_request("203.0.113.7")) == "10.0.0.99"

    def test_zero_proxies_ignores_header(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 0)
        assert client_ip(make_request("203.0.113.7")) == "10.0.0.99"


class TestRegistrationRateLimit:
    def test_register_within_limits(
        self,
        client: TestClient,
        enable_rate_limiting: dict,
    ):
        for i in range(3):
            response = client.post(
                "/auth/register",
                json={
                    "email": f"user{i}@example.com",
                    "username": f"user{i}",
                    "password": f"password12{i}",
                },
            )
            assert response.status_code == 201

    def test_register_exceeds_limit(
        self,
        client: TestClient,
        enable_rate_limiting: dict,
    ):
        for i in range(4):
            response = client.post(
                "/auth/register",
                json={
                    "email": f"user{i}@example.com",
                    "username": f"user{i}",
                    "password": f"password12{i}",
                },
            )
            if i < 3:
                assert response.status_code == 201
            else:
                assert response.status_code == 429


class TestLoginRateLimit:
    def test_login_within_limits(
        self,
        client: TestClient,
        auth_headers: dict,
        enable_rate_limiting: dict,
        registered_user: dict,
    ):
        for i in range(5):
            response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )
            assert response.status_code == 200

    def test_login_exceeds_limit(
        self,
        client: TestClient,
        auth_headers: dict,
        enable_rate_limiting: dict,
        registered_user: dict,
    ):
        for i in range(6):
            response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
            )

            if i < 5:
                assert response.status_code == 200
            else:
                assert response.status_code == 429


class TestForwardedForSpoofing:
    @pytest.fixture(autouse=True)
    def one_trusted_proxy(self, monkeypatch):
        monkeypatch.setattr(settings, "TRUSTED_PROXY_COUNT", 1)

    def test_spoofed_entries_do_not_bypass_login_limit(
        self,
        client: TestClient,
        auth_headers: dict,
        enable_rate_limiting: dict,
        registered_user: dict,
    ):
        """Regression: a fresh fake leftmost entry per request used to
        put every attempt in its own bucket."""
        for i in range(6):
            response = client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
                headers={"X-Forwarded-For": f"6.6.6.{i}, 203.0.113.7"},
            )

            if i < 5:
                assert response.status_code == 200
            else:
                assert response.status_code == 429

    def test_distinct_clients_have_separate_limits(
        self,
        client: TestClient,
        auth_headers: dict,
        enable_rate_limiting: dict,
        registered_user: dict,
    ):
        for _ in range(5):
            client.post(
                "/auth/login",
                json={"email": "test@example.com", "password": "testpassword123"},
                headers={"X-Forwarded-For": "203.0.113.7"},
            )

        response = client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "testpassword123"},
            headers={"X-Forwarded-For": "203.0.113.8"},
        )
        assert response.status_code == 200
