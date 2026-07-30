"""密码重置 OTP 链路测试 — purpose 隔离 + reset_session 一次性消费。

Step 1: 写失败测试,先确认红。
Step 2: 改 EmailVerificationService 加 OtpPurpose 后应全绿。

测试用 SQLite-backed fake DB(参考 tests/test_email_verification.py 的 _FakeDB),
让 EmailVerificationService 的原生 SQL 能在不依赖 PostgreSQL 的情况下跑通。
"""
from __future__ import annotations

import sqlite3
from datetime import datetime as _dt, timezone as _tz
from unittest.mock import MagicMock

import pytest


# ── SQLite-backed fake DB mimicking psycopg2 cursor API ──────────────────


class _Row(dict):
    """Dict row that mimics psycopg2.extras.DictRow (string keys)."""


class _Cursor:
    """SQLite-backed cursor with psycopg2-style fetchone/fetchall/rowcount."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self._rows: list[_Row] = []
        self.rowcount: int = 0

    def _translate(self, sql: str) -> str:
        out = sql.replace("%s", "?")
        out = out.replace("NOW()", "CURRENT_TIMESTAMP")
        import re
        out = re.sub(r"\bFOR\s+UPDATE\b", "", out, flags=re.IGNORECASE)
        out = out.replace(
            "CURRENT_TIMESTAMP + (? || ' seconds')::interval",
            "datetime('now', '+' || ? || ' seconds')",
        )
        out = out.replace(
            "CURRENT_TIMESTAMP - (? || ' days')::interval",
            "datetime('now', '-' || ? || ' days')",
        )
        out = re.sub(r"::\w+", "", out)
        return out

    def execute(self, sql: str, params: tuple | list | None = None):
        params = tuple(params or ())
        if "SELECT NOW()" in sql.upper():
            self._rows = [_Row({"now": _dt.now(_tz.utc).replace(tzinfo=None)})]
            self.rowcount = 1
            return self
        translated = self._translate(sql)
        cur = self._conn.execute(translated, params)
        rows = cur.fetchall()
        self._rows = []
        for r in rows:
            d = dict(r)
            for k, v in list(d.items()):
                if isinstance(v, str) and v and v[0].isdigit() and len(v) >= 10:
                    try:
                        d[k] = _dt.strptime(v[:19], "%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        pass
            self._rows.append(_Row(d))
        self.rowcount = cur.rowcount
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeSession:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple | list | None = None):
        cur = _Cursor(self._conn)
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        pass


class _FakeDB:
    """Owns the shared in-memory SQLite connection.

    Mirrors the email_verifications table schema with a `purpose` column
    (added in Task 1).
    """

    def __init__(self) -> None:
        self._conn = sqlite3.connect(":memory:")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                username TEXT,
                hashed_password TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_superuser INTEGER NOT NULL DEFAULT 0,
                is_verified INTEGER NOT NULL DEFAULT 0,
                role TEXT NOT NULL DEFAULT 'user',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT
            );
            CREATE TABLE email_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 5,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
                purpose TEXT NOT NULL DEFAULT 'email_verification'
            );
            """
        )
        self._conn.commit()

    def execute(self, sql: str, params: tuple | list | None = None):
        cur = _Cursor(self._conn)
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()

    def new_session(self) -> _FakeSession:
        return _FakeSession(self._conn)


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch):
    """SQLite-backed fake DB,monkeypatch app.database.get_db 指向它。"""
    fake = _FakeDB()
    monkeypatch.setattr("app.database.get_db", fake.new_session)
    yield fake
    fake.close()


@pytest.fixture
def make_user(db):
    """插入测试用户,返回 email + user_id。"""
    created = []

    def _make(email: str, is_verified: bool = True) -> dict:
        db.execute(
            "INSERT INTO users (email, username, hashed_password, is_active, is_verified, is_superuser) "
            "VALUES (%s, %s, %s, 1, %s, 0)",
            (email, email.split("@")[0], "fakehash", 1 if is_verified else 0),
        )
        db.commit()
        row = db.execute("SELECT id, email FROM users WHERE email=%s", (email,)).fetchone()
        created.append(email)
        return row

    yield _make

    for email in created:
        db.execute("DELETE FROM email_verifications WHERE email=%s", (email,))
        db.execute("DELETE FROM users WHERE email=%s", (email,))
    db.commit()


# ── Email-service stub ──────────────────────────────────────────────────


class _Stub:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_verification_otp_sync(self, user, code, request=None) -> None:
        self.sent.append((user.email, code))

    def send_password_reset_otp_sync(self, user, code, request=None) -> None:
        self.sent.append((user.email, code))


# ── Tests ───────────────────────────────────────────────────────────────


class TestPurposeIsolation:
    def test_request_otp_creates_password_reset_purpose_row(
        self, db, make_user, monkeypatch: pytest.MonkeyPatch
    ):
        """下发 password_reset OTP,DB 行 purpose 字段必须正确。"""
        from app.services.email_service import email_service
        from app.services.email_verification_service import EmailVerificationService, OtpPurpose

        stub = _Stub()
        monkeypatch.setattr(
            email_service, "send_password_reset_otp_sync",
            stub.send_password_reset_otp_sync, raising=False,
        )
        # 防止默认发 verification OTP 也触发 stub 写错
        monkeypatch.setattr(
            email_service, "send_verification_otp_sync",
            stub.send_verification_otp_sync, raising=False,
        )

        row = make_user("isolation@example.com")
        svc = EmailVerificationService()

        class _U:
            email = "isolation@example.com"
            id = row["id"]

        svc.issue_for_user(_U(), request=None, purpose=OtpPurpose.PASSWORD_RESET)
        ev_row = db.execute(
            "SELECT purpose FROM email_verifications "
            "WHERE email=%s ORDER BY id DESC LIMIT 1",
            ("isolation@example.com",),
        ).fetchone()
        assert ev_row["purpose"] == "password_reset", (
            f"purpose 应为 password_reset,实际 {ev_row['purpose']}"
        )

    def test_email_verification_otp_cannot_reset_password(
        self, db, make_user, monkeypatch: pytest.MonkeyPatch
    ):
        """用 email_verification 类型的 OTP 调重置 verify → 抛 CodeExpired/Invalid/Exhausted。"""
        from app.services.email_service import email_service
        from app.services.email_verification_service import EmailVerificationService, OtpPurpose

        stub = _Stub()
        monkeypatch.setattr(
            email_service, "send_verification_otp_sync",
            stub.send_verification_otp_sync, raising=False,
        )
        monkeypatch.setattr(
            email_service, "send_password_reset_otp_sync",
            stub.send_password_reset_otp_sync, raising=False,
        )

        row = make_user("cross1@example.com")
        svc = EmailVerificationService()

        class _U:
            email = "cross1@example.com"
            id = row["id"]

        svc.issue_for_user(_U(), request=None, purpose=OtpPurpose.EMAIL_VERIFICATION)

        with pytest.raises((CodeExpiredE, CodeInvalidE, CodeExhaustedE)):
            svc.verify(
                "cross1@example.com", "000000",
                purpose=OtpPurpose.PASSWORD_RESET,
            )


# Local aliases to avoid leaking names at module level for pytest collection
from app.exceptions.email_verification import (
    CodeExpired as CodeExpiredE,
    CodeInvalid as CodeInvalidE,
    CodeExhausted as CodeExhaustedE,
)
