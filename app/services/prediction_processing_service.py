from sqlalchemy.orm import Session

from app.core.logging import logger
from app.services.drift_detection_service import run_drift_detection
from app.utils.cache import invalidate_model_summary_cache
from app.services.prediction_service import get_prediction


def process_prediction(db: Session, prediction_id: int):
    prediction = get_prediction(db, prediction_id)

    if prediction is None:
        logger.warning("Prediction %s not found", prediction_id)
        return

    run_drift_detection(
        db=db,
        prediction_id=prediction.id,
        model_id=prediction.ml_model_id,
    )

    invalidate_model_summary_cache(prediction.ml_model_id)
