"""SQLAlchemy 同步 session（仅用于 users 表 / 认证层）。"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供 ORM session。仅用于认证/用户表。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()