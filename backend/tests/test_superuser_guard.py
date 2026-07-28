"""超管权限守卫测试。"""
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from tests.conftest_auth import *  # noqa: F401, F403

from app.auth.instance import current_superuser
from app.db.session import get_session


@pytest.fixture
def guard_app(auth_session):
    """挂载一个仅超管可访问的测试端点。"""
    app = FastAPI()
    app.dependency_overrides[get_session] = lambda: auth_session

    @app.get("/admin-only")
    def admin_only(user=Depends(current_superuser)):
        return {"ok": True, "user_id": user.id}
    return app


@pytest.fixture
def guard_client(guard_app):
    return TestClient(guard_app)


def _login(auth_client, email, password):
    resp = auth_client.post(
        "/api/auth/jwt/login", data={"username": email, "password": password},
    )
    assert resp.status_code in (200, 204), resp.text
    cookies = list(resp.cookies.keys())
    return {cookies[0]: resp.cookies[cookies[0]]} if cookies else {}


class TestSuperuserGuard:
    def test_no_token_returns_401(self, guard_client):
        resp = guard_client.get("/admin-only")
        assert resp.status_code == 401

    def test_normal_user_forbidden(self, guard_client, seed_user, auth_client):
        """普通用户访问返回 403。"""
        cookies = _login(auth_client, "test@example.com", "test1234")
        guard_resp = guard_client.get("/admin-only", cookies=cookies)
        assert guard_resp.status_code == 403

    def test_superuser_allowed(self, guard_client, seed_admin, auth_client):
        """超管访问返回 200。"""
        cookies = _login(auth_client, "admin@example.com", "admin1234")
        guard_resp = guard_client.get("/admin-only", cookies=cookies)
        assert guard_resp.status_code == 200
        assert guard_resp.json()["ok"] is True