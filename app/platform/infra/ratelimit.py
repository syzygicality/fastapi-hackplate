import logging

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.platform.hackplate_types import Hackplate
from app.platform.infra.redis import get_redis_settings
from app.platform.toml_settings import BackendTOMLSettings

logger = logging.getLogger(__name__)


def _build_limiter() -> tuple[Limiter, bool]:
    """
    Builds the slowapi Limiter from [tool.hackplate.ratelimit], backed by Redis
    when Redis is enabled, otherwise in-process memory.

    Returns the limiter and whether the Redis backend is in use (for logging).
    """
    settings = BackendTOMLSettings()
    redis = get_redis_settings()
    rl = settings.ratelimit

    storage_uri = redis.connection_url if redis is not None else "memory://"
    limiter = Limiter(
        key_func=get_remote_address,  # rate-limit per client IP
        default_limits=rl.default_limits,
        storage_uri=storage_uri,
        key_prefix=rl.key_prefix,
        enabled=rl.ratelimiting_enabled,
        swallow_errors=True,  # a limit-store outage must not turn requests into 500s
    )
    return limiter, redis is not None


# Module-level singleton so feature routes can decorate endpoints with
# `@limiter.limit("5/minute")` (the endpoint must accept `request: Request`).
limiter, _uses_redis = _build_limiter()


def register_rate_limiter(app: Hackplate) -> None:
    """
    Wires slowapi into the app: the shared limiter, its HTTP 429 handler, and the
    middleware that enforces default_limits globally. Called at construction time
    from configure().
    """
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)


def log_rate_limit_backend() -> None:
    """Logs the active rate-limit backend. Called at startup, after logging setup."""
    if not limiter.enabled:
        logger.info("Rate limiting disabled, enable in pyproject.toml.")
    elif _uses_redis:
        logger.info("Using Redis rate-limit backend...")
    else:
        logger.info("Redis disabled, using in-memory rate-limit backend... ")
