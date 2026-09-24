from typing import Any

from pydantic_settings import (
    BaseSettings,
    PyprojectTomlConfigSettingsSource,
    SettingsConfigDict,
)


class BaseTOMLSettings(BaseSettings):
    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("tool", "hackplate"),
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        **kwargs: Any,
    ) -> tuple[PyprojectTomlConfigSettingsSource]:
        return (PyprojectTomlConfigSettingsSource(settings_cls),)


class ProjectDetails(BaseTOMLSettings):
    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("project",),
        extra="ignore",
    )

    name: str = "fastapi-hackplate"
    version: str = "0.1.0"
    description: str = ""


class GeneralSettings(BaseTOMLSettings):
    auth_user_model: str = "app.platform.user.models.User"
    mcp_server_enabled: bool = False


class DatabaseSettings(BaseTOMLSettings):
    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("tool", "hackplate", "db"),
        extra="ignore",
    )

    alembic: bool = False


class AuthSettings(BaseTOMLSettings):
    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("tool", "hackplate", "auth"),
        extra="ignore",
    )


class CacheSettings(BaseTOMLSettings):
    """Response-cache (fastapi-cache2) options from [tool.hackplate.cache]."""

    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("tool", "hackplate", "cache"),
        extra="ignore",
    )

    prefix: str = "hackplate-cache"
    expire: int = 60


class RateLimitSettings(BaseTOMLSettings):
    """Rate limiting (slowapi) options from [tool.hackplate.ratelimit]."""

    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("tool", "hackplate", "ratelimit"),
        extra="ignore",
    )

    ratelimiting_enabled: bool = True
    default_limits: list[str] = []
    key_prefix: str = "hackplate-ratelimit"


class SchedulerSettings(BaseTOMLSettings):
    """Task scheduling (APScheduler) options from [tool.hackplate.scheduler]."""

    model_config = SettingsConfigDict(
        pyproject_toml_table_header=("tool", "hackplate", "scheduler"),
        extra="ignore",
    )

    task_scheduling_enabled: bool = False
    timezone: str = "UTC"


class BackendTOMLSettings:
    def __init__(self):
        self.details = ProjectDetails()
        self.project = GeneralSettings()
        self.db = DatabaseSettings()
        self.auth = AuthSettings()
        self.cache = CacheSettings()
        self.ratelimit = RateLimitSettings()
        self.scheduler = SchedulerSettings()
