"""Tests for ModelService.check_connection — integration with reachability_probe.

Covers:
- Default reachability mode (GET base_url, no token consumed)
- Real mode (POST chat completions, legacy behavior)
- Anthropic sub-path fallback
- not_found / no_model branches
"""
from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from app.algorithm.model_service import model_service


class _CaptureClient:
    """Fake httpx.AsyncClient that records requests and returns canned responses."""

    def __init__(self, response: httpx.Response):
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    async def get(self, url: str, headers: dict | None = None):
        self.calls.append(("GET", {"url": url, "headers": headers or {}}))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def post(self, url: str, headers=None, json=None):
        self.calls.append(("POST", {"url": url, "headers": headers or {}, "json": json}))
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def aclose(self):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


@pytest.fixture(autouse=True)
def _patch_db(monkeypatch):
    mock_conn = MagicMock()

    def mock_get_db():
        return mock_conn

    monkeypatch.setattr("app.algorithm.model_service.get_db", mock_get_db)
    monkeypatch.setattr(
        "app.algorithm.model_service.load_api_key_cipher", lambda: MagicMock()
    )
    monkeypatch.setattr(
        "app.services.api_key_service.get_db", mock_get_db, raising=False
    )


class _FakeProviderRow:
    """模拟 _row_to_dict 返回的 provider dict。"""

    @staticmethod
    def make(api_host: str, api_model: str = "default-model") -> dict:
        return {
            "providerId": "test-p",
            "name": "Test",
            "notes": "",
            "apiHost": api_host,
            "apiModel": api_model,
            "isEnabled": True,
            "createdAt": "",
            "updatedAt": "",
        }


class TestCheckConnectionReachability:
    @pytest.mark.asyncio
    async def test_default_mode_is_reachability(self, monkeypatch):
        """默认 mode='reachability' 不消耗 token,只发 GET base_url。"""
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.example.com"),
        )

        client = _CaptureClient(httpx.Response(200, content=b""))
        monkeypatch.setattr(
            "app.algorithm.model_service.httpx.AsyncClient",
            lambda timeout=None: client,
        )

        result = await model_service.check_connection("test-p")

        # 应只有一次 GET,没有 POST
        assert len(client.calls) == 1
        assert client.calls[0][0] == "GET"
        assert client.calls[0][1]["url"] == "https://api.example.com"

        assert result["status"] == "ok"
        assert result["health"] == "operational"
        assert result["latency_ms"] is not None
        assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_4xx_returns_ok_for_reachability(self, monkeypatch):
        """reachability 模式: 401/403/404 等都视为可达(网关活着)。"""
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.example.com"),
        )
        client = _CaptureClient(httpx.Response(401, content=b"Unauthorized"))
        monkeypatch.setattr(
            "app.algorithm.model_service.httpx.AsyncClient",
            lambda timeout=None: client,
        )

        result = await model_service.check_connection("test-p")
        assert result["status"] == "ok"
        assert result["status_code"] == 401
        # 健康应该是 operational(因为 latency 在阈值内)
        assert result["health"] in ("operational", "degraded")

    @pytest.mark.asyncio
    async def test_connect_error_returns_failed_with_category(self, monkeypatch):
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.example.com"),
        )
        client = _CaptureClient(httpx.ConnectError("connection refused"))
        monkeypatch.setattr(
            "app.algorithm.model_service.httpx.AsyncClient",
            lambda timeout=None: client,
        )

        result = await model_service.check_connection("test-p")
        assert result["status"] == "error"
        assert result["health"] == "failed"
        assert result["error_category"] == "connect"

    @pytest.mark.asyncio
    async def test_anthropic_subpath_attempted_first(self, monkeypatch):
        """DeepSeek /anthropic: 先试子路径,失败回退根域。"""
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.deepseek.com/anthropic"),
        )

        attempted: list[str] = []

        async def fake_probe(url, config=None, client=None):
            from app.algorithm.reachability_probe import ProbeResult
            attempted.append(url)
            if "anthropic" in url:
                return ProbeResult(
                    status="error",
                    health="failed",
                    success=False,
                    latency_ms=100,
                    http_status=None,
                    message="",
                    error_category="connect",
                    retry_count=0,
                    checked_url=url,
                )
            return ProbeResult(
                status="ok",
                health="operational",
                success=True,
                latency_ms=200,
                http_status=200,
                message="Reachable",
                error_category=None,
                retry_count=0,
                checked_url=url,
            )

        monkeypatch.setattr(
            "app.algorithm.model_service.probe_reachability", fake_probe
        )

        result = await model_service.check_connection("test-p")
        # 应先试 anthropic 子路径,失败后试根域
        assert attempted[0] == "https://api.deepseek.com/anthropic"
        assert "https://api.deepseek.com" in attempted
        # 最终应成功(根域)
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_not_found_returns_correct_status(self, monkeypatch):
        monkeypatch.setattr(model_service, "get", lambda pid: None)
        result = await model_service.check_connection("missing-p")
        assert result["status"] == "not_found"
        assert result["health"] == "failed"

    @pytest.mark.asyncio
    async def test_empty_api_host_returns_no_model(self, monkeypatch):
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make(api_host=""),
        )
        result = await model_service.check_connection("test-p")
        assert result["status"] == "no_model"
        assert result["health"] == "failed"


