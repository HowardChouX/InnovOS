"""密码重置端点测试 — 短信 OTP 版（POST /send-code + POST /verify）。

Task 8 后 password-reset 完全走短信 OTP 链路：
- send-code / verify 均为 SMS 版路由（见 app/api/password_reset.py）
- 原邮箱 OTP 的 purpose 隔离 / reset_session 一次性消费逻辑已随
  EmailVerificationService 一并删除，相关测试不再存在。
"""
from tests.conftest_auth import *  # noqa: F401, F403


class TestPasswordResetRoutes:
    """HTTP 路由集成测试 — 短信 OTP 版。"""

    @staticmethod
    def _patch_sms_client(monkeypatch):
        """按 test_sms_verification_api.py 的模式：patch SmsClient 类属性。"""
        from app.services.sms_client import SmsClient

        class _FakeSmsClient:
            async def send_code(self, phone, template_code):
                return {"success": True, "biz_id": "test-biz", "message": "ok"}

            async def verify_code(self, phone, code):
                return code == "123456"

        monkeypatch.setattr(SmsClient, "send_code", _FakeSmsClient.send_code)
        monkeypatch.setattr(SmsClient, "verify_code", _FakeSmsClient.verify_code)

    def test_send_code_route_exists(self, auth_client, seed_user, monkeypatch):
        """路由存在且接受 POST。已注册手机号返回 202。"""
        self._patch_sms_client(monkeypatch)
        r = auth_client.post(
            "/api/auth/password-reset/send-code",
            json={"phone": "13800000001"},
        )
        assert r.status_code == 202, r.text

    def test_verify_route_updates_password(
        self, auth_client, auth_session, seed_user, monkeypatch
    ):
        """验证码正确 → 200 reset:true，数据库密码已更新。"""
        self._patch_sms_client(monkeypatch)
        r = auth_client.post(
            "/api/auth/password-reset/verify",
            json={
                "phone": "13800000001",
                "code": "123456",
                "new_password": "newpass1234",
            },
        )
        assert r.status_code == 200, r.text
        assert r.json() == {"reset": True}

        from pwdlib import PasswordHash

        auth_session.refresh(seed_user)
        assert PasswordHash.recommended().verify("newpass1234", seed_user.hashed_password)

    def test_verify_short_password_rejected(self, auth_client):
        """短密码被 schema 校验拒绝 (422)。"""
        r = auth_client.post(
            "/api/auth/password-reset/verify",
            json={"phone": "13800000001", "code": "123456", "new_password": "short"},
        )
        assert r.status_code == 422, r.text
