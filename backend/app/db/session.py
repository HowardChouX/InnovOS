"""SQLAlchemy 同步 session（仅用于 users 表 / 认证层）。"""
from collections.abc import Generator
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        url = settings.DATABASE_URL
        connect_args: dict = {}
        engine_kwargs: dict = {"pool_pre_ping": True}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        else:
            engine_kwargs["pool_size"] = 10
            engine_kwargs["max_overflow"] = 20
        _engine = create_engine(url, connect_args=connect_args, **engine_kwargs)
    return _engine


def _get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=_get_engine(), autocommit=False, autoflush=False,
        )
    return _SessionLocal


def get_session() -> Generator[Session, None, None]:
    """FastAPI 依赖：提供 ORM session。仅用于认证/用户表。"""
    factory = _get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()