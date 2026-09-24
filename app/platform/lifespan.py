import logging
import asyncio
from contextlib import asynccontextmanager, AsyncExitStack
from collections.abc import AsyncGenerator, Callable

from fastapi import status
from fastapi.exceptions import HTTPException
from fastapi.responses import RedirectResponse

from app.platform.config import BackendConfig
from app.platform.cors import register_cors_middleware
from app.platform.exceptions import register_exception_handlers
from app.platform.infra.ratelimit import (
    register_rate_limiter,
    log_rate_limit_backend,
)
from app.platform.infra.task_scheduling import (
    scheduler,
    start_scheduler,
    shutdown_scheduler,
)
from app.platform.logging import register_logging
from app.platform.hackplate_types import Hackplate, HackplateRequest
from app.platform.toml_settings import BackendTOMLSettings
from app.platform.mcp import mcp as mcp_instance

logger = logging.getLogger(__name__)


@asynccontextmanager
async def base_lifespan(app: Hackplate) -> AsyncGenerator[None, None]:
    settings = BackendTOMLSettings()
    app.state.settings = settings
    config = BackendConfig(settings)
    app.state.config = config
    log_rate_limit_backend()
    yield


@asynccontextmanager
async def config_lifespan(app: Hackplate) -> AsyncGenerator[None, None]:
    await app.state.config.db.connect()
    logger.info("Successful database connection!")
    if not await app.state.config.db.ping():
        logger.exception("Database ping failed.")
        await app.state.config.db.disconnect()
        raise RuntimeError("Database ping failed.")
    logger.info("Database: PONG")
    if not await app.state.config.auth.ping():
        logger.exception("Auth ping failed.")
        await app.state.config.db.disconnect()
        raise RuntimeError("Auth ping failed.")
    logger.info("Auth: PONG")
    if app.state.config.redis is not None:
        if not await app.state.config.redis.ping():
            logger.exception("Redis ping failed.")
            await app.state.config.db.disconnect()
            raise RuntimeError("Redis ping failed.")
        logger.info("Redis: PONG")
    await app.state.config.auth.register_auth_routes(app)
    app.state.scheduler = scheduler
    start_scheduler()
    yield
    shutdown_scheduler()
    await app.state.config.db.disconnect()


@asynccontextmanager
async def hackplate_lifespan(app: Hackplate) -> AsyncGenerator[None, None]:
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(base_lifespan(app))
        if app.pre_hackplate_lifespan:
            await stack.enter_async_context(app.pre_hackplate_lifespan(app))
        await stack.enter_async_context(config_lifespan(app))
        if app.state.settings.project.mcp_server_enabled and mcp_instance is not None:
            await stack.enter_async_context(mcp_instance.session_manager.run())
        if app.post_hackplate_lifespan:
            await stack.enter_async_context(app.post_hackplate_lifespan(app))
        yield


def register_root_redirect(app: Hackplate) -> None:
    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/docs")


def register_health_ping(app: Hackplate) -> None:
    @app.get("/ping")
    async def ping(request: HackplateRequest) -> dict[str, str]:
        config = request.app.state.config
        checks: dict[str, "asyncio.Future[bool]"] = {
            "Database": config.db.ping(),
            "Auth": config.auth.ping(),
        }
        if config.redis is not None:
            checks["Redis"] = config.redis.ping()

        results = await asyncio.gather(*checks.values())
        failed = [name for name, ok in zip(checks, results) if not ok]
        if failed:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"{' and '.join(failed)} Ping Failed.",
            )
        return {"message": "PONG"}


def register_mcp(app: Hackplate) -> None:
    from app.platform.toml_settings import BackendTOMLSettings

    settings = BackendTOMLSettings()
    if settings.project.mcp_server_enabled:
        from app.platform.mcp import init_mcp, get_mcp

        init_mcp(settings.details.name)
        import migrations.register_tools  # noqa: F401

        app.mount("/mcp", get_mcp().streamable_http_app())


def configure(app: Hackplate, register_functions: list[Callable[[Hackplate], None]]):
    """
    Centralizes app configuration logic

    Args:
        app: initialized Hackplate object originating from main.py
        register_functions: list of functions with a single `app: Hackplate` param
    """
    register_logging()
    register_exception_handlers(app)
    register_cors_middleware(app)
    register_rate_limiter(app)
    register_root_redirect(app)
    register_health_ping(app)
    register_mcp(app)

    for fn in register_functions:
        try:
            fn(app)
        except Exception as e:
            raise RuntimeError(f"Failed to register {fn.__name__}") from e
