"""
Auth API tests — SQLModel-based with file-backed SQLite.

Uses a temporary SQLite database file to test SQLModel operations
without requiring PostgreSQL. Each test module creates one database
and reuses it across tests.
"""
import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.security import get_password_hash


@pytest.fixture(scope="module")
def db_path():
    """Create a temporary SQLite database file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    path = tmp.name
    tmp.close()

    # Must import User model before create_all to register it with metadata
    from app.models.user import User  # noqa: F401
    engine = create_engine(f"sqlite:///{path}")
    SQLModel.metadata.create_all(engine)
    yield path, engine
    os.unlink(path)


@pytest.fixture
def client(db_path):
    """Create a TestClient that uses the file-backed SQLite database.

    Uses FastAPI's dependency_overrides to replace the get_db
    dependency with a SQLite-based session.
    """
    path, engine = db_path

    from app.core.db import get_db

    def _mock_get_db():
        with Session(engine) as session:
            yield session

    from fastapi import FastAPI
    from app.api.auth import router

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db] = _mock_get_db
    return TestClient(test_app)


@pytest.fixture
def seeded_user(db_path, client):
    """Insert a test user directly into the SQLite database.

    Idempotent: reuses an existing user if the username is already taken.
    Uses a unique username that won't conflict with register tests.
    """
    path, engine = db_path
    with Session(engine) as session:
        from app.models.user import User
        from sqlmodel import select
        existing = session.exec(select(User).where(User.username == "seeduser")).first()
        if existing:
            return existing
        user = User(
            username="seeduser",
            password_hash=get_password_hash("test1234"),
            role="user",
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


class TestRegister:
    """注册接口测试"""

    def test_register_short_username(self, client):
        """Pydantic validation rejects < 2 char username with 422."""
        resp = client.post("/api/auth/register", json={
            "username": "a",
            "password": "test1234",
        })
        assert resp.status_code == 422

    def test_register_short_password(self, client):
        """Pydantic validation rejects < 8 char password with 422."""
        resp = client.post("/api/auth/register", json={
            "username": "testuser",
            "password": "12",
        })
        assert resp.status_code == 422

    def test_register_duplicate_username(self, client, seeded_user):
        """Business logic rejects duplicate username with 400."""
        resp = client.post("/api/auth/register", json={
            "username": "seeduser",  # already created by seeded_user fixture
            "password": "test1234",
        })
        assert resp.status_code == 400, resp.text
        assert "用户名已存在" in resp.json()["detail"]

    def test_register_success(self, client):
        """Successful registration returns 200 with token + user."""
        resp = client.post("/api/auth/register", json={
            "username": "newuser",
            "password": "test1234",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "newuser"
        assert data["user"]["role"] == "user"
        assert data["user"]["id"] is not None


class TestLogin:
    """登录接口测试"""

    def test_login_invalid_credentials(self, client):
        """Wrong password returns 401."""
        resp = client.post("/api/auth/login", json={
            "username": "nonexistent",
            "password": "wrong",
        })
        assert resp.status_code == 401
        assert "用户名或密码错误" in resp.json()["detail"]

    def test_login_success(self, client, seeded_user):
        """Valid credentials return 200 with access_token."""
        resp = client.post("/api/auth/login", json={
            "username": "seeduser",
            "password": "test1234",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["username"] == "seeduser"

    def test_login_admin(self, client, monkeypatch):
        """Admin login via .env credentials."""
        # Must patch both the original module AND the importing module
        # since app.api.auth imports _verify_admin_credentials at import time
        import app.auth
        import app.api.auth
        mock_fn = lambda u, p: u == "admin" and p == "adminpass"
        monkeypatch.setattr(app.auth, "_verify_admin_credentials", mock_fn)
        monkeypatch.setattr(app.api.auth, "_verify_admin_credentials", mock_fn)
        resp = client.post("/api/auth/login", json={
            "username": "admin",
            "password": "adminpass",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["role"] == "admin"


class TestMe:
    """当前用户接口测试"""

    def test_me_requires_token(self, client):
        """No auth header returns 401."""
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self, client, seeded_user):
        """Valid JWT returns the user profile."""
        from app.auth import create_access_token
        token = create_access_token({"user_id": seeded_user.id, "role": "user"})

        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["username"] == "seeduser"
        assert data["role"] == "user"
        assert data["id"] is not None
