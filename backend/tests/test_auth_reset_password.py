"""密码重置端点测试 — 短信 OTP 版（POST /send-code + POST /verify）。"""
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


class TestResetPassword:
    def test_send_code(self, auth_client, seed_user, monkeypatch):
        """已注册手机号下发验证码返回 202 + 有效期字段。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/password-reset/send-code",
            json={"phone": "13800000001"},
        )
        assert resp.status_code == 202, resp.text
        data = resp.json()
        assert data["expires_in"] == 300
        assert data["next_resend_in"] == 60

    def test_send_code_unknown_phone(self, auth_client, monkeypatch):
        """未注册手机号 → 404 PHONE_NOT_FOUND（预检，UX 优先）。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/password-reset/send-code",
            json={"phone": "13999999999"},
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["code"] == "PHONE_NOT_FOUND"

    def test_send_code_invalid_phone(self, auth_client):
        """非法手机号 → 422。"""
        resp = auth_client.post(
            "/api/auth/password-reset/send-code",
            json={"phone": "123"},
        )
        assert resp.status_code == 422

    def test_send_code_rate_limited(self, auth_client, seed_user, monkeypatch):
        """60s 内同一手机号第二次请求 → 429 SMS_RATE_LIMITED。"""
        _patch_sms_client(monkeypatch)
        first = auth_client.post(
            "/api/auth/password-reset/send-code",
            json={"phone": "13800000001"},
        )
        assert first.status_code == 202, first.text
        second = auth_client.post(
            "/api/auth/password-reset/send-code",
            json={"phone": "13800000001"},
        )
        assert second.status_code == 429, second.text
        assert second.json()["code"] == "SMS_RATE_LIMITED"

    def test_verify_success(self, auth_client, auth_session, seed_user, monkeypatch):
        """验证码正确 → 200 reset:true，数据库密码已更新（bcrypt 可验证新密码）。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/password-reset/verify",
            json={
                "phone": "13800000001",
                "code": "123456",
                "new_password": "newpass1234",
            },
        )
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"reset": True}

        from pwdlib import PasswordHash

        ph = PasswordHash.recommended()
        auth_session.refresh(seed_user)
        assert ph.verify("newpass1234", seed_user.hashed_password)
        assert not ph.verify("test1234", seed_user.hashed_password)

    def test_verify_invalid_code(self, auth_client, auth_session, seed_user, monkeypatch):
        """验证码错误 → 400 RESET_CODE_INVALID，密码不变。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/password-reset/verify",
            json={
                "phone": "13800000001",
                "code": "000000",
                "new_password": "newpass1234",
            },
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "RESET_CODE_INVALID"

        from pwdlib import PasswordHash

        ph = PasswordHash.recommended()
        auth_session.refresh(seed_user)
        assert ph.verify("test1234", seed_user.hashed_password)

    def test_verify_unknown_phone(self, auth_client, monkeypatch):
        """验证码正确但手机号未注册 → 404 USER_NOT_FOUND。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/password-reset/verify",
            json={
                "phone": "13999999999",
                "code": "123456",
                "new_password": "newpass1234",
            },
        )
        assert resp.status_code == 404, resp.text
        assert resp.json()["detail"]["code"] == "USER_NOT_FOUND"

    def test_verify_same_password(self, auth_client, seed_user, monkeypatch):
        """新密码与旧密码相同 → 400 SAME_PASSWORD，密码不变。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/password-reset/verify",
            json={
                "phone": "13800000001",
                "code": "123456",
                "new_password": "test1234",
            },
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["detail"]["code"] == "SAME_PASSWORD"

    def test_verify_short_password(self, auth_client, monkeypatch):
        """新密码 < 8 位 → 422（schema 校验）。"""
        _patch_sms_client(monkeypatch)
        resp = auth_client.post(
            "/api/auth/password-reset/verify",
            json={
                "phone": "13800000001",
                "code": "123456",
                "new_password": "short",
            },
        )
        assert resp.status_code == 422, resp.text

    def test_verify_rate_limited(self, auth_client, monkeypatch):
        """同一手机号 60s 内验证超过 10 次 → 429 SMS_RATE_LIMITED。"""
        _patch_sms_client(monkeypatch)
        # 用未注册手机号：验证码正确但用户不存在 → 404，密码不变，可反复请求
        payload = {
            "phone": "13700000001",
            "code": "123456",
            "new_password": "newpass1234",
        }
        for _ in range(10):
            resp = auth_client.post("/api/auth/password-reset/verify", json=payload)
            assert resp.status_code == 404, resp.text
        limited = auth_client.post("/api/auth/password-reset/verify", json=payload)
        assert limited.status_code == 429, limited.text
        assert limited.json()["code"] == "SMS_RATE_LIMITED"
