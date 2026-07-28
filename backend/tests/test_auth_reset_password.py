"""密码重置端点测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestResetPassword:
    def test_forgot_password(self, auth_client, seed_user):
        """忘记密码返回 202。"""
        resp = auth_client.post(
            "/api/auth/forgot-password",
            json={"email": "test@example.com"},
        )
        assert resp.status_code in (202, 200), resp.text

    def test_forgot_password_nonexistent(self, auth_client):
        """不存在的邮箱也返回 2xx（防探测）。"""
        resp = auth_client.post(
            "/api/auth/forgot-password",
            json={"email": "nobody@example.com"},
        )
        assert resp.status_code in (202, 200)