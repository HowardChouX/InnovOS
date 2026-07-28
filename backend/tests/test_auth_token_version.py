"""token_version 撤销机制测试。"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestTokenVersionRevocation:
    def test_token_works_before_revoke(self, auth_client, seed_user):
        """登录后 cookie 中的 token 可访问 /api/users/me。"""
        # 登录拿 cookie（auth_client 自动持久化 cookie）
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        assert resp.status_code in (200, 204), resp.text
        # 检查 cookie 被设置
        cookies = list(resp.cookies.keys())
        assert cookies, f"No cookies set, got {resp.cookies}"

        # 用 cookie 直接请求
        cookie_name = cookies[0]
        cookie_value = resp.cookies[cookie_name]
        me_resp = auth_client.get(
            "/api/users/me",
            cookies={cookie_name: cookie_value},
        )
        assert me_resp.status_code == 200, me_resp.text
        assert me_resp.json()["email"] == "test@example.com"

    def test_token_invalid_after_revoke(
        self, auth_client, seed_user, auth_session,
    ):
        """token_version 变更后旧 token 失效。"""
        # 登录
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        assert resp.status_code in (200, 204)
        cookies = list(resp.cookies.keys())
        assert cookies
        cookie_name = cookies[0]
        cookie_value = resp.cookies[cookie_name]

        # 撤销：token_version + 1
        seed_user.token_version += 1
        auth_session.commit()

        # 旧 token 应失效
        me_resp = auth_client.get(
            "/api/users/me",
            cookies={cookie_name: cookie_value},
        )
        assert me_resp.status_code in (401, 403)