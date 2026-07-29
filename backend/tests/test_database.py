"""
Tests for app/database.py — _Row, _Cursor, query parameter rewriting, db_session behavior.
"""

import importlib
import sys
from unittest.mock import MagicMock, PropertyMock, patch

import psycopg2
import psycopg2.extras
import pytest

from app.database import (
    _Cursor,
    _PostgresDatabase,
    _Row,
    _get_pg_db,
    db_session,
    get_db,
    init_db,
    pool_usage,
)


class TestRow:
    """_Row — dict subclass that also supports integer index access."""

    def test_dict_access(self):
        row = _Row({"id": 1, "name": "test"})
        assert row["id"] == 1
        assert row["name"] == "test"

    def test_integer_index_access(self):
        row = _Row({"id": 1, "name": "test"})
        assert row[0] == 1
        assert row[1] == "test"

    def test_inherits_dict_methods(self):
        row = _Row({"a": 1, "b": 2})
        assert list(row.keys()) == ["a", "b"]
        assert list(row.values()) == [1, 2]

    def test_get_method(self):
        row = _Row({"id": 1})
        assert row.get("id") == 1
        assert row.get("missing", "default") == "default"

    def test_empty_row(self):
        row = _Row({})
        assert len(row) == 0

    def test_contains(self):
        row = _Row({"id": 1})
        assert "id" in row
        assert "missing" not in row


