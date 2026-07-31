from app.core.celery import celery_app
from app.database import SessionLocal
from app.services.prediction_processing_service import process_prediction
from app.core.logging import logger


@celery_app.task(
    name="process_prediction",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def process_prediction_task(self, prediction_id: int):
    db = SessionLocal()

    try:
        logger.info(
            "Processing prediction %s (attempt %d/%d)",
            prediction_id,
            self.request.retries + 1,
            self.max_retries + 1,
        )

        process_prediction(db, prediction_id)

        logger.info(
            "Successfully processed prediction %s",
            prediction_id,
        )

    except Exception:
        logger.exception(
            "Processing prediction %s failed (attempt %d/%d)",
            prediction_id,
            self.request.retries + 1,
            self.max_retries + 1,
        )
        raise

    finally:
        db.close()
