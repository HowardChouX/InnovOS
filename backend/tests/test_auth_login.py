"""登录端点测试。

FastAPI Users 登录用 OAuth2PasswordRequestForm：
- Content-Type: application/x-www-form-urlencoded
- 字段: username (填邮箱值), password
"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestLogin:
    def test_login_success(self, auth_client, seed_user):
        """正确邮箱密码登录返回 204 + 设置 cookie。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "test@example.com", "password": "test1234"},
        )
        assert resp.status_code in (200, 204), resp.text
        # cookie 应被设置（__Host- 或默认 fastapiusersauth）
        cookies = list(resp.cookies.keys())
        assert any("token" in c.lower() or "fastapi" in c.lower() for c in cookies), \
            f"Expected auth cookie, got {cookies}"

    def test_login_with_phone(self, auth_client, seed_user):
        """phone-first：用手机号 + 密码登录成功（核心修复：内置路由查 email 字段导致永远失败）。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "13800000001", "password": "test1234"},
        )
        assert resp.status_code in (200, 204), resp.text
        cookies = list(resp.cookies.keys())
        assert any("token" in c.lower() for c in cookies), f"Expected auth cookie, got {cookies}"

    def test_login_wrong_password(self, auth_client, seed_user):
        """错误密码返回 400 + 中文 reason。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "13800000001", "password": "wrong"},
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert detail["code"] == "LOGIN_BAD_CREDENTIALS"
        assert detail["reason"] == "手机号或密码错误"

    def test_login_nonexistent_user(self, auth_client):
        """不存在的用户返回 400。"""
        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "nobody@example.com", "password": "test1234"},
        )
        assert resp.status_code == 400

    def test_login_unverified_user(self, auth_client, auth_session):
        """未验证用户密码登录返回 400 + LOGIN_USER_NOT_VERIFIED（前端据此跳转验证页）。"""
        from pwdlib import PasswordHash
        from app.db.models import User
        ph = PasswordHash.recommended()
        unverified = User(
            email="unverified@example.com",
            phone="13800000008",
            hashed_password=ph.hash("test1234"),
            is_active=True,
            is_superuser=False,
            is_verified=False,
        )
        auth_session.add(unverified)
        auth_session.commit()

        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "13800000008", "password": "test1234"},
        )
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "LOGIN_USER_NOT_VERIFIED"

    def test_login_inactive_user(self, auth_client, auth_session):
        """禁用用户登录失败。"""
        from pwdlib import PasswordHash
        from app.db.models import User
        ph = PasswordHash.recommended()
        inactive = User(
            email="inactive@example.com",
            phone="13800000003",
            hashed_password=ph.hash("test1234"),
            is_active=False,
            is_superuser=False,
            is_verified=True,
        )
        auth_session.add(inactive)
        auth_session.commit()

        resp = auth_client.post(
            "/api/auth/jwt/login",
            data={"username": "inactive@example.com", "password": "test1234"},
        )
        assert resp.status_code == 400