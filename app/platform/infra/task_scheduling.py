import logging

from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.platform.infra.redis import get_redis_settings
from app.platform.toml_settings import BackendTOMLSettings

logger = logging.getLogger(__name__)


def _build_scheduler() -> tuple[AsyncIOScheduler, bool]:
    """
    Builds the APScheduler AsyncIOScheduler from [tool.hackplate.scheduler]. Jobs
    are persisted in a Redis job store when Redis is enabled, otherwise kept in
    an in-process memory store.

    Returns the scheduler and whether the Redis job store is in use (for logging).
    """
    settings = BackendTOMLSettings()
    redis = get_redis_settings()

    if redis is not None:
        from apscheduler.jobstores.redis import RedisJobStore

        jobstore = RedisJobStore(
            db=redis.db,
            host=redis.host,
            port=redis.port,
            username=redis.username,
            password=redis.password,
            ssl=redis.ssl_required,
        )
    else:
        jobstore = MemoryJobStore()

    scheduler = AsyncIOScheduler(
        jobstores={"default": jobstore},
        timezone=settings.scheduler.timezone,
    )
    return scheduler, redis is not None


# Module-level singleton so feature code can register jobs with
# `@scheduler.scheduled_job("interval", minutes=5)` or `scheduler.add_job(...)`.
scheduler, _uses_redis = _build_scheduler()


def start_scheduler() -> None:
    """
    Starts the scheduler when task scheduling is enabled. Must be called from
    inside the running event loop (i.e. the async lifespan), since
    AsyncIOScheduler binds to the loop it starts on.

    When disabled, any registered jobs simply never fire.
    """
    if not BackendTOMLSettings().scheduler.task_scheduling_enabled:
        logger.info("Task scheduling disabled, enable in pyproject.toml.")
        return
    if _uses_redis:
        logger.info("Using Redis job store for task scheduling...")
    else:
        logger.info("Redis disabled, using in-memory job store for task scheduling...")
    scheduler.start()


def shutdown_scheduler() -> None:
    """Stops the scheduler if it is running. Called on app shutdown."""
    if scheduler.running:
        logger.info("Shutting down task scheduler...")
        scheduler.shutdown(wait=False)
