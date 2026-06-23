"""
SQLModel engine & session management.

Provides the primary database engine for SQLModel ORM access.
Coexists with the legacy psycopg2 connection pool (app.database)
during the incremental migration.
"""

from collections.abc import Generator

from sqlmodel import Session, create_engine

from app.core.config import settings

engine = create_engine(
    str(settings.SQLALCHEMY_DATABASE_URI),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a SQLModel session (auto-closes on return)."""
    with Session(engine) as session:
        yield session
