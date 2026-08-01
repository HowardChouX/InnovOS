"""认证测试 fixtures - 使用 SQLite 内存库（替代 mock DB）。

FastAPI Users 的 SQLAlchemy adapter 需要真实 ORM session，
mock DB 模式不兼容，故认证测试用 SQLite 内存库。
"""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# 确保 settings 有值
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-auth-tests")

from app.db.base import Base  # noqa: E402
import app.db.models  # noqa: F401, E402
from app.db.session import get_session  # noqa: E402


@pytest.fixture
def auth_engine():
    """SQLite 内存库 engine，启用 FK 约束。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, conn_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def auth_session(auth_engine):
    Session = sessionmaker(bind=auth_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def auth_app(auth_session):
    """挂载 FastAPI Users 路由的测试 app。"""
    from app.auth.instance import fastapi_users
    from app.auth.backend import auth_backend
    from app.auth.schemas import UserCreate, UserRead, UserUpdate
    from app.auth.exceptions import fastapi_users_exception_handler
    from fastapi_users.exceptions import (
        UserAlreadyExists, UserNotExists, UserInactive,
        UserAlreadyVerified, InvalidVerifyToken,
        InvalidResetPasswordToken, InvalidPasswordException,
    )

    app = FastAPI()
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth/jwt", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/api/auth", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/api/auth", tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/api/users", tags=["users"],
    )

    # Mount custom password-reset router so HTTP route integration tests
    # can exercise the 4 new endpoints (request-otp / resend-otp / verify /
    # set-password) via auth_client without depending on the full app_.
    from app.api.password_reset import router as password_reset_router
    app.include_router(password_reset_router)
    # Register EmailVerificationError handler so route exceptions become
    # proper JSON responses (401 InvalidResetSession, 429 rate-limited, etc.)
    from app.exceptions.email_verification import (
        EmailVerificationError,
        email_verification_exception_handler,
    )
    app.add_exception_handler(EmailVerificationError, email_verification_exception_handler)

    for exc in (UserAlreadyExists, UserNotExists, UserInactive,
                UserAlreadyVerified, InvalidVerifyToken,
                InvalidResetPasswordToken, InvalidPasswordException):
        app.add_exception_handler(exc, fastapi_users_exception_handler)

    app.dependency_overrides[get_session] = lambda: auth_session
    return app


@pytest.fixture
def auth_client(auth_app):
    return TestClient(auth_app)


@pytest.fixture
def seed_user(auth_session):
    """创建一个测试普通用户。"""
    from pwdlib import PasswordHash
    from app.db.models import User
    ph = PasswordHash.recommended()
    user = User(
        email="test@example.com",
        phone="13800000001",
        hashed_password=ph.hash("test1234"),
        is_active=True,
        is_superuser=False,
        is_verified=True,
        role="user",
        token_version=0,
    )
    auth_session.add(user)
    auth_session.commit()
    auth_session.refresh(user)
    return user


@pytest.fixture
def seed_admin(auth_session):
    """创建一个测试管理员。"""
    from pwdlib import PasswordHash
    from app.db.models import User
    ph = PasswordHash.recommended()
    admin = User(
        email="admin@example.com",
        phone="13800000002",
        hashed_password=ph.hash("admin1234"),
        is_active=True,
        is_superuser=True,
        is_verified=True,
        role="admin",
        token_version=0,
    )
    auth_session.add(admin)
    auth_session.commit()
    auth_session.refresh(admin)
    return admin