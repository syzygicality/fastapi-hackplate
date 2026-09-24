import logging

from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.types import Backend

from app.platform.infra.redis import RedisSettings
from app.platform.toml_settings import CacheSettings

logger = logging.getLogger(__name__)


def init_cache(
    cache_settings: CacheSettings,
    redis_settings: RedisSettings | None = None,
) -> None:
    """
    Initializes fastapi-cache2 with a Redis backend when Redis is configured,
    otherwise an in-memory backend. Call this once during startup (lifespan).

    Args:
        cache_settings: prefix / default TTL for cached responses.
        redis_settings: when provided, cached responses are stored in Redis.
    """
    logger.info("Cache prefix: %s", cache_settings.prefix)
    if redis_settings is not None:
        from redis import asyncio as aioredis
        from fastapi_cache.backends.redis import RedisBackend

        client = aioredis.from_url(redis_settings.connection_url)
        backend: Backend = RedisBackend(client)

        logger.info("Using Redis cache backend...")
    else:
        backend = InMemoryBackend()
        logger.info("Redis disabled, using in-memory cache backend...")

    FastAPICache.init(
        backend,
        prefix=cache_settings.prefix,
        expire=cache_settings.expire,
    )


async def clear_cache() -> None:
    """Flushes every entry stored under the configured cache prefix."""
    await FastAPICache.clear()
