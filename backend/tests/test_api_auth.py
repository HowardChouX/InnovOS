"""
Auth API tests — mock DB (SQLModel removed).

Uses a lightweight mock database that mimics the psycopg2 wrapper
to test auth routes without requiring PostgreSQL.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash


class MockRow(dict):
    """Dict row that supports both string and integer indexing (mimics _Row)."""

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]
        return super().__getitem__(key)


class MockDB:
    """In-memory mock database that mimics _PostgresDatabase API."""

    def __init__(self):
        self._users: dict[int, dict] = {}
        self._next_id = 1
        self._last_result: list[MockRow] = []

    def _parse_where(self, sql: str, params: tuple | None) -> dict:
        """Naive WHERE clause parser — handles simple `col = ?` only."""
        where = {}
        if params is None:
            return where
        parts = sql.split("WHERE")
        if len(parts) < 2:
            return where
        conditions = parts[1].strip()
        # Simple parser: AND-separated col = ? or col=? patterns
        i = 0
        for clause in conditions.replace("= ?", "=?").split("AND"):
            clause = clause.strip()
            if "=?" in clause:
                col = clause.split("=")[0].strip()
                if i < len(params):
                    where[col] = params[i]
                    i += 1
        return where

    def execute(self, sql: str, params: tuple | None = None):
        self._last_result = []

        if sql.startswith("SELECT") and "FROM users" in sql:
            where = self._parse_where(sql, params)
            matching = list(self._users.values())
            for col, val in where.items():
                matching = [u for u in matching if u.get(col) == val]
            if "ORDER BY" in sql:
                desc = "DESC" in sql.upper()
                matching = sorted(matching, key=lambda x: str(x.get("created_at", "") or ""), reverse=desc)
            self._last_result = [MockRow(u.copy()) for u in matching]

        elif sql.startswith("INSERT") and "INTO users" in sql:
            import re

            m = re.search(r"\(([^)]+)\)\s*VALUES", sql)
            cols = [c.strip() for c in m.group(1).split(",") if c.strip()] if m else []

            now = "2024-01-01 00:00:00"
            user = {
                "id": self._next_id,
                "username": "",
                "password_hash": "",
                "role": "user",
                "email": "",
                "is_active": 1,
                "created_at": now,
            }
            if params:
                for i, col in enumerate(cols):
                    if i < len(params):
                        user[col] = params[i]

            self._users[self._next_id] = user
            self._next_id += 1

            # Handle RETURNING clause
            if "RETURNING" in sql:
                ret_part = sql.split("RETURNING")[1].strip()
                ret_cols = [c.strip() for c in ret_part.split(",")]
                ret_row = {c: user.get(c) for c in ret_cols}
                self._last_result = [MockRow(ret_row)]
            else:
                self._last_result = []

        elif sql.startswith("UPDATE") and "users" in sql:
            set_part = sql.split("SET")[1].split("WHERE")[0] if "WHERE" in sql else sql.split("SET")[1]
            set_cols = []
            set_vals = []
            for assignment in set_part.split(","):
                if "=?" in assignment or "= ?" in assignment:
                    col = assignment.split("=")[0].strip()
                    set_cols.append(col)

            where = self._parse_where(sql, params)
            if params and set_cols:
                val_idx = 0
                for col in set_cols:
                    if val_idx < len(params):
                        set_vals.append((col, params[val_idx]))
                        val_idx += 1
                # remaining params are for WHERE
                where_params = params[val_idx:] if val_idx < len(params) else ()
                where = self._parse_where(sql.replace("?", "%s") if val_idx > 0 else sql, where_params or None)

            for uid, u in self._users.items():
                match = True
                for col, val in where.items():
                    if u.get(col) != val:
                        match = False
                        break
                if match:
                    for col, val in set_vals:
                        self._users[uid][col] = val

        elif sql.startswith("DELETE") and "FROM users" in sql:
            where = self._parse_where(sql, params)
            to_delete = []
            for uid, u in self._users.items():
                match = True
                for col, val in where.items():
                    if u.get(col) != val:
                        match = False
                        break
                if match:
                    to_delete.append(uid)
            for uid in to_delete:
                del self._users[uid]

        else:
            # Generic DELETE for related tables — just ignore in mock
            pass

        return self

    def fetchone(self):
        return self._last_result[0] if self._last_result else None

    def fetchall(self):
        return self._last_result

    def commit(self):
        pass

    def close(self):
        pass

    def __iter__(self):
        return iter(self._last_result)


@pytest.fixture
def mock_db():
    return MockDB()


@pytest.fixture
def client(mock_db):
    from app.database import get_db_dep

    def _mock_db_dep():
        yield mock_db

    from fastapi import FastAPI
    from app.api.auth import router

    test_app = FastAPI()
    test_app.include_router(router)
    test_app.dependency_overrides[get_db_dep] = _mock_db_dep
    return TestClient(test_app)


@pytest.fixture
def seeded_user(mock_db):
    """Insert a test user directly into the mock database.

    Idempotent: reuses an existing user if the username is already taken.
    Uses a unique username that won't conflict with register tests.
    """
    for u in mock_db._users.values():
        if u.get("username") == "seeduser":
            return u
    mock_db.execute(
        "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
        ("seeduser", get_password_hash("test1234"), "user"),
    ).commit()
    return mock_db._users[1]


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

    def test_register_duplicate_username(self, client, mock_db, seeded_user):
        """Business logic rejects duplicate username with 400."""
        resp = client.post("/api/auth/register", json={
            "username": "seeduser",  # already created by seeded_user fixture
            "password": "test1234",
        })
        assert resp.status_code == 400, resp.text
        assert "用户名已存在" in resp.json()["detail"]

    def test_register_success(self, client, mock_db):
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

    def test_login_success(self, client, mock_db, seeded_user):
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

    def test_me_with_valid_token(self, client, mock_db, seeded_user):
        """Valid JWT returns the user profile."""
        from app.auth import create_access_token
        token = create_access_token({"user_id": 1, "role": "user"})

        resp = client.get("/api/auth/me", headers={
            "Authorization": f"Bearer {token}",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["username"] == "seeduser"
        assert data["role"] == "user"
        assert data["id"] is not None
