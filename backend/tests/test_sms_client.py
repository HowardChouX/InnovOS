"""SmsClient 单元测试 — mock 阿里云 SDK。"""
import pytest


@pytest.fixture
def sms_client(monkeypatch):
    """构造一个 client 存在的实例，mock 阿里云 SDK 调用。"""
    from app.services.sms_client import SmsClient

    client = SmsClient()

    class FakeModel:
        biz_id = "biz-123"

    class FakeBody:
        code = "OK"
        message = "成功"
        model = FakeModel()

    class FakeResp:
        body = FakeBody()

    class FakeClient:
        async def send_sms_verify_code_with_options_async(self, req, runtime):
            return FakeResp()

    client._client = FakeClient()
    return client


class TestSendCode:
    @pytest.mark.asyncio
    async def test_send_success(self, sms_client):
        result = await sms_client.send_code("13800000000", "100001")
        assert result["success"] is True
        assert result["biz_id"] == "biz-123"


class TestVerifyCode:
    @pytest.mark.asyncio
    async def test_verify_pass(self, sms_client, monkeypatch):
        class FakeModel:
            verify_result = "PASS"

        class FakeBody:
            code = "OK"
            model = FakeModel()

        class FakeResp:
            body = FakeBody()

        async def fake_check(self, req, runtime):
            return FakeResp()

        monkeypatch.setattr(
            sms_client._client.__class__,
            "check_sms_verify_code_with_options_async",
            fake_check,
            raising=False,
        )
        assert await sms_client.verify_code("13800000000", "123456") is True

    @pytest.mark.asyncio
    async def test_verify_unknown(self, sms_client, monkeypatch):
        class FakeModel:
            verify_result = "UNKNOWN"

        class FakeBody:
            code = "OK"
            model = FakeModel()

        class FakeResp:
            body = FakeBody()

        async def fake_check(self, req, runtime):
            return FakeResp()

        monkeypatch.setattr(
            sms_client._client.__class__,
            "check_sms_verify_code_with_options_async",
            fake_check,
            raising=False,
        )
        assert await sms_client.verify_code("13800000000", "654321") is False
