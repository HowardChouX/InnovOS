"""
Database abstraction layer — PostgreSQL only.
Uses psycopg2 with connection pooling.

NOTE: psycopg2 connections are not coroutine-safe. Each asyncio task should use
its own connection. The get_db()/db_session() pattern already provides per-call
connections, which is correct. However, sharing a connection across concurrent
coroutines within the same call is unsafe.

RECOMMENDED: Use 'with db_session() as db:' for automatic cleanup.

Usage pattern:
  with db_session() as db:
      db.execute("SELECT * FROM users WHERE id=?", (uid,))
      row = db.execute(...).fetchone()
"""

import logging
import re
import threading
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

from app.core.config import settings

logger = logging.getLogger(__name__)


def _build_pg_dsn(url: str) -> str:
    """Convert SQLAlchemy URL ('postgresql+psycopg2://...?host=/tmp') to psycopg2 DSN.

    psycopg2 does not understand the '+psycopg2' driver prefix or query-string
    fields like 'host=/tmp'; we strip the driver and merge query fields into
    keyword args. Returns a libpq-style DSN string.
    """
    if not url:
        raise RuntimeError(
            "DATABASE_URL environment variable not set. "
            "Example: postgresql://user:password@host:5432/innovos"
        )
    # Strip SQLAlchemy driver prefix: postgresql+psycopg2:// -> postgresql://
    cleaned = re.sub(r"^postgresql\+\w+://", "postgresql://", url)
    parsed = urlparse(cleaned)
    if not parsed.scheme.startswith("postgresql"):
        raise RuntimeError(f"Unsupported DATABASE_URL scheme: {parsed.scheme}")
    # libpq key=value DSN
    parts = []
    if parsed.hostname:
        parts.append(f"host={parsed.hostname}")
    if parsed.port:
        parts.append(f"port={parsed.port}")
    if parsed.path and parsed.path.lstrip("/"):
        parts.append(f"dbname={parsed.path.lstrip('/')}")
    if parsed.username:
        parts.append(f"user={parsed.username}")
    if parsed.password:
        parts.append(f"password={parsed.password}")
    # Merge non-DSN query params (e.g. ?host=/tmp for local socket) into DSN.
    # Skip keys already covered above so libpq doesn't complain about dupes.
    skip = {"host", "port", "dbname", "user", "password"}
    for k, v in parsed.query_params if hasattr(parsed, "query_params") else []:
        if k in skip:
            continue
        parts.append(f"{k}={v}")
    return " ".join(parts)


DATABASE_URL = settings.DATABASE_URL or ""
_PG_DSN = _build_pg_dsn(DATABASE_URL)

_QMARK = re.compile(r"\?")


class _Row(dict):
    """Dict row that also supports integer indexing."""

    def __getitem__(self, key):
        if isinstance(key, (int,)):
            return list(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    """Cursor wrapper returning _Row objects."""

    def __init__(self, conn_cursor):
        self._cur = conn_cursor

    def execute(self, sql: str, params=None):
        if params is not None:
            sql = _QMARK.sub("%s", sql)
        self._cur.execute(sql, params)
        return self

    def fetchone(self):
        row = self._cur.fetchone()
        return _Row(row) if row else None

    def fetchall(self):
        rows = self._cur.fetchall()
        return [_Row(r) for r in rows]

    def __iter__(self):
        for r in self._cur:
            yield _Row(r)

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description

    @property
    def lastrowid(self):
        return self._cur.lastrowid


_pg_pool: Any = None
_pg_pool_lock = threading.Lock()


class _PostgresDatabase:
    """PostgreSQL database wrapper with automatic connection recovery.

    If close() is not called explicitly, the connection is returned to the pool
    during garbage collection as a safety net to prevent connection leaks.
    """

    def __init__(self, conn):
        self._conn = conn
        self._closed = False

    def execute(self, sql: str, params=None):
        if params is not None:
            sql = _QMARK.sub("%s", sql)
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return _Cursor(cur)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        if self._closed:
            return
        self._closed = True
        global _pg_pool
        try:
            _pg_pool.putconn(self._conn)
        except Exception:
            logger.warning("Failed to return connection to pool, closing directly")
            try:
                self._conn.close()
            except Exception:
                pass

    def __del__(self):
        """Safety net: auto-return connection if not explicitly closed."""
        if not self._closed:
            logger.warning(
                "Database connection was not closed explicitly. "
                "It is being returned to the pool by the garbage collector. "
                "Please use 'with db_session() as db:' to avoid this warning."
            )
            try:
                self.close()
            except Exception:
                pass


def _get_pg_db():
    global _pg_pool
    if _pg_pool is None:
        with _pg_pool_lock:
            if _pg_pool is None:  # double-checked locking
                from psycopg2 import pool as _pool

                if not DATABASE_URL:
                    raise RuntimeError(
                        "DATABASE_URL environment variable not set. Example: postgresql://user:password@host:5432/innovos"
                    )
                logger.info(f"Connecting to PostgreSQL: {DATABASE_URL[:30]}...")
                _pg_pool = _pool.ThreadedConnectionPool(1, 50, dsn=_PG_DSN)
    raw_conn = _pg_pool.getconn()
    return _PostgresDatabase(raw_conn)


def get_db():
    """Get a PostgreSQL database connection.

    DEPRECATED: Prefer 'with db_session() as db:' for automatic cleanup.
    The __del__ safety net will catch leaks, but explicit cleanup is better.
    """
    return _get_pg_db()


@contextmanager
def db_session():
    """Get a DB connection with guaranteed return to pool.

    Auto-commits on success, auto-rollbacks on exception, auto-closes on exit.

    Usage:
        with db_session() as db:
            rows = db.execute("SELECT * FROM users").fetchall()
    """
    db = get_db()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dep():
    """FastAPI dependency yielding a DB connection."""
    with db_session() as db:
        yield db


def pool_usage() -> dict:
    """Return pool usage stats for health monitoring."""
    global _pg_pool
    if _pg_pool is None:
        return {"status": "not_initialized"}
    return {
        "status": "ok",
        "used": getattr(_pg_pool, "_used", 0),
        "max": getattr(_pg_pool, "_maxconn", 50),
    }


def init_db():
    """Initialize database schema. Called once at application startup."""
    from app.tables.pg_schema import init_all_tables

    logger.info("Initializing PostgreSQL schema...")

    with db_session() as db:
        init_all_tables(db)
        logger.info("Database schema initialized")

    # 清理过期 email_verifications（best-effort，失败不阻塞启动）
    try:
        from app.services.email_verification_service import email_verification_service

        email_verification_service.purge_expired()
    except Exception as e:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning("purge_expired 失败: %s", e)
