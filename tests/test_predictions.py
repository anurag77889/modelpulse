import pytest
from fastapi.testclient import TestClient


class TestLogPrediction:
    def test_log_prediction_success(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        response = client.post(f"/models/{model_id}/predictions/", json={
            "input_data": {"age": 34, "tenure_months": 12},
            "prediction_output": {"label": "churn", "probability": 0.87},
            "confidence_score": 0.87,
            "latency_ms": 42.5,
        }, headers=auth_headers)
        assert response.status_code == 201
        body = response.json()
        assert body["confidence_score"] == 0.87
        assert body["latency_ms"] == 42.5
        assert body["drift_score"] is None       # populated by background task
        assert body["actual_output"] is None     # not labelled yet

    def test_log_prediction_model_not_found(
        self, client: TestClient, auth_headers: dict
    ):
        response = client.post("/models/9999/predictions/", json={
            "input_data": {"x": 1},
            "prediction_output": {"y": 0},
        }, headers=auth_headers)
        assert response.status_code == 404

    def test_log_prediction_unauthenticated(
        self, client: TestClient, registered_model: dict
    ):
        model_id = registered_model["id"]
        response = client.post(f"/models/{model_id}/predictions/", json={
            "input_data": {"x": 1},
            "prediction_output": {"y": 0},
        })
        assert response.status_code == 403

    def test_log_prediction_invalid_confidence(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        response = client.post(f"/models/{model_id}/predictions/", json={
            "input_data": {"x": 1},
            "prediction_output": {"y": 0},
            "confidence_score": 1.5,    # must be <= 1.0
        }, headers=auth_headers)
        assert response.status_code == 422


class TestListPredictions:
    def test_list_predictions(
        self,
        client: TestClient,
        logged_prediction: dict,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        response = client.get(
            f"/models/{model_id}/predictions/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_list_predictions_returns_own_predictions_only(
        self,
        client: TestClient,
        registered_model: dict,
        logged_prediction: dict,
        auth_headers: dict,
    ):
        # Register a second user and their model
        client.post("/auth/register", json={
            "email": "other@example.com",
            "username": "otheruser",
            "password": "password123",
        })
        login = client.post("/auth/login", json={
            "email": "other@example.com",
            "password": "password123",
        })
        other_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        model_id = registered_model["id"]
        client.post(f"/models/{model_id}/predictions/", json={
            "input_data": {"age": 34, "tenure_months": 12},
            "prediction_output": {"label": "churn", "probability": 0.87},
            "confidence_score": 0.87,
            "latency_ms": 42.5,
        }, headers=other_headers)

        # First user should only see their own predictions
        response = client.get(f"/models/{model_id}/predictions/", headers=auth_headers)
        body = response.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_list_predictions_unauthorized(
        self,
        client: TestClient,
        logged_prediction: dict,
        registered_model: dict,
    ):
        model_id = registered_model["id"]
        response = client.get(
            f"/models/{model_id}/predictions/",
        )
        assert response.status_code == 403

    def test_list_predictions_empty(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        response = client.get(
            f"/models/{model_id}/predictions/",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_filter_by_confidence(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]

        # Log two predictions with different confidence scores
        for confidence in [0.3, 0.9]:
            client.post(f"/models/{model_id}/predictions/", json={
                "input_data": {"x": 1},
                "prediction_output": {"y": 0},
                "confidence_score": confidence,
            }, headers=auth_headers)

        # Filter for high confidence only
        response = client.get(
            f"/models/{model_id}/predictions/?min_confidence=0.8",
            headers=auth_headers,
        )
        body = response.json()
        assert body["total"] == 1
        assert body["items"][0]["confidence_score"] == 0.9

    def test_filter_labelled(
        self,
        client: TestClient,
        logged_prediction: dict,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        prediction_id = logged_prediction["id"]

        # Label the prediction
        client.patch(
            f"/models/{model_id}/predictions/{prediction_id}/label",
            json={"actual_output": {"label": "churn"}},
            headers=auth_headers,
        )

        # Should appear in labelled filter
        labelled = client.get(
            f"/models/{model_id}/predictions/?labelled=true",
            headers=auth_headers,
        )
        assert labelled.json()["total"] == 1

        # Should not appear in unlabelled filter
        unlabelled = client.get(
            f"/models/{model_id}/predictions/?labelled=false",
            headers=auth_headers,
        )
        assert unlabelled.json()["total"] == 0

    def test_list_predictions_pagination(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):

        model_id = registered_model["id"]

        # List 3 predictions
        for i in range(3):
            client.post(f"/models/{model_id}/predictions/", json={
                "input_data": {"age": 34, "tenure_months": 12},
                "prediction_output": {"label": "churn", "probability": 0.87},
                "confidence_score": 0.87,
                "latency_ms": 42.5,
            }, headers=auth_headers)

        response = client.get(
            f"/models/{model_id}/predictions/?skip=0&limit=2", headers=auth_headers)
        body = response.json()
        assert body["total"] == 3
        assert len(body["items"]) == 2


class TestLabelPrediction:
    def test_label_prediction_success(
        self,
        client: TestClient,
        logged_prediction: dict,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        prediction_id = logged_prediction["id"]

        response = client.patch(
            f"/models/{model_id}/predictions/{prediction_id}/label",
            json={"actual_output": {"label": "churn"}},
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["actual_output"] == {"label": "churn"}

    def test_label_prediction_not_found(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        response = client.patch(
            f"/models/{model_id}/predictions/9999/label",
            json={"actual_output": {"label": "no_churn"}},
            headers=auth_headers,
        )
        assert response.status_code == 404

    def test_label_prediction_forbidden(
        self,
        client: TestClient,
        registered_model: dict,
        logged_prediction: dict
    ):
        # Second user tries to label first user's prediction
        client.post("/auth/register", json={
            "email": "attacker@example.com",
            "username": "attacker",
            "password": "password123",
        })
        login = client.post("/auth/login", json={
            "email": "attacker@example.com",
            "password": "password123",
        })
        attacker_headers = {
            "Authorization": f"Bearer {login.json()['access_token']}"
        }
        model_id = registered_model["id"]
        prediction_id = logged_prediction["id"]
        response = client.patch(
            f"/models/{model_id}/predictions/{prediction_id}/label",
            json={
                "actual_output": {
                    "label": "churn",
                }
            },
            headers=attacker_headers,
        )
        assert response.status_code == 403


class TestPredictionStats:
    def test_stats_empty(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]
        response = client.get(
            f"/models/{model_id}/predictions/stats",
            headers=auth_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["total_predictions"] == 0

    def test_stats_populated(
        self,
        client: TestClient,
        registered_model: dict,
        auth_headers: dict,
    ):
        model_id = registered_model["id"]

        # Log 3 predictions
        for confidence in [0.6, 0.8, 0.9]:
            client.post(f"/models/{model_id}/predictions/", json={
                "input_data": {"x": 1},
                "prediction_output": {"y": 0},
                "confidence_score": confidence,
                "latency_ms": 50.0,
            }, headers=auth_headers)

        response = client.get(
            f"/models/{model_id}/predictions/stats",
            headers=auth_headers,
        )
        body = response.json()
        assert body["total_predictions"] == 3
        assert body["avg_confidence"] == round((0.6 + 0.8 + 0.9) / 3, 4)
