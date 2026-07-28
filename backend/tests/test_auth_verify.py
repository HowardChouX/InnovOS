"""邮箱验证端点测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestVerify:
    def test_request_verify_token(self, auth_client, seed_user):
        """请求验证 token 返回 202。"""
        resp = auth_client.post(
            "/api/auth/request-verify-token",
            json={"email": "test@example.com"},
        )
        assert resp.status_code in (202, 200), resp.text

    def test_request_verify_nonexistent(self, auth_client):
        """不存在的邮箱也返回 2xx（防探测）。"""
        resp = auth_client.post(
            "/api/auth/request-verify-token",
            json={"email": "nobody@example.com"},
        )
        assert resp.status_code in (202, 200)