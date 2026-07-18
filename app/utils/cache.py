from redis.exceptions import RedisError

from app.core.redis import redis_client
from app.core.logging import logger


def invalidate_model_summary_cache(model_id: int) -> None:
    cache_key = f"model:{model_id}:summary"

    try:
        redis_client.delete(cache_key)
        logger.info(f"Invalidated cache for model {model_id}.")
    except RedisError as e:
        logger.warning(f"Failed to invalidate cache for model {model_id}: {e}")