class TestCheckConnectionRealMode:
    @pytest.mark.asyncio
    async def test_real_mode_uses_post_chat_completions(self, monkeypatch):
        """mode='real' 走真实 chat completions (旧行为,深度诊断)。"""
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.example.com", "gpt-4"),
        )
        monkeypatch.setattr(
            model_service, "_lease_key_plaintext", lambda pid: "sk-test"
        )

        client = _CaptureClient(httpx.Response(200, content=b'{"choices":[]}'))
        monkeypatch.setattr(
            "app.algorithm.model_service.httpx.AsyncClient",
            lambda timeout=None: client,
        )

        result = await model_service.check_connection("test-p", mode="real")

        # 应只有一次 POST 到 chat completions
        assert len(client.calls) == 1
        assert client.calls[0][0] == "POST"
        assert client.calls[0][1]["url"] == "https://api.example.com/v1/chat/completions"
        body = client.calls[0][1]["json"]
        assert body["model"] == "gpt-4"
        assert body["max_tokens"] == 1

        assert result["status"] == "ok"
        assert result["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_real_mode_5xx_returns_error(self, monkeypatch):
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.example.com"),
        )
        monkeypatch.setattr(
            model_service, "_lease_key_plaintext", lambda pid: "sk"
        )
        client = _CaptureClient(httpx.Response(500, content=b"oops"))
        monkeypatch.setattr(
            "app.algorithm.model_service.httpx.AsyncClient",
            lambda timeout=None: client,
        )

        result = await model_service.check_connection("test-p", mode="real")
        assert result["status"] == "error"
        assert result["status_code"] == 500
        assert result["model"] == "default-model"

    @pytest.mark.asyncio
    async def test_real_mode_no_key_returns_no_key(self, monkeypatch):
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.example.com"),
        )
        monkeypatch.setattr(model_service, "_lease_key_plaintext", lambda pid: None)
        result = await model_service.check_connection("test-p", mode="real")
        assert result["status"] == "no_key"


class TestCheckConnectionUserAgent:
    @pytest.mark.asyncio
    async def test_user_agent_passed_through(self, monkeypatch):
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: _FakeProviderRow.make("https://api.example.com"),
        )

        async def fake_probe(url, config=None, client=None):
            from app.algorithm.reachability_probe import ProbeResult
            assert config.user_agent == "InnovOS-Admin/1.0"
            return ProbeResult(
                status="ok",
                health="operational",
                success=True,
                latency_ms=50,
                http_status=200,
                message="",
                error_category=None,
                retry_count=0,
                checked_url=url,
            )

        monkeypatch.setattr(
            "app.algorithm.model_service.probe_reachability", fake_probe
        )

        result = await model_service.check_connection(
            "test-p", user_agent="InnovOS-Admin/1.0"
        )
        assert result["status"] == "ok"
