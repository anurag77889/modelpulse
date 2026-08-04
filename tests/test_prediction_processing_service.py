from unittest.mock import MagicMock, patch

from app.services.prediction_processing_service import process_prediction


class TestProcessPrediction:

    @patch("app.services.prediction_processing_service.invalidate_model_summary_cache")
    @patch("app.services.prediction_processing_service.run_drift_detection")
    @patch("app.services.prediction_processing_service.get_prediction")
    def test_process_prediction_success(
        self,
        mock_get_prediction,
        mock_run_drift_detection,
        mock_invalidate_cache,
    ):
        db = MagicMock()

        prediction = MagicMock()
        prediction.id = 1
        prediction.ml_model_id = 10

        mock_get_prediction.return_value = prediction

        process_prediction(db, prediction.id)

        mock_get_prediction.assert_called_once_with(db, prediction.id)

        mock_run_drift_detection.assert_called_once_with(
            db=db,
            prediction_id=1,
            model_id=10,
        )

        mock_invalidate_cache.assert_called_once_with(10)

    @patch("app.services.prediction_processing_service.invalidate_model_summary_cache")
    @patch("app.services.prediction_processing_service.run_drift_detection")
    @patch("app.services.prediction_processing_service.get_prediction")
    def test_process_prediction_not_found(
        self,
        mock_get_prediction,
        mock_run_drift_detection,
        mock_invalidate_cache,
    ):
        db = MagicMock()

        mock_get_prediction.return_value = None

        process_prediction(db, prediction_id=999)

        mock_get_prediction.assert_called_once_with(db, 999)

        mock_run_drift_detection.assert_not_called()
        mock_invalidate_cache.assert_not_called()
