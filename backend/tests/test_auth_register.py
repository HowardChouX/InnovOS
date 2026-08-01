"""注册 / 验证码登录端点测试。"""

from tests.conftest_auth import *  # noqa: F401, F403


class FakeSmsClient:
    """测试用假客户端：验证码固定 123456 可通过，send 恒成功。"""

    async def send_code(self, phone, template_code):
        return {"success": True, "biz_id": "test-biz", "message": "ok"}

    async def verify_code(self, phone, code):
        return code == "123456"


def _patch_sms_client(monkeypatch):
    """patch SmsClient 类属性（路由导入期已绑定单例实例，模块级替换不传导）。"""
    from app.services.sms_client import SmsClient

    monkeypatch.setattr(SmsClient, "send_code", FakeSmsClient.send_code)
    monkeypatch.setattr(SmsClient, "verify_code", FakeSmsClient.verify_code)


def _register_payload(email="new@example.com", phone="13800000000", password="test1234"):
    return {"email": email, "password": password, "phone": phone}


class TestRegister:
    def test_register_success(self, auth_client, auth_session, monkeypatch):
        """成功注册返回 201，用户写入 DB，phone 回显。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post("/api/auth/register", json=_register_payload())
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["phone"] == "13800000000"
        assert "id" in data
        assert data["is_active"] is True

    def test_register_duplicate_phone(self, auth_client, auth_session, monkeypatch):
        """同一手机号二次注册返回 400 REGISTER_PHONE_DUPLICATE。"""
        _patch_sms_client(monkeypatch)
        first = auth_client.post("/api/auth/register", json=_register_payload(email="first@example.com"))
        assert first.status_code == 201, first.text
        second = auth_client.post("/api/auth/register", json=_register_payload(email="second@example.com"))
        assert second.status_code == 400, second.text
        detail = second.json().get("detail", {})
        assert detail.get("code") == "REGISTER_PHONE_DUPLICATE"

    def test_register_duplicate_email(self, auth_client, seed_user, monkeypatch):
        """重复邮箱返回 400。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/register",
            json=_register_payload(email="test@example.com", phone="13800000005"),
        )
        assert resp.status_code == 400

    def test_register_short_password(self, auth_client, monkeypatch):
        """密码 < 8 位返回 400。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/register",
            json=_register_payload(phone="13800000006", password="123"),
        )
        assert resp.status_code == 400
        data = resp.json()
        # FastAPI Users register router 用 ErrorCode，详情在 reason
        detail = data.get("detail", {})
        if isinstance(detail, dict):
            assert "密码至少 8 位" in detail.get("reason", "")

    def test_register_phone_required(self, auth_client):
        """phone 必填（主登录标识）：缺失返回 422。"""
        resp = auth_client.post(
            "/api/auth/register",
            json={"email": "nophone@example.com", "password": "test1234"},
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json().get("detail", [])
        assert any(isinstance(d, dict) and d.get("loc") == ["body", "phone"] for d in detail)

    def test_register_invalid_phone(self, auth_client):
        """非法手机号返回 422。"""
        resp = auth_client.post(
            "/api/auth/register",
            json=_register_payload(phone="23800000000"),
        )
        assert resp.status_code == 422, resp.text
        detail = resp.json().get("detail", [])
        assert any(isinstance(d, dict) and d.get("loc") == ["body", "phone"] for d in detail)

    def test_register_invalid_email(self, auth_client):
        """非法 email 返回 422。"""
        resp = auth_client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "test1234", "phone": "13800000009"},
        )
        assert resp.status_code == 422


class TestLoginWithCode:
    def test_login_code_success(self, auth_client, seed_user, monkeypatch):
        """验证码正确 → 200 + 签发 JWT Set-Cookie（token 可解码且 sub 对应用户）。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/login/code",
            json={"phone": "13800000001", "code": "123456"},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["phone"] == "13800000001"
        assert data["is_verified"] is True
        assert "token" in resp.cookies, resp.cookies
        cookie = resp.cookies.get("token")
        assert cookie

        # 与登录链路同一策略解码（InnovOSJWTStrategy / fastapi-users jwt）
        from fastapi_users.jwt import decode_jwt

        from app.core.config import settings
        from app.auth.strategy import TOKEN_AUDIENCE

        payload = decode_jwt(
            cookie, settings.SECRET_KEY, TOKEN_AUDIENCE, algorithms=["HS256"]
        )
        assert payload["sub"] == str(seed_user.id)
        assert payload["token_version"] == seed_user.token_version

    def test_login_code_invalid(self, auth_client, seed_user, monkeypatch):
        """验证码错误 → 400 LOGIN_CODE_INVALID。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/login/code",
            json={"phone": "13800000001", "code": "000000"},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "LOGIN_CODE_INVALID"

    def test_login_code_user_not_found(self, auth_client, monkeypatch):
        """手机号未注册 → 400 LOGIN_USER_NOT_FOUND。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/login/code",
            json={"phone": "13999999999", "code": "123456"},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "LOGIN_USER_NOT_FOUND"

    def test_login_code_disabled_user_rejected(self, auth_client, auth_session, monkeypatch):
        """管理员禁用用户（is_active=false, is_verified=true）验证码正确也拒绝登录，且不重新激活。"""
        _patch_sms_client(monkeypatch)
        from pwdlib import PasswordHash

        from app.db.models import User

        ph = PasswordHash.recommended()
        disabled = User(
            email="disabled@example.com",
            phone="13800000007",
            hashed_password=ph.hash("test1234"),
            is_active=False,
            is_superuser=False,
            is_verified=True,
            role="user",
            token_version=0,
        )
        auth_session.add(disabled)
        auth_session.commit()

        resp = auth_client.post(
            "/api/auth/login/code",
            json={"phone": "13800000007", "code": "123456"},
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"]["code"] == "LOGIN_USER_DISABLED"
        assert "token" not in resp.cookies

        # 数据库状态未被改写（不得自行重新激活）
        auth_session.refresh(disabled)
        assert disabled.is_active is False
        assert disabled.is_verified is True

    def test_login_code_auto_activate(self, auth_client, auth_session, monkeypatch):
        """注册用户（is_verified=false, is_active=true）验证码登录 → 自动激活 is_verified 并返回 true。"""
        _patch_sms_client(monkeypatch)
        reg = auth_client.post("/api/auth/register", json=_register_payload())
        assert reg.status_code == 201, reg.text
        assert reg.json()["is_verified"] is False

        resp = auth_client.post(
            "/api/auth/login/code",
            json={"phone": "13800000000", "code": "123456"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_verified"] is True
        assert resp.json()["is_active"] is True
        assert "token" in resp.cookies

        from app.db.models import User

        user = auth_session.query(User).filter(User.phone == "13800000000").one()
        assert user.is_verified is True
        assert user.is_active is True

    def test_login_code_invalid_payload(self, auth_client):
        """非法 phone / code → 422。"""
        resp = auth_client.post(
            "/api/auth/login/code",
            json={"phone": "123", "code": "abc"},
        )
        assert resp.status_code == 422
