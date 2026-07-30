"""Tests for EmailVerificationService.

Uses a lightweight SQLite-backed fake DB (psycopg2-compatible cursor API)
so the service's raw SQL can be exercised without PostgreSQL. Patches
``app.database.get_db`` so ``db_session()`` yields the fake.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
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
        # %s → ? (sqlite placeholder)
        out = sql.replace("%s", "?")
        # NOW() → use SQLite current_timestamp (works for the SELECT trick)
        out = out.replace("NOW()", "CURRENT_TIMESTAMP")
        # Strip PostgreSQL FOR UPDATE clause (sqlite has no row locking)
        import re
        out = re.sub(r"\bFOR\s+UPDATE\b", "", out, flags=re.IGNORECASE)
        # PostgreSQL `NOW() <op> (<val> || ' <unit>')::interval`:
        # Collapse to a single datetime() call so the result is a TIMESTAMP
        # value comparable to other TIMESTAMP values in the row.
        out = out.replace(
            "CURRENT_TIMESTAMP + (? || ' seconds')::interval",
            "datetime('now', '+' || ? || ' seconds')",
        )
        out = out.replace(
            "CURRENT_TIMESTAMP - (? || ' days')::interval",
            "datetime('now', '-' || ? || ' days')",
        )
        # Strip any remaining `::type` casts (postgres syntax not in sqlite)
        out = re.sub(r"::\w+", "", out)
        return out

    def execute(self, sql: str, params: tuple | list | None = None):
        from datetime import datetime as _dt, timezone as _tz
        params = tuple(params or ())
        # Special-case: SELECT NOW() AS now — return a real datetime so the
        # service can subtract it from row["last_sent_at"] / "expires_at".
        # Use UTC because SQLite's datetime('now') returns UTC.
        if "SELECT NOW()" in sql.upper():
            self._rows = [_Row({"now": _dt.now(_tz.utc).replace(tzinfo=None)})]
            self.rowcount = 1
            return self
        translated = self._translate(sql)
        cur = self._conn.execute(translated, params)
        rows = cur.fetchall()
        # Parse timestamp-looking strings back to datetime so service
        # arithmetic (e.g. (now - last_sent_at).total_seconds()) works.
        self._rows = []
        for r in rows:
            d = dict(r)
            for k, v in list(d.items()):
                if isinstance(v, str) and v and v[0].isdigit() and len(v) >= 10:
                    # SQLite CURRENT_TIMESTAMP format: "YYYY-MM-DD HH:MM:SS"
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

    def commit(self) -> None:  # not used directly on cursor
        pass


class _FakeSession:
    """Per-call wrapper around the shared SQLite connection.

    Mimics ``_PostgresDatabase``: each ``get_db()`` call returns a fresh
    wrapper, but the underlying SQLite connection is shared across the
    whole fixture. ``close()`` is a no-op (the connection is only closed
    when the fixture tears down).
    """

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
        # No-op: the connection lives for the whole fixture.
        pass


class _FakeDB:
    """Owns the shared in-memory SQLite connection.

    Returned by the ``fake_db`` fixture so tests can pre-seed data.
    Direct calls to its ``execute`` go straight to the SQLite connection.
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
def fake_db(monkeypatch: pytest.MonkeyPatch):
    db = _FakeDB()
    # app.database.get_db is mocked by conftest auto_mock_db; we override it
    # so db_session() yields a fresh wrapper around the shared connection.
    monkeypatch.setattr("app.database.get_db", db.new_session)
    yield db
    db.close()


# ── Email-service stub ──────────────────────────────────────────────────


class _Stub:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_verification_otp_sync(self, user, code, request=None) -> None:  # type: ignore[no-untyped-def]
        self.sent.append((user.email, code))


# ── Helpers ─────────────────────────────────────────────────────────────


