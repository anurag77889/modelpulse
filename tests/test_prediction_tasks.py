import pytest
from unittest.mock import MagicMock, patch

from app.tasks.prediction_tasks import process_prediction_task


class TestPredictionTask:

    @patch("app.tasks.prediction_tasks.process_prediction")
    @patch("app.tasks.prediction_tasks.SessionLocal")
    def test_process_prediction_task_success(
        self,
        mock_session_local,
        mock_process_prediction,
    ):
        db = MagicMock()
        mock_session_local.return_value = db

        process_prediction_task.run(prediction_id=1)

        mock_session_local.assert_called_once()

        mock_process_prediction.assert_called_once_with(
            db,
            1,
        )

        db.close.assert_called_once()

    @patch("app.tasks.prediction_tasks.process_prediction")
    @patch("app.tasks.prediction_tasks.SessionLocal")
    def test_process_prediction_task_exception(
        self,
        mock_session_local,
        mock_process_prediction,
    ):
        db = MagicMock()
        mock_session_local.return_value = db

        mock_process_prediction.side_effect = Exception("Task failed")

        with pytest.raises(Exception, match="Task failed"):
            process_prediction_task.run(prediction_id=1)

        mock_session_local.assert_called_once()

        mock_process_prediction.assert_called_once_with(
            db,
            1,
        )

        db.close.assert_called_once()
