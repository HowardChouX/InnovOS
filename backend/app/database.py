"""
Database abstraction layer — PostgreSQL only.
Uses psycopg2 with connection pooling.

Compatible with existing sqlite3-based code patterns:
  db = get_db()
  db.execute("SELECT * FROM users WHERE id=?", (uid,))    # ? auto-converted to %s for PG
  row = db.execute(...).fetchone() / .fetchall()           # dict-like rows → row["col"]
  cursor = db.execute("INSERT INTO ... RETURNING id", ...
  inserted_id = cursor.fetchone()["id"]                    # RETURNING id + fetchone
  db.commit()
  db.close()
"""
import os
import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")

_QMARK = re.compile(r"\?")

def is_postgres() -> bool:
    return True  # PostgreSQL only now


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


import psycopg2
import psycopg2.extras

_pg_pool: Any = None


class _PostgresDatabase:
    """PostgreSQL database wrapper."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params=None):
        import psycopg2.extras
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
        global _pg_pool
        try:
            _pg_pool.putconn(self._conn)  # type: ignore[union-attr]
        except Exception:
            logger.warning("Failed to return connection to pool, closing directly")
            self._conn.close()


def _get_pg_db():
    global _pg_pool
    if _pg_pool is None:
        from psycopg2 import pool as _pool
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL environment variable not set. "
                "Example: postgresql://user:password@host:5432/innovos"
            )
        logger.info(f"Connecting to PostgreSQL: {DATABASE_URL[:30]}...")
        _pg_pool = _pool.ThreadedConnectionPool(1, 50, DATABASE_URL)
    raw_conn = _pg_pool.getconn()
    return _PostgresDatabase(raw_conn)


def get_db():
    """Get a PostgreSQL database connection."""
    return _get_pg_db()


def init_db():
    """Initialize database schema. Called once at application startup."""
    from app.tables.pg_schema import init_all_tables

    logger.info("Initializing PostgreSQL schema...")

    db = get_db()
    try:
        init_all_tables(db)
        db.commit()
        logger.info("Database schema initialized")
    except Exception:
        db.rollback()
        logger.exception("Database schema initialization failed")
        raise
    finally:
        db.close()