class TestCursor:
    """_Cursor — wraps psycopg2 cursor with ?→%s rewriting and _Row returns."""

    @pytest.fixture
    def mock_psycopg2_cursor(self):
        return MagicMock()

    @pytest.fixture
    def cursor(self, mock_psycopg2_cursor):
        return _Cursor(mock_psycopg2_cursor)

    def test_execute_rewrites_qmark_to_percent_s(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.execute.return_value = mock_psycopg2_cursor
        result = cursor.execute("SELECT * FROM users WHERE id = ? AND name = ?", (1, "test"))
        mock_psycopg2_cursor.execute.assert_called_once_with(
            "SELECT * FROM users WHERE id = %s AND name = %s", (1, "test")
        )
        assert result is cursor

    def test_execute_no_params(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.execute.return_value = mock_psycopg2_cursor
        cursor.execute("SELECT 1")
        mock_psycopg2_cursor.execute.assert_called_once_with("SELECT 1", None)

    def test_execute_none_params(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.execute.return_value = mock_psycopg2_cursor
        cursor.execute("SELECT 1", None)
        mock_psycopg2_cursor.execute.assert_called_once_with("SELECT 1", None)

    def test_fetchone_returns_row(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.fetchone.return_value = {"id": 1, "name": "test"}
        row = cursor.fetchone()
        assert isinstance(row, _Row)
        assert row["id"] == 1
        assert row["name"] == "test"

    def test_fetchone_none_returns_none(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.fetchone.return_value = None
        assert cursor.fetchone() is None

    def test_fetchall_returns_rows(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.fetchall.return_value = [{"id": 1}, {"id": 2}]
        rows = cursor.fetchall()
        assert len(rows) == 2
        assert all(isinstance(r, _Row) for r in rows)
        assert rows[0]["id"] == 1
        assert rows[1]["id"] == 2

    def test_fetchall_empty(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.fetchall.return_value = []
        assert cursor.fetchall() == []

    def test_iteration(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.__iter__.return_value = iter([{"id": 1}, {"id": 2}])
        rows = list(cursor)
        assert len(rows) == 2
        assert rows[0]["id"] == 1

    def test_rowcount_property(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.rowcount = 5
        assert cursor.rowcount == 5

    def test_description_property(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.description = [("id",), ("name",)]
        assert cursor.description == [("id",), ("name",)]

    def test_lastrowid_property(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.lastrowid = 42
        assert cursor.lastrowid == 42

    def test_multiple_question_marks(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.execute.return_value = mock_psycopg2_cursor
        cursor.execute("INSERT INTO t (a, b, c) VALUES (?, ?, ?)", (1, 2, 3))
        mock_psycopg2_cursor.execute.assert_called_once_with(
            "INSERT INTO t (a, b, c) VALUES (%s, %s, %s)", (1, 2, 3)
        )

    def test_sql_without_qmark_unchanged(self, cursor, mock_psycopg2_cursor):
        mock_psycopg2_cursor.execute.return_value = mock_psycopg2_cursor
        cursor.execute("SELECT 1 AS num")
        mock_psycopg2_cursor.execute.assert_called_once_with("SELECT 1 AS num", None)


class TestPostgresDatabase:
    """_PostgresDatabase — connection wrapper."""

    @pytest.fixture
    def mock_conn(self):
        conn = MagicMock()
        conn.cursor.return_value = MagicMock()
        return conn

    def test_execute_creates_real_dict_cursor(self, mock_conn):
        db = _PostgresDatabase(mock_conn)
        db.execute("SELECT 1")
        mock_conn.cursor.assert_called_once_with(cursor_factory=psycopg2.extras.RealDictCursor)

    def test_execute_returns_cursor(self, mock_conn):
        db = _PostgresDatabase(mock_conn)
        result = db.execute("SELECT 1")
        assert isinstance(result, _Cursor)

    def test_commit(self, mock_conn):
        db = _PostgresDatabase(mock_conn)
        db.commit()
        mock_conn.commit.assert_called_once()

    def test_rollback(self, mock_conn):
        db = _PostgresDatabase(mock_conn)
        db.rollback()
        mock_conn.rollback.assert_called_once()

    def test_close_returns_to_pool(self, mock_conn):
        mock_pool = MagicMock()
        with patch("app.database._pg_pool", mock_pool):
            db = _PostgresDatabase(mock_conn)
            db.close()
            mock_pool.putconn.assert_called_once_with(mock_conn)

    def test_close_fallback_on_error(self, mock_conn):
        mock_pool = MagicMock()
        mock_pool.putconn.side_effect = Exception("pool error")
        with patch("app.database._pg_pool", mock_pool):
            db = _PostgresDatabase(mock_conn)
            db.close()  # should not raise
            mock_conn.close.assert_called_once()


class TestGetDB:
    """get_db() and _get_pg_db() — connection acquisition."""

    def test_get_db_returns_postgres_database(self, monkeypatch):
        mock_conn = MagicMock()
        mock_pool = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        monkeypatch.setattr("app.database._pg_pool", mock_pool)
        db = get_db()
        assert isinstance(db, _PostgresDatabase)

    def test_get_db_initializes_pool_if_none(self, monkeypatch):
        """If _pg_pool is None, get_db should initialize it."""
        monkeypatch.setattr("app.database._pg_pool", None)
        monkeypatch.setattr("app.database.DATABASE_URL", "postgresql://test:test@localhost/test")

        mock_pool_instance = MagicMock()
        mock_pool_class = MagicMock(return_value=mock_pool_instance)

        # _get_pg_db does "from psycopg2 import pool as _pool" at runtime.
        # psycopg2.pool exists as a submodule but not as an attribute on the
        # parent module until imported. We import it first, then monkeypatch.
        import psycopg2.pool as psycopg2_pool
        monkeypatch.setattr(psycopg2_pool, "ThreadedConnectionPool", mock_pool_class)

        db = get_db()
        mock_pool_class.assert_called_once_with(1, 50, "postgresql://test:test@localhost/test")
        assert isinstance(db, _PostgresDatabase)

    def test_empty_database_url_raises(self, monkeypatch):
        monkeypatch.setattr("app.database._pg_pool", None)
        monkeypatch.setattr("app.database.DATABASE_URL", "")
        with pytest.raises(RuntimeError, match="DATABASE_URL environment variable not set"):
            _get_pg_db()


class TestDBSession:
    """db_session() — context manager with auto commit/rollback/close."""

    def test_successful_session_commits(self):
        mock_db = MagicMock(spec=_PostgresDatabase)
        with patch("app.database.get_db", return_value=mock_db):
            with db_session() as db:
                db.execute("SELECT 1")
        mock_db.commit.assert_called_once()
        mock_db.rollback.assert_not_called()
        mock_db.close.assert_called_once()

    def test_exception_causes_rollback(self):
        mock_db = MagicMock(spec=_PostgresDatabase)
        with patch("app.database.get_db", return_value=mock_db):
            with pytest.raises(ValueError, match="test error"):
                with db_session() as db:
                    db.execute("SELECT 1")
                    raise ValueError("test error")
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()
        mock_db.commit.assert_not_called()

    def test_rollback_closes_on_exception(self):
        """Even if rollback raises, close should still be called (rollback exception propagates)."""
        mock_db = MagicMock(spec=_PostgresDatabase)
        mock_db.rollback.side_effect = Exception("rollback failed")
        with patch("app.database.get_db", return_value=mock_db):
            with pytest.raises(Exception):
                with db_session() as db:
                    raise ValueError("test error")
        # close should be called even though rollback also failed
        assert mock_db.close.called


class TestPoolUsage:
    """pool_usage() — health monitoring stats."""

    def test_pool_not_initialized(self, monkeypatch):
        monkeypatch.setattr("app.database._pg_pool", None)
        assert pool_usage() == {"status": "not_initialized"}

    def test_pool_initialized(self, monkeypatch):
        mock_pool = MagicMock()
        mock_pool._used = 3
        mock_pool._maxconn = 50
        monkeypatch.setattr("app.database._pg_pool", mock_pool)
        result = pool_usage()
        assert result["status"] == "ok"
        assert result["used"] == 3
        assert result["max"] == 50


class TestInitDB:
    """init_db() — schema initialization at startup."""

    def test_init_db_calls_init_all_tables(self, monkeypatch):
        mock_db = MagicMock(spec=_PostgresDatabase)
        mock_init_all = MagicMock()
        monkeypatch.setattr("app.database.get_db", lambda: mock_db)
        monkeypatch.setattr("app.tables.pg_schema.init_all_tables", mock_init_all)
        init_db()
        mock_init_all.assert_called_once_with(mock_db)
        assert mock_db.commit.call_count == 2  # init_all_tables 提交 + purge_expired 提交
        assert mock_db.close.call_count == 2  # 对应的两次 close

    def test_init_db_rollback_on_failure(self, monkeypatch):
        mock_db = MagicMock(spec=_PostgresDatabase)
        monkeypatch.setattr("app.database.get_db", lambda: mock_db)
        monkeypatch.setattr(
            "app.tables.pg_schema.init_all_tables",
            MagicMock(side_effect=RuntimeError("schema fail")),
        )
        with pytest.raises(RuntimeError, match="schema fail"):
            init_db()
        mock_db.rollback.assert_called_once()
        mock_db.close.assert_called_once()
