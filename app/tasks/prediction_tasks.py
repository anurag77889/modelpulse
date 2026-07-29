from app.core.celery import celery_app
from app.database import SessionLocal
from app.services.prediction_processing_service import process_prediction


@celery_app.task(
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_prediction_task(prediction_id: int):
    db = SessionLocal()
    try:
        process_prediction(db, prediction_id)
    finally:
        db.close()
