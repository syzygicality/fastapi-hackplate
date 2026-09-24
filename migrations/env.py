import asyncio
import os
from logging.config import fileConfig
from pathlib import Path
from typing import Any, Literal

from alembic.autogenerate.api import AutogenContext
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context
from sqlmodel import SQLModel
from sqlmodel.sql.sqltypes import AutoString

# Import all SQLModel table models so they register with SQLModel.metadata
import migrations.register_models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def get_url() -> str:
    db = os.getenv("HACKPLATE_DB", "sqlite")
    if db == "supabase":
        from app.platform.plates.db_plates.postgres.supabase_config import (
            SupabaseSettings,
        )

        sb = SupabaseSettings()
        if sb.url:
            return sb.url
        base = f"postgresql+asyncpg://{sb.username}:{sb.password}@{sb.host}:{sb.port}/{sb.name}"
        return f"{base}?ssl=require" if sb.ssl_required else base
    if db == "postgres":
        from app.platform.plates.db_plates.postgres.config import PostgresSettings

        pg = PostgresSettings()
        if pg.url:
            return pg.url
        base = f"postgresql+asyncpg://{pg.username}:{pg.password}@{pg.host}:{pg.port}/{pg.name}"
        return f"{base}?ssl=require" if pg.ssl_required else base
    else:
        from app.platform.plates.db_plates.sqlite.config import SQLiteSettings

        lite = SQLiteSettings()
        resolved = str(Path(lite.db_path).resolve())
        return f"sqlite+aiosqlite:///{resolved}"


def render_item(
    type_: str, obj: Any, autogen_context: AutogenContext
) -> str | Literal[False]:
    """Render SQLModel's AutoString as plain sa.String() in migration files."""
    if type_ == "type" and isinstance(obj, AutoString):
        autogen_context.imports.add("import sqlalchemy as sa")
        return "sa.String()"
    return False


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
        render_item=render_item,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(get_url(), poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
