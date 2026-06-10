"""
Database abstraction layer — dual-mode: PostgreSQL (production) / SQLite (development).

Compatible with existing sqlite3-based code patterns:
  db = get_db()
  db.execute("SELECT * FROM users WHERE id=?", (uid,))    # ? auto-converted to %s for PG
  row = db.execute(...).fetchone() / .fetchall()           # dict-like rows → row["col"]
  cursor = db.execute("INSERT INTO ... RETURNING id", ...
  inserted_id = cursor.fetchone()["id"]                    # RETURNING id + fetchone
  db.commit()
  db.close()

Auto-detection: DATABASE_URL starting with "postgresql://" → PostgreSQL
               everything else (empty, .db path, or sqlite://) → SQLite
"""
import os
import re
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "")


# ═══════════════════════════════════════════════════════════════
#  Backend detection
# ═══════════════════════════════════════════════════════════════

def is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql://")

def get_sqlite_path() -> str:
    """Resolve SQLite database path from DATABASE_URL or default."""
    if DATABASE_URL and not DATABASE_URL.startswith("postgresql://"):
        # Could be a file path or sqlite:///path/to/db
        path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
        if path:
            return path
    return os.getenv("SQLITE_PATH", "InnovOS_ACCOUNTS.db")


# ═══════════════════════════════════════════════════════════════
#  Cursor — unified dict-like row access
# ═══════════════════════════════════════════════════════════════

class _Row(dict):
    """Dict row that also supports integer indexing (compatible with sqlite3.Row)."""
    def __getitem__(self, key):
        if isinstance(key, (int,)):
            return list(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    """Cursor wrapper returning _Row objects."""

    def __init__(self, conn_cursor, backend: str = "sqlite"):
        self._cur = conn_cursor
        self._backend = backend

    def execute(self, sql: str, params=None):
        if params is not None and self._backend == "postgres":
            from app.database import _QMARK
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


# ═══════════════════════════════════════════════════════════════
#  PostgreSQL backend (psycopg2)
# ═══════════════════════════════════════════════════════════════

_QMARK = re.compile(r"\?")
_pg_pool: Any = None


class _PostgresDatabase:
    """PostgreSQL database wrapper — compatible with sqlite3.Connection interface."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params=None):
        import psycopg2.extras
        sql = _QMARK.sub("%s", sql) if params is not None else sql
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return _Cursor(cur, backend="postgres")

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
        _pg_pool = _pool.ThreadedConnectionPool(1, 20, DATABASE_URL)
    raw_conn = _pg_pool.getconn()
    return _PostgresDatabase(raw_conn)


# ═══════════════════════════════════════════════════════════════
#  SQLite backend (standard library)
# ═══════════════════════════════════════════════════════════════

import sqlite3

_sqlite_conn: Optional[sqlite3.Connection] = None


class _SQLiteDatabase:
    """SQLite database wrapper."""

    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql: str, params=None):
        cur = self._conn.execute(sql, params or ())
        return _Cursor(cur, backend="sqlite")

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        pass  # Keep connection open for reuse (module-level singleton)

    def closed(self) -> bool:
        return False


def _get_sqlite_db():
    global _sqlite_conn
    if _sqlite_conn is None:
        db_path = get_sqlite_path()
        # If relative path, resolve relative to backend/ directory
        if not os.path.isabs(db_path):
            # Check if running from project root or backend/
            for base in [os.getcwd(), os.path.join(os.path.dirname(__file__), "..")]:
                candidate = os.path.join(base, db_path)
                if os.path.exists(candidate):
                    db_path = candidate
                    break
            else:
                db_path = os.path.join(os.path.dirname(__file__), "..", db_path)
        logger.info(f"Opening SQLite database: {db_path}")
        _sqlite_conn = sqlite3.connect(db_path)
        _sqlite_conn.row_factory = sqlite3.Row
        _sqlite_conn.execute("PRAGMA journal_mode=WAL")
        _sqlite_conn.execute("PRAGMA foreign_keys=ON")
    return _SQLiteDatabase(_sqlite_conn)


# ═══════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════

def get_db():
    """Get a database connection — auto-detects backend from DATABASE_URL."""
    if is_postgres():
        return _get_pg_db()
    return _get_sqlite_db()


def init_db():
    """Initialize database schema. Called once at application startup."""
    from app.tables.pg_schema import init_all_tables

    backend = "postgres" if is_postgres() else "sqlite"
    logger.info(f"Initializing {backend} schema...")

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
