"""
Alembic migrations environment — SQLModel-aware.

target_metadata = SQLModel.metadata enables `alembic revision --autogenerate`.
Importing SQLModel table models registers them in the metadata.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import app bootstrap first: load_dotenv + setup_logging
# (triggered by importing any app submodule)
from app.core.config import settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Database URL from settings (pydantic-settings, reads from .env / env vars)
db_url = settings.DATABASE_URL
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

# Import all SQLModel table models so autogenerate detects schema changes
from app.models.user import User  # noqa: F401
# Future: import app.models.* when migrated to SQLModel

# SQLModel.metadata is the target for autogenerate
from sqlmodel import SQLModel

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
