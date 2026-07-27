from app.core.celery import celery_app


@celery_app.task
def add(x: int, y: int) -> int:
    return x + y
