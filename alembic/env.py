"""Alembic async env."""

import asyncio
from logging.config import fileConfig

from alembic import context  # type: ignore[attr-defined]
from sqlalchemy.ext.asyncio import create_async_engine

from mv_hofki.db.base import Base
from mv_hofki.models import *  # noqa: F401, F403 — register all models

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    assert url is not None, "sqlalchemy.url must be set in alembic.ini"
    connectable = create_async_engine(url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