def _make_user(_client, db: _FakeDB, email: str = "t@example.com", password: str = "password123") -> int:
    """Insert a user directly via the fake DB.

    ``_client`` is kept for signature compatibility (per Plan notes) but
    is not used.
    """
    from app.db.models import User as OrmUser  # noqa: F401  (sanity import)
    db.execute(
        "INSERT INTO users (email, username, hashed_password, is_active, is_superuser, is_verified) "
        "VALUES (%s, %s, %s, TRUE, FALSE, FALSE)",
        (email, email.split("@")[0], f"hash({password})"),
    )
    db.commit()
    row = db.execute("SELECT id FROM users WHERE email=%s", (email,)).fetchone()
    assert row is not None, "user insert failed"
    return int(row["id"])


# ── Tests ──────────────────────────────────────────────────────────────


def test_issue_and_verify_success(fake_db: _FakeDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """issue_for_user → email stub receives code; verify flips is_verified."""
    from app.core.config import settings
    from app.services.email_service import email_service
    from app.services.email_verification_service import email_verification_service

    stub = _Stub()
    # raising=False because Task 6 will add this method to EmailService;
    # Task 5's service already calls it.
    monkeypatch.setattr(
        email_service, "send_verification_otp_sync", stub.send_verification_otp_sync, raising=False
    )

    user_id = _make_user(None, fake_db, email="t@example.com")
    # Construct a lightweight object with id/email — the service only
    # uses these two attributes.
    user_obj = MagicMock()
    user_obj.id = user_id
    user_obj.email = "t@example.com"

    rec = email_verification_service.issue_for_user(user_obj, request=None)
    assert rec["expires_in"] == settings.OTP_TTL_SECONDS
    assert rec["next_resend_in"] == settings.OTP_RESEND_COOLDOWN
    assert len(stub.sent) == 1
    sent_email, sent_code = stub.sent[-1]
    assert sent_email == "t@example.com"
    assert len(sent_code) == 6 and sent_code.isdigit()

    # Verify the code; user should be flipped to is_verified=TRUE
    result = email_verification_service.verify(user_obj.email, sent_code, request=None)
    assert result == {"verified": True, "already": False}

    row = fake_db.execute(
        "SELECT is_verified, is_active FROM users WHERE id=%s", (user_id,)
    ).fetchone()
    assert row is not None
    assert bool(row["is_verified"]) is True
    assert bool(row["is_active"]) is True


def test_issue_invalidate_previous_unconsumed(fake_db: _FakeDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """A new issue_for_user call should consume all prior unconsumed codes for that user."""
    from app.services.email_service import email_service
    from app.services.email_verification_service import email_verification_service

    stub = _Stub()
    monkeypatch.setattr(
        email_service, "send_verification_otp_sync", stub.send_verification_otp_sync, raising=False
    )

    user_id = _make_user(None, fake_db, email="u2@example.com")
    user_obj = MagicMock()
    user_obj.id = user_id
    user_obj.email = "u2@example.com"

    email_verification_service.issue_for_user(user_obj)
    email_verification_service.issue_for_user(user_obj)

    # Both inserts should exist, but only the latest should be unconsumed.
    rows = fake_db.execute(
        "SELECT id, consumed_at FROM email_verifications WHERE user_id=%s ORDER BY id ASC",
        (user_id,),
    ).fetchall()
    assert len(rows) == 2
    # The first insert was invalidated (consumed_at != NULL) by the second call.
    assert rows[0]["consumed_at"] is not None
    assert rows[1]["consumed_at"] is None


def test_verify_wrong_code_then_correct(fake_db: _FakeDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrong code raises CodeInvalid; subsequent correct code succeeds."""
    import pytest as _pytest

    from app.exceptions.email_verification import CodeInvalid
    from app.services.email_service import email_service
    from app.services.email_verification_service import email_verification_service

    stub = _Stub()
    monkeypatch.setattr(
        email_service, "send_verification_otp_sync", stub.send_verification_otp_sync, raising=False
    )

    user_id = _make_user(None, fake_db, email="u3@example.com")
    user_obj = MagicMock()
    user_obj.id = user_id
    user_obj.email = "u3@example.com"
    email_verification_service.issue_for_user(user_obj)
    correct_code = stub.sent[-1][1]

    with _pytest.raises(CodeInvalid) as exc_info:
        email_verification_service.verify(user_obj.email, "000000")
    assert exc_info.value.detail["remaining"] >= 1

    # The correct code still verifies successfully (attempts < max_attempts).
    result = email_verification_service.verify(user_obj.email, correct_code)
    assert result == {"verified": True, "already": False}


def test_resend_rate_limited(fake_db: _FakeDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """Second resend within cooldown should raise OtpRateLimited."""
    import pytest as _pytest

    from app.exceptions.email_verification import OtpRateLimited
    from app.services.email_service import email_service
    from app.services.email_verification_service import email_verification_service

    stub = _Stub()
    monkeypatch.setattr(
        email_service, "send_verification_otp_sync", stub.send_verification_otp_sync, raising=False
    )

    user_id = _make_user(None, fake_db, email="u4@example.com")
    user_obj = MagicMock()
    user_obj.id = user_id
    user_obj.email = "u4@example.com"

    email_verification_service.issue_for_user(user_obj)
    with _pytest.raises(OtpRateLimited):
        email_verification_service.resend("u4@example.com")


def test_purge_expired(fake_db: _FakeDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """purge_expired removes old consumed/expired rows."""
    from app.services.email_verification_service import email_verification_service

    # Insert two rows: one fresh (no consumed_at), one ancient consumed.
    user_id = _make_user(None, fake_db, email="u5@example.com")
    # Fresh row (issued just now, no consumed_at) — should NOT be purged.
    fake_db.execute(
        "INSERT INTO email_verifications (user_id, email, code_hash, attempts, max_attempts, "
        "expires_at, consumed_at, created_at, last_sent_at) "
        "VALUES (%s, %s, %s, 0, 5, datetime('now', '+1 hour'), NULL, "
        "datetime('now'), datetime('now'))",
        (user_id, "u5@example.com", "hash_fresh"),
    )
    # Old consumed row (40 days ago) — should be purged.
    fake_db.execute(
        "INSERT INTO email_verifications (user_id, email, code_hash, attempts, max_attempts, "
        "expires_at, consumed_at, created_at, last_sent_at) "
        "VALUES (%s, %s, %s, 5, 5, datetime('now', '-40 days'), "
        "datetime('now', '-40 days'), datetime('now', '-40 days'), "
        "datetime('now', '-40 days'))",
        (user_id, "u5@example.com", "hash_old"),
    )
    fake_db.commit()

    deleted = email_verification_service.purge_expired(retention_days=30)
    assert deleted >= 1

    remaining = fake_db.execute(
        "SELECT code_hash FROM email_verifications WHERE user_id=%s", (user_id,)
    ).fetchall()
    remaining_hashes = {r["code_hash"] for r in remaining}
    assert "hash_fresh" in remaining_hashes
    assert "hash_old" not in remaining_hashes


def test_verify_wrong_code_increments_attempts_persisted(fake_db: _FakeDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """错误码后 attempts 必须持久化（验证 db_session 异常回滚不撤销 UPDATE）。"""
    from app.exceptions.email_verification import CodeInvalid
    from app.services.email_service import email_service
    from app.services.email_verification_service import email_verification_service

    class _Stub:
        def __init__(self) -> None:
            self.code: str = ""

        def send_verification_otp_sync(self, user, code, request=None) -> None:
            self.code = code

    stub = _Stub()
    monkeypatch.setattr(
        email_service, "send_verification_otp_sync", stub.send_verification_otp_sync, raising=False
    )

    from app.database import db_session
    from fastapi_users.password import PasswordHelper
    pw = PasswordHelper()
    with db_session() as db:
        db.execute(
            "INSERT INTO users (email, username, hashed_password, is_active, is_superuser, is_verified) "
            "VALUES (%s, %s, %s, TRUE, FALSE, FALSE)",
            ("att@x.com", "att", pw.hash("password123")),
        )
        uid = db.execute("SELECT id FROM users WHERE email=%s", ("att@x.com",)).fetchone()["id"]
    from app.db.models import User
    user = User(id=uid, email="att@x.com")  # type: ignore[call-arg]
    email_verification_service.issue_for_user(user)
    correct_code = stub.code

    # 提交一次错误码
    try:
        email_verification_service.verify("att@x.com", "000000")
    except CodeInvalid:
        pass

    # 断言 attempts 持久化为 1（如果 db_session 回滚了 UPDATE，这里会是 0）
    with db_session() as db:
        row = db.execute(
            "SELECT attempts FROM email_verifications WHERE email=%s AND consumed_at IS NULL ORDER BY id DESC LIMIT 1",
            ("att@x.com",),
        ).fetchone()
    assert row is not None, "active OTP row should exist"
    assert row["attempts"] == 1, f"attempts should be persisted as 1, got {row['attempts']}"

    # 验证正确码仍能成功
    result = email_verification_service.verify("att@x.com", correct_code)
    assert result == {"verified": True, "already": False}

    # 注意：此测试依赖 fake session 的行为。如果 fake session 在异常时不 rollback
    # （与真实 db_session 不同），测试仍可能假绿。已知 _FakeSession 的 rollback()
    # 调用 sqlite3.Connection.rollback() 可撤销未提交的 UPDATE，语义正确。
    # 如需完全验证回滚语义，需真实 PG 覆盖。


def test_5_wrong_attempts_exhaust(fake_db: _FakeDB, monkeypatch: pytest.MonkeyPatch) -> None:
    """5 次错误码后 CodeExhausted，第 6 次直接 CodeExpired（已作废）。"""
    import pytest as _pytest

    from app.exceptions.email_verification import CodeExhausted, CodeExpired, CodeInvalid
    from app.services.email_verification_service import email_verification_service as ev
    from app.services.email_service import email_service

    class _Stub:
        def __init__(self) -> None:
            self.code: str = ""

        def send_verification_otp_sync(self, user, code, request=None) -> None:
            self.code = code

    stub = _Stub()
    monkeypatch.setattr(
        email_service, "send_verification_otp_sync", stub.send_verification_otp_sync, raising=False
    )

    user_id = _make_user(None, fake_db, email="e5@x.com")
    user_obj = MagicMock()
    user_obj.id = user_id
    user_obj.email = "e5@x.com"
    ev.issue_for_user(user_obj)

    # 前 4 次错误码 -> CodeInvalid（attempts 1->4）
    for i in range(4):
        with _pytest.raises(CodeInvalid):
            ev.verify("e5@x.com", "000000")
    # 第 5 次错误码 -> CodeExhausted（attempts=5=max，作废）
    with _pytest.raises(CodeExhausted):
        ev.verify("e5@x.com", "000000")
    # 第 6 次 -> CodeExpired（已作废，无活跃 row）
    with _pytest.raises(CodeExpired):
        ev.verify("e5@x.com", "111111")


# ── Route-level tests (HTTP contract via mocked service) ──────────────────

from fastapi.testclient import TestClient


def _client():
    from app.main import app_
    return TestClient(app_)


def test_request_endpoint_returns_202(monkeypatch):
    """Unknown email returns 202 (防探测)."""
    from app.exceptions.email_verification import EmailNotFound
    from app.services.email_verification_service import email_verification_service
    from unittest.mock import MagicMock

    mock = MagicMock(side_effect=EmailNotFound())
    monkeypatch.setattr(email_verification_service, "resend", mock)

    c = _client()
    r = c.post(
        "/api/auth/email-verifications/request",
        json={"email": "noone@x.com"},
    )
    # 邮箱不存在返回 202（防探测）
    assert r.status_code == 202


def test_resend_endpoint_rate_limits(monkeypatch):
    """Second resend within cooldown returns 429."""
    from app.exceptions.email_verification import OtpRateLimited
    from app.services.email_verification_service import email_verification_service
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.side_effect = [
        {"expires_in": 600, "next_resend_in": 60},
        OtpRateLimited(30),
    ]
    monkeypatch.setattr(email_verification_service, "resend", mock)

    c = _client()
    r1 = c.post(
        "/api/auth/email-verifications/resend",
        json={"email": "rl@example.com"},
    )
    assert r1.status_code == 202
    r2 = c.post(
        "/api/auth/email-verifications/resend",
        json={"email": "rl@example.com"},
    )
    assert r2.status_code == 429


def test_verify_endpoint_wrong_code_returns_400(monkeypatch):
    """Wrong code returns 400."""
    from app.exceptions.email_verification import CodeInvalid
    from app.services.email_verification_service import email_verification_service
    from unittest.mock import MagicMock

    mock = MagicMock(side_effect=CodeInvalid(4))
    monkeypatch.setattr(email_verification_service, "verify", mock)

    c = _client()
    r = c.post(
        "/api/auth/email-verifications/verify",
        json={"email": "vc@example.com", "code": "000000"},
    )
    assert r.status_code == 400


def test_verify_endpoint_expired_code_returns_410(monkeypatch):
    """CodeExpired -> 410（路由层 mock service，验证 HTTP 契约）。"""
    from app.exceptions.email_verification import CodeExpired
    from app.services.email_verification_service import email_verification_service

    def _raise(*args, **kwargs):
        raise CodeExpired()

    monkeypatch.setattr(email_verification_service, "verify", _raise)

    c = _client()
    r = c.post(
        "/api/auth/email-verifications/verify",
        json={"email": "ex@x.com", "code": "111111"},
    )
    assert r.status_code == 410
    assert r.json()["code"] == "CODE_EXPIRED"


def test_login_requires_verification():
    """未验证用户登录被拒（requires_verification=True on auth router）。"""
    import os
    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-auth-tests")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.auth.backend import auth_backend
    from app.auth.exceptions import fastapi_users_exception_handler
    from app.auth.instance import fastapi_users
    from app.auth.schemas import UserCreate, UserRead, UserUpdate
    from app.db.base import Base
    import app.db.models  # noqa: F401  (ensure models are loaded)
    from app.db.session import get_session
    from fastapi_users.exceptions import (
        InvalidPasswordException,
        InvalidResetPasswordToken,
        InvalidVerifyToken,
        UserAlreadyExists,
        UserAlreadyVerified,
        UserInactive,
        UserNotExists,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _conn_record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    app = FastAPI()
    app.include_router(
        fastapi_users.get_auth_router(auth_backend, requires_verification=True),
        prefix="/api/auth/jwt", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth", tags=["auth"],
    )
    for exc in (UserAlreadyExists, UserNotExists, UserInactive,
                UserAlreadyVerified, InvalidVerifyToken,
                InvalidResetPasswordToken, InvalidPasswordException):
        app.add_exception_handler(exc, fastapi_users_exception_handler)

    app.dependency_overrides[get_session] = lambda: session

    c = TestClient(app)

    # 注册一个未验证用户 -> 注册成功返回 201
    r = c.post("/api/auth/register", json={"email": "nr@x.com", "password": "password123"})
    assert r.status_code == 201, f"注册应成功: {r.json()}"

    # 登录未验证用户 -> 400（UserInactive）
    r = c.post(
        "/api/auth/jwt/login",
        data={"username": "nr@x.com", "password": "password123"},
    )
    assert r.status_code == 400, f"未验证用户登录应被拒: {r.json()}"

    session.close()
    Base.metadata.drop_all(engine)


# ── Error-code matrix (reviewer I4) ─────────────────────────────────────


def test_email_not_found_resend_raises(fake_db: _FakeDB) -> None:
    """未注册邮箱调 resend → EmailNotFound."""
    from app.exceptions.email_verification import EmailNotFound
    from app.services.email_verification_service import email_verification_service

    import pytest

    with pytest.raises(EmailNotFound):
        email_verification_service.resend("noone@x.com")


def test_already_verified_resend_raises(fake_db: _FakeDB) -> None:
    """已验证邮箱调 resend → AlreadyVerified."""
    from app.database import db_session
    from app.exceptions.email_verification import AlreadyVerified
    from app.services.email_verification_service import email_verification_service
    from fastapi_users.password import PasswordHelper

    import pytest

    pw = PasswordHelper()
    with db_session() as db:
        db.execute(
            "INSERT INTO users (email, username, hashed_password, is_active, is_superuser, is_verified) "
            "VALUES (%s, %s, %s, TRUE, FALSE, TRUE)",
            ("av@x.com", "av", pw.hash("password123")),
        )
    with pytest.raises(AlreadyVerified):
        email_verification_service.resend("av@x.com")


def test_login_succeeds_when_verified() -> None:
    """已验证用户登录应成功。"""
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
    os.environ.setdefault("SECRET_KEY", "test-secret-key-for-auth-tests")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.auth.backend import auth_backend
    from app.auth.exceptions import fastapi_users_exception_handler
    from app.auth.instance import fastapi_users
    from app.auth.schemas import UserCreate, UserRead, UserUpdate
    from app.db.base import Base
    import app.db.models  # noqa: F401
    from app.db.session import get_session
    from fastapi_users.exceptions import (
        InvalidPasswordException,
        InvalidResetPasswordToken,
        InvalidVerifyToken,
        UserAlreadyExists,
        UserAlreadyVerified,
        UserInactive,
        UserNotExists,
    )

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _conn_record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    app = FastAPI()
    app.include_router(
        fastapi_users.get_auth_router(auth_backend, requires_verification=True),
        prefix="/api/auth/jwt", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth", tags=["auth"],
    )
    for exc in (
        UserAlreadyExists, UserNotExists, UserInactive,
        UserAlreadyVerified, InvalidVerifyToken,
        InvalidResetPasswordToken, InvalidPasswordException,
    ):
        app.add_exception_handler(exc, fastapi_users_exception_handler)

    app.dependency_overrides[get_session] = lambda: session

    c = TestClient(app)

    # 注册未验证用户
    r = c.post("/api/auth/register", json={"email": "ov@x.com", "password": "password123"})
    assert r.status_code == 201

    # 直接 DB 标记已验证
    session.execute(text("UPDATE users SET is_verified=TRUE WHERE email='ov@x.com'"))
    session.commit()

    # 验证用户登录应成功
    r = c.post(
        "/api/auth/jwt/login",
        data={"username": "ov@x.com", "password": "password123"},
    )
    assert r.status_code in (200, 204), f"已验证用户登录应成功: {r.status_code} {r.json() if r.content else ''}"

    session.close()
    Base.metadata.drop_all(engine)


def test_email_unavailable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """未配 SMTP + ENVIRONMENT=production + EMAIL_OTP_SOFT_FAIL=False → EmailUnavailable."""
    from app.exceptions.email_verification import EmailUnavailable
    from app.services import email_service as es

    monkeypatch.setattr(es.settings, "SMTP_HOST", "")
    monkeypatch.setattr(es.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(es.settings, "EMAIL_OTP_SOFT_FAIL", False)

    import pytest

    class _U:
        email = "x@y.com"

    with pytest.raises(EmailUnavailable):
        es.email_service.send_verification_otp_sync(_U(), "123456")