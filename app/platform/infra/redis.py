import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class RedisSettings(BaseSettings):
    """
    Loads Redis connection settings from the environment (REDIS_* variables).

    Set REDIS_ENABLED=true to turn Redis on. Provide either REDIS_URL or the
    individual connection fields below.
    """

    model_config = SettingsConfigDict(
        env_prefix="REDIS_",
        env_file=".env",
        extra="ignore",
        env_ignore_empty=True,
    )

    enabled: bool = False

    url: str | None = None

    host: str = "localhost"
    port: int = 6379
    db: int = 0
    username: str | None = None
    password: str | None = None
    ssl_required: bool = False

    @property
    def connection_url(self) -> str:
        """Builds a redis:// (or rediss://) URL from the configured settings."""
        if self.url:
            return self.url
        scheme = "rediss" if self.ssl_required else "redis"
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        elif self.password:
            auth = f":{self.password}@"
        else:
            auth = ""
        return f"{scheme}://{auth}{self.host}:{self.port}/{self.db}"

    async def ping(self) -> bool:
        """Ensure the Redis server is reachable. Returns True on PONG, False otherwise."""
        import redis.asyncio as redis

        client = redis.from_url(self.connection_url)
        try:
            return bool(await client.ping())
        except Exception:
            logger.warning("Redis ping failed.")
            return False
        finally:
            await client.close()


def get_redis_settings() -> RedisSettings | None:
    """Returns the Redis settings when REDIS_ENABLED is true, otherwise None."""
    redis = RedisSettings()
    return redis if redis.enabled else None
