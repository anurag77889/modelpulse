from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.models.alert import Alert
from app.models.ml_model import MLModel
from app.models.prediction import Prediction
from app.models.user import User
from app.services.drift_detection_service import (
    _compute_drift_score,
    _get_baseline_stats,
    run_drift_detection,
)
from tests.conftest import TestingSessionLocal


def _seed_model(db, drift_threshold: float = 0.05) -> MLModel:
    owner = User(
        email="drift@example.com",
        username="driftuser",
        hashed_password="not-a-real-hash",
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)

    model = MLModel(
        name="Drift Model",
        version="1.0.0",
        model_type="classification",
        drift_threshold=drift_threshold,
        owner_id=owner.id,
    )
    db.add(model)
    db.commit()
    db.refresh(model)
    return model


def _seed_prediction(
    db,
    model_id: int,
    confidence: float | None,
    created_at: datetime,
) -> Prediction:
    prediction = Prediction(
        input_data={"feature": 1},
        prediction_output={"class": "a"},
        confidence_score=confidence,
        ml_model_id=model_id,
        created_at=created_at,
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    return prediction


class TestComputeDriftScore:
    def test_zero_std_returns_zero(self):
        assert _compute_drift_score(0.5, 0.9, 0.0) == 0.0

    def test_score_bounded_between_zero_and_one(self):
        assert 0.0 <= _compute_drift_score(0.1, 0.9, 0.05) <= 1.0

    def test_score_grows_with_deviation(self):
        small = _compute_drift_score(0.85, 0.9, 0.05)
        large = _compute_drift_score(0.2, 0.9, 0.05)
        assert large > small


class TestBaselineStats:
    def test_baseline_uses_recent_window(self, setup_database):
        """Regression: aggregate must run AFTER the 100-row window.

        The old query aggregated before applying the window limit,
        so the baseline covered every row instead of the last 100.
        """
        db = TestingSessionLocal()
        try:
            model = _seed_model(db)

            old_base = datetime(2026, 1, 1, tzinfo=UTC)
            for i in range(100):
                _seed_prediction(db, model.id, 0.1, old_base + timedelta(minutes=i))

            recent_base = datetime(2026, 6, 1, tzinfo=UTC)
            for i in range(20):
                _seed_prediction(db, model.id, 0.9, recent_base + timedelta(minutes=i))

            mean, std = _get_baseline_stats(db, model.id, exclude_prediction_id=-1)

            # Window keeps the 100 most recent rows: 20 x 0.9 + 80 x 0.1
            # mean = 26 / 100 = 0.26, std = sqrt(0.17 - 0.26^2) = 0.32
            # Aggregating all 120 rows would give mean ~0.2333 instead.
            assert round(mean, 4) == 0.26
            assert round(std, 4) == 0.32
        finally:
            db.close()

    def test_baseline_excludes_current_prediction(self, setup_database):
        db = TestingSessionLocal()
        try:
            model = _seed_model(db)
            base = datetime(2026, 1, 1, tzinfo=UTC)
            for i, conf in enumerate([0.8, 0.8, 0.8, 0.8]):
                _seed_prediction(db, model.id, conf, base + timedelta(minutes=i))
            current = _seed_prediction(db, model.id, 0.1, base + timedelta(hours=1))

            mean, _ = _get_baseline_stats(
                db, model.id, exclude_prediction_id=current.id
            )

            assert round(mean, 4) == 0.8
        finally:
            db.close()


class TestRunDriftDetection:
    def test_detects_drift_and_creates_alert(self, setup_database):
        db = TestingSessionLocal()
        try:
            model = _seed_model(db, drift_threshold=0.05)

            base = datetime(2026, 1, 1, tzinfo=UTC)
            baseline = [0.90, 0.91, 0.89, 0.92, 0.88, 0.93, 0.87, 0.94, 0.86, 0.95]
            for i, conf in enumerate(baseline):
                _seed_prediction(db, model.id, conf, base + timedelta(minutes=i))

            current = _seed_prediction(db, model.id, 0.10, base + timedelta(hours=1))

            run_drift_detection(db, prediction_id=current.id, model_id=model.id)

            db.refresh(current)
            assert current.drift_score is not None
            assert current.drift_score > model.drift_threshold

            alert = (
                db.query(Alert)
                .filter(
                    Alert.ml_model_id == model.id,
                    Alert.alert_type == "drift_detected",
                )
                .one_or_none()
            )
            assert alert is not None
            assert alert.triggered_value == current.drift_score
            assert alert.severity == "critical"
        finally:
            db.close()

    def test_no_alert_within_threshold(self, setup_database):
        db = TestingSessionLocal()
        try:
            model = _seed_model(db, drift_threshold=0.75)

            base = datetime(2026, 1, 1, tzinfo=UTC)
            baseline = [0.90, 0.91, 0.89, 0.92, 0.88, 0.93, 0.87, 0.94, 0.86, 0.95]
            for i, conf in enumerate(baseline):
                _seed_prediction(db, model.id, conf, base + timedelta(minutes=i))

            current = _seed_prediction(db, model.id, 0.89, base + timedelta(hours=1))

            run_drift_detection(db, prediction_id=current.id, model_id=model.id)

            db.refresh(current)
            assert current.drift_score is not None
            assert current.drift_score <= model.drift_threshold
            assert db.query(Alert).count() == 0
        finally:
            db.close()

    def test_skips_when_history_too_short(self, setup_database):
        db = TestingSessionLocal()
        try:
            model = _seed_model(db)

            base = datetime(2026, 1, 1, tzinfo=UTC)
            for i in range(9):
                _seed_prediction(db, model.id, 0.9, base + timedelta(minutes=i))
            current = _seed_prediction(db, model.id, 0.1, base + timedelta(hours=1))

            run_drift_detection(db, prediction_id=current.id, model_id=model.id)

            db.refresh(current)
            assert current.drift_score is None
            assert db.query(Alert).count() == 0
        finally:
            db.close()

    def test_skips_prediction_without_confidence(self, setup_database):
        db = TestingSessionLocal()
        try:
            model = _seed_model(db)

            base = datetime(2026, 1, 1, tzinfo=UTC)
            for i in range(10):
                _seed_prediction(db, model.id, 0.9, base + timedelta(minutes=i))
            current = _seed_prediction(db, model.id, None, base + timedelta(hours=1))

            run_drift_detection(db, prediction_id=current.id, model_id=model.id)

            db.refresh(current)
            assert current.drift_score is None
            assert db.query(Alert).count() == 0
        finally:
            db.close()

    def test_errors_propagate_for_celery_retry(self):
        """Failures must bubble up so the Celery task can retry."""
        db = MagicMock()
        db.query.side_effect = RuntimeError("db down")

        with pytest.raises(RuntimeError, match="db down"):
            run_drift_detection(db, prediction_id=1, model_id=1)

        db.rollback.assert_called_once()
