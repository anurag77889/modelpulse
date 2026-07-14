import pytest
from fastapi.testclient import TestClient


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
                    "password": f"password12{i}"
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
                    "password": f"password12{i}"
                }
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
                json={
                    "email": "test@example.com",
                    "password": "testpassword123"
                },
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
                json={
                    "email": "test@example.com",
                    "password": "testpassword123"
                }
            )

            if i < 5:
                assert response.status_code == 200
            else:
                assert response.status_code == 429
