"""短信验证码 API 测试。

verify（register 场景）需要查库激活用户并自动登录，故复用 conftest_auth 的
auth_client（SQLite + get_session override + 限流重置），而非独立轻量 app。
"""

from tests.conftest_auth import *  # noqa: F401, F403

from app.services.sms_client import SmsClient


class FakeSmsClient:
    """测试用假客户端：verify 恒真，send 恒成功。"""

    async def send_code(self, phone, template_code):
        return {"success": True, "biz_id": "test-biz", "message": "ok"}

    async def verify_code(self, phone, code):
        return True


def _patch_sms_client(monkeypatch):
    """patch SmsClient 类属性（路由导入期已绑定单例实例，模块级替换不传导）。"""
    monkeypatch.setattr(SmsClient, "send_code", FakeSmsClient.send_code)
    monkeypatch.setattr(SmsClient, "verify_code", FakeSmsClient.verify_code)


def test_send_code(auth_client, monkeypatch):
    _patch_sms_client(monkeypatch)
    resp = auth_client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    assert resp.status_code == 202
    assert resp.json()["expires_in"] == 300


def test_verify_success_auto_login(auth_client, auth_session, monkeypatch):
    """注册验证通过 → 200 verified:true，激活用户、自动登录（Set-Cookie + 返回 user）。"""
    from pwdlib import PasswordHash

    from app.db.models import User

    _patch_sms_client(monkeypatch)
    auth_session.add(
        User(
            email=None,
            phone="13800000000",
            hashed_password=PasswordHash.recommended().hash("test1234"),
            is_active=True,
            is_superuser=False,
            is_verified=False,
        )
    )
    auth_session.commit()

    resp = auth_client.post(
        "/api/auth/sms-verifications/verify",
        json={"phone": "13800000000", "code": "123456"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["verified"] is True
    assert data["user"]["phone"] == "13800000000"
    assert data["user"]["is_verified"] is True
    # 自动登录：Set-Cookie 写入会话
    assert any("token" in c.lower() for c in resp.cookies.keys())

    # 数据库已激活
    auth_session.refresh(auth_session.query(User).filter_by(phone="13800000000").one())


def test_verify_unknown_phone(auth_client, monkeypatch):
    """注册验证时手机号未注册 → 404 PHONE_NOT_FOUND。"""
    _patch_sms_client(monkeypatch)
    resp = auth_client.post(
        "/api/auth/sms-verifications/verify",
        json={"phone": "13999999999", "code": "123456"},
    )
    assert resp.status_code == 404, resp.text
    assert resp.json()["code"] == "PHONE_NOT_FOUND"


def test_verify_invalid_phone(auth_client):
    resp = auth_client.post(
        "/api/auth/sms-verifications/verify",
        json={"phone": "123", "code": "123456"},
    )
    assert resp.status_code == 422


def test_send_rate_limited(auth_client, monkeypatch):
    _patch_sms_client(monkeypatch)
    # 同一手机号 60s 内第二次请求 → 429
    auth_client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    resp = auth_client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    assert resp.status_code == 429
