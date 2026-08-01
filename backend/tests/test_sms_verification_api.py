"""短信验证码 API 测试。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.phone_verification import router
from app.exceptions.sms_verification import (
    SmsVerificationError,
    sms_verification_exception_handler,
)
from app.services.sms_client import SmsClient


class FakeSmsClient:
    """测试用假客户端：verify 恒真，send 恒成功。"""

    async def send_code(self, phone, template_code):
        return {"success": True, "biz_id": "test-biz", "message": "ok"}

    async def verify_code(self, phone, code):
        return True


def make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.add_exception_handler(SmsVerificationError, sms_verification_exception_handler)
    app.dependency_overrides = {}
    return app


def _patch_sms_client(monkeypatch):
    """按 test_sms_client.py 的模式：patch 类属性（而非模块级实例替换）。

    路由模块在导入时执行 `from app.services.sms_client import sms_client`，
    实例已绑定在 app.api.phone_verification.sms_client 上 —— 仅替换
    app.services.sms_client.sms_client 不会传导到路由。patch SmsClient
    的类方法可同时覆盖路由持有的单例实例。
    """
    monkeypatch.setattr(SmsClient, "send_code", FakeSmsClient.send_code)
    monkeypatch.setattr(SmsClient, "verify_code", FakeSmsClient.verify_code)


def test_send_code(monkeypatch):
    _patch_sms_client(monkeypatch)
    client = TestClient(make_app())
    resp = client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    assert resp.status_code == 202
    assert resp.json()["expires_in"] == 300


def test_verify_success(monkeypatch):
    _patch_sms_client(monkeypatch)
    client = TestClient(make_app())
    resp = client.post(
        "/api/auth/sms-verifications/verify",
        json={"phone": "13800000000", "code": "123456"},
    )
    assert resp.status_code == 200
    assert resp.json()["verified"] is True


def test_verify_invalid_phone():
    client = TestClient(make_app())
    resp = client.post(
        "/api/auth/sms-verifications/verify",
        json={"phone": "123", "code": "123456"},
    )
    assert resp.status_code == 422


def test_send_rate_limited(monkeypatch):
    _patch_sms_client(monkeypatch)
    client = TestClient(make_app())
    # 同一手机号 60s 内第二次请求 → 429
    client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    resp = client.post("/api/auth/sms-verifications/send", json={"phone": "13800000000"})
    assert resp.status_code == 429
