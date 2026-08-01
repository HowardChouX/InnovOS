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


class TestDevMode:
    @pytest.mark.asyncio
    async def test_dev_mode_no_credentials(self, monkeypatch):
        """无阿里云凭证时降级为开发模式：available=False，send_code 返回 dev-mock。"""
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("ALIBABA_CLOUD_ACCESS_KEY_SECRET", raising=False)

        from app.services.sms_client import SmsClient

        client = SmsClient()
        assert client.available is False

        result = await client.send_code("13800000000", "100001")
        assert result == {"success": True, "biz_id": "dev-mock", "message": "开发模式模拟发送"}
