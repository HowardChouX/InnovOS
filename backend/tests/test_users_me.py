"""GET/PATCH /api/users/me 测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


def _login_and_get_cookie(auth_client, email, password):
    """辅助：登录并返回 cookie dict。"""
    resp = auth_client.post(
        "/api/auth/jwt/login", data={"username": email, "password": password},
    )
    assert resp.status_code in (200, 204), resp.text
    cookies = list(resp.cookies.keys())
    assert cookies, f"No cookies set, got {resp.cookies}"
    return {cookies[0]: resp.cookies[cookies[0]]}


class TestUsersMe:
    def test_me_requires_auth(self, auth_client):
        """无 token 返回 401。"""
        resp = auth_client.get("/api/users/me")
        assert resp.status_code == 401

    def test_me_returns_user(self, auth_client, seed_user):
        """有效 token 返回用户信息。"""
        cookies = _login_and_get_cookie(
            auth_client, "test@example.com", "test1234",
        )
        me_resp = auth_client.get("/api/users/me", cookies=cookies)
        assert me_resp.status_code == 200
        data = me_resp.json()
        assert data["email"] == "test@example.com"

    def test_me_patch_username(self, auth_client, seed_user):
        """PATCH 更新 username。"""
        cookies = _login_and_get_cookie(
            auth_client, "test@example.com", "test1234",
        )
        patch_resp = auth_client.patch(
            "/api/users/me", cookies=cookies, json={"username": "newname"},
        )
        assert patch_resp.status_code == 200, patch_resp.text
        assert patch_resp.json().get("username") == "newname"