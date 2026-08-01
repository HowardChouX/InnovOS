"""Tests for the upgraded detect_models / fetch_remote_models in model_service.

The HTTP layer is mocked via httpx.MockTransport so we never touch the network.
DB calls are intercepted by the autouse ``auto_mock_db`` fixture in conftest.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from app.algorithm.model_service import (
    _normalize_models_response,
    fetch_remote_models,
    model_service,
)


@pytest.fixture(autouse=True)
def _patch_model_service_db(monkeypatch):
    """model_service 在模块顶层做了 ``from app.database import get_db``,
    conftest 只 patch 了 ``app.api.models`` 的 get_db,需要补 patch。"""
    mock_conn = MagicMock()

    def mock_get_db():
        return mock_conn

    monkeypatch.setattr("app.algorithm.model_service.get_db", mock_get_db)
    monkeypatch.setattr(
        "app.algorithm.model_service.load_api_key_cipher",
        lambda: MagicMock(),
    )
    # ApiKeyService 内部也会调 get_db,统一拦截
    monkeypatch.setattr(
        "app.services.api_key_service.get_db", mock_get_db, raising=False
    )


# ═══════════════════════════════════════════════════════════════════════════
#  _normalize_models_response
# ═══════════════════════════════════════════════════════════════════════════


class TestNormalizeModelsResponse:
    def test_standard_response(self):
        payload = {
            "object": "list",
            "data": [
                {"id": "gpt-4", "object": "model", "owned_by": "openai"},
                {"id": "claude-3-sonnet", "object": "model", "owned_by": "anthropic"},
            ],
        }
        out = _normalize_models_response(payload)
        assert out == [
            {"id": "claude-3-sonnet", "name": "claude-3-sonnet", "ownedBy": "anthropic"},
            {"id": "gpt-4", "name": "gpt-4", "ownedBy": "openai"},
        ]

    def test_response_without_owned_by(self):
        payload = {"data": [{"id": "my-model", "object": "model"}]}
        out = _normalize_models_response(payload)
        assert out == [{"id": "my-model", "name": "my-model"}]

    def test_empty_data(self):
        assert _normalize_models_response({"data": []}) == []

    def test_missing_data(self):
        assert _normalize_models_response({"object": "list"}) == []

    def test_invalid_payload(self):
        assert _normalize_models_response(None) == []
        assert _normalize_models_response("not a dict") == []
        assert _normalize_models_response({"data": "oops"}) == []

    def test_dedupes_by_id(self):
        payload = {"data": [{"id": "a"}, {"id": "a"}, {"id": "b"}]}
        out = _normalize_models_response(payload)
        ids = [m["id"] for m in out]
        assert ids == ["a", "b"]

    def test_skips_empty_id(self):
        payload = {"data": [{"id": ""}, {"id": "valid"}, {"object": "no-id"}]}
        out = _normalize_models_response(payload)
        assert [m["id"] for m in out] == ["valid"]

    def test_sorted_by_id(self):
        payload = {"data": [{"id": "z"}, {"id": "a"}, {"id": "m"}]}
        out = _normalize_models_response(payload)
        assert [m["id"] for m in out] == ["a", "m", "z"]


# ═══════════════════════════════════════════════════════════════════════════
#  fetch_remote_models
# ═══════════════════════════════════════════════════════════════════════════


def _make_mock_transport(responses: list[httpx.Response | Exception]) -> httpx.MockTransport:
    """按顺序消费 responses 列表 — 适合多候选 URL 重试场景。"""
    iter_responses = iter(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        try:
            item = next(iter_responses)
        except StopIteration as exc:
            raise AssertionError("MockTransport called more times than expected") from exc
        if isinstance(item, Exception):
            raise item
        return item

    return httpx.MockTransport(handler)


class TestFetchRemoteModels:
    @pytest.mark.asyncio
    async def test_single_candidate_success(self):
        body = json.dumps({"data": [{"id": "gpt-4"}]}).encode()
        transport = _make_mock_transport([
            httpx.Response(200, content=body, headers={"content-type": "application/json"})
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            out = await fetch_remote_models(
                ["https://example.com/v1/models"],
                api_key="sk-test",
                client=client,
            )
        assert [m["id"] for m in out] == ["gpt-4"]

    @pytest.mark.asyncio
    async def test_404_falls_through_to_next(self):
        """404 表示端点不存在,继续尝试下一个候选。"""
        body_ok = json.dumps({"data": [{"id": "found-model"}]}).encode()
        transport = _make_mock_transport([
            httpx.Response(404, content=b"Not Found"),
            httpx.Response(200, content=body_ok, headers={"content-type": "application/json"}),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            out = await fetch_remote_models(
                ["https://a.example/v1/models", "https://b.example/v1/models"],
                api_key="sk-test",
                client=client,
            )
        assert [m["id"] for m in out] == ["found-model"]

    @pytest.mark.asyncio
    async def test_405_falls_through(self):
        body_ok = json.dumps({"data": [{"id": "ok"}]}).encode()
        transport = _make_mock_transport([
            httpx.Response(405, content=b""),
            httpx.Response(200, content=body_ok, headers={"content-type": "application/json"}),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            out = await fetch_remote_models(
                ["https://a.example/v1/models", "https://b.example/v1/models"],
                api_key="sk",
                client=client,
            )
        assert [m["id"] for m in out] == ["ok"]

    @pytest.mark.asyncio
    async def test_401_fails_immediately(self):
        """401 不是端点不存在,立即抛错不重试。"""
        transport = _make_mock_transport([
            httpx.Response(401, content=b"Unauthorized"),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="HTTP 401"):
                await fetch_remote_models(
                    ["https://a.example/v1/models"],
                    api_key="bad-key",
                    client=client,
                )

    @pytest.mark.asyncio
    async def test_all_404_raises_with_last_error(self):
        transport = _make_mock_transport([
            httpx.Response(404, content=b"first 404"),
            httpx.Response(404, content=b"second 404"),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="All candidates failed"):
                await fetch_remote_models(
                    ["https://a.example/v1/models", "https://b.example/v1/models"],
                    api_key="sk",
                    client=client,
                )

    @pytest.mark.asyncio
    async def test_invalid_json_raises(self):
        transport = _make_mock_transport([
            httpx.Response(200, content=b"not json", headers={"content-type": "application/json"}),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="Failed to parse response"):
                await fetch_remote_models(
                    ["https://example.com/v1/models"],
                    api_key="sk",
                    client=client,
                )

    @pytest.mark.asyncio
    async def test_network_error_raises_immediately(self):
        """网络层错误不应继续尝试(继续只会浪费超时)。"""
        transport = _make_mock_transport([
            httpx.ConnectError("connection refused"),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="Request failed"):
                await fetch_remote_models(
                    ["https://example.com/v1/models"],
                    api_key="sk",
                    client=client,
                )

    @pytest.mark.asyncio
    async def test_user_agent_header_sent(self):
        seen_headers: dict[str, str] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen_headers.update({k.lower(): v for k, v in request.headers.items()})
            body = json.dumps({"data": [{"id": "x"}]}).encode()
            return httpx.Response(200, content=body, headers={"content-type": "application/json"})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            await fetch_remote_models(
                ["https://example.com/v1/models"],
                api_key="sk",
                user_agent="My-Client/1.0",
                client=client,
            )
        assert seen_headers.get("user-agent") == "My-Client/1.0"
        assert seen_headers.get("authorization") == "Bearer sk"

    @pytest.mark.asyncio
    async def test_empty_candidates_raises_value_error(self):
        with pytest.raises(ValueError, match="empty"):
            await fetch_remote_models([], api_key="sk")

    @pytest.mark.asyncio
    async def test_large_error_body_truncated(self):
        big_body = "x" * 5000
        transport = _make_mock_transport([
            httpx.Response(500, content=big_body.encode()),
        ])
        async with httpx.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError) as excinfo:
                await fetch_remote_models(
                    ["https://example.com/v1/models"],
                    api_key="sk",
                    client=client,
                )
        # 错误信息不应包含完整 5000 x,应被截断
        assert len(str(excinfo.value)) < 1000


# ═══════════════════════════════════════════════════════════════════════════
#  model_service.detect_models (integration)
# ═══════════════════════════════════════════════════════════════════════════


class TestDetectModelsIntegration:
    """detect_models 通过多候选 URL 工作的集成测试。

    DB 通过 conftest 的 auto_mock_db 拦截,需要的话手动 patch。
    """

    @pytest.mark.asyncio
    async def test_pre_create_path_with_known_provider(self, monkeypatch):
        """OpenAI 风格 baseURL -> 直接拿到 /v1/models 列表。"""
        body = json.dumps(
            {
                "object": "list",
                "data": [
                    {"id": "gpt-4", "owned_by": "openai"},
                    {"id": "gpt-3.5-turbo", "owned_by": "openai"},
                ],
            }
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/models"
            return httpx.Response(
                200, content=body, headers={"content-type": "application/json"}
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            # Patch fetch_remote_models to use our mock client
            monkeypatch.setattr(
                "app.algorithm.model_service.httpx.AsyncClient",
                lambda timeout=None: client,
            )
            result = await model_service.detect_models(
                provider_id="__detect__",
                api_host="https://api.openai.com",
                api_key="sk-test",
            )

        ids = [m["id"] for m in result["models"]]
        assert ids == ["gpt-3.5-turbo", "gpt-4"]
        # 应该返回候选 URL 给前端做调试提示
        assert result["candidates"] == ["https://api.openai.com/v1/models"]

    @pytest.mark.asyncio
    async def test_pre_create_anthropic_compat_fallback(self, monkeypatch):
        """DeepSeek-style baseURL 带 /anthropic 子路径 -> 先试子路径 404,
        再试根域的 /v1/models,最终成功。"""
        body = json.dumps(
            {"data": [{"id": "deepseek-chat", "owned_by": "deepseek"}]}
        ).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            # 子路径下的 /v1/models 不存在(DeepSeek 官方没把 OpenAI 端点
            # 挂在 /anthropic 子路径下),直接 404。
            if request.url.path == "/anthropic/v1/models":
                return httpx.Response(404, content=b"Not Found")
            # 根域的 /v1/models 是真实端点
            assert request.url.path == "/v1/models"
            return httpx.Response(
                200, content=body, headers={"content-type": "application/json"}
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            monkeypatch.setattr(
                "app.algorithm.model_service.httpx.AsyncClient",
                lambda timeout=None: client,
            )
            result = await model_service.detect_models(
                provider_id="__detect__",
                api_host="https://api.deepseek.com/anthropic",
                api_key="sk-test",
            )

        assert [m["id"] for m in result["models"]] == ["deepseek-chat"]

    @pytest.mark.asyncio
    async def test_pre_create_zhipu_coding_plan_v4(self, monkeypatch):
        """智谱 Coding Plan baseURL 以 /v4 结尾 -> 正确路径是 /v4/models 不是 /v4/v1/models。"""
        body = json.dumps({"data": [{"id": "glm-coding"}]}).encode()

        called_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            called_urls.append(str(request.url))
            if "/v4/v1/models" in str(request.url):
                # 错误的次候选路径 -> 模拟 404
                return httpx.Response(404, content=b"Not Found")
            assert "/v4/models" in str(request.url)
            return httpx.Response(
                200, content=body, headers={"content-type": "application/json"}
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            monkeypatch.setattr(
                "app.algorithm.model_service.httpx.AsyncClient",
                lambda timeout=None: client,
            )
            result = await model_service.detect_models(
                provider_id="__detect__",
                api_host="https://open.bigmodel.cn/api/coding/paas/v4",
                api_key="sk-test",
            )

        assert [m["id"] for m in result["models"]] == ["glm-coding"]
        # 第一个被调用的 URL 应是正确路径 /v4/models
        assert called_urls[0].endswith("/api/coding/paas/v4/models")

    @pytest.mark.asyncio
    async def test_provider_id_path_uses_db_lookup(self, monkeypatch):
        """provider_id 非 __detect__ 时,从 DB 拿 apiHost + apiKey。"""
        body = json.dumps({"data": [{"id": "bge-large"}]}).encode()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, content=body, headers={"content-type": "application/json"}
            )

        # Patch self.get + self._lease_key_plaintext
        monkeypatch.setattr(
            model_service, "get",
            lambda pid: {"apiHost": "https://api.siliconflow.cn", "isEnabled": True},
        )
        monkeypatch.setattr(
            model_service, "_lease_key_plaintext", lambda pid: "sk-from-db"
        )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            monkeypatch.setattr(
                "app.algorithm.model_service.httpx.AsyncClient",
                lambda timeout=None: client,
            )
            result = await model_service.detect_models(provider_id="silicon")

        assert [m["id"] for m in result["models"]] == ["bge-large"]

    @pytest.mark.asyncio
    async def test_provider_id_not_found_raises(self, monkeypatch):
        """provider_id 非 __detect__ 且 DB 中不存在 -> LookupError。"""
        # 显式让 self.get 返回 None 模拟「DB 中不存在该 provider」,
        # 此时走 LookupError 分支;否则 mock 环境下 MagicMock 会让
        # current 不为 None 而走到 api_host/api_key 校验路径。
        monkeypatch.setattr(model_service, "get", lambda pid: None)
        with pytest.raises(LookupError):
            await model_service.detect_models(provider_id="__nonexistent__")

    @pytest.mark.asyncio
    async def test_invalid_api_host_raises(self):
        """空 baseURL -> ValueError(候选构造失败)。"""
        with pytest.raises(ValueError, match="api_host and api_key are required"):
            await model_service.detect_models(
                provider_id="__detect__", api_host="", api_key="sk"
            )

    @pytest.mark.asyncio
    async def test_models_url_override(self, monkeypatch):
        """models_url 精确覆写时,不走候选生成逻辑,只试一个 URL。"""
        body = json.dumps({"data": [{"id": "custom-model"}]}).encode()

        called_urls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            called_urls.append(str(request.url))
            return httpx.Response(
                200, content=body, headers={"content-type": "application/json"}
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            monkeypatch.setattr(
                "app.algorithm.model_service.httpx.AsyncClient",
                lambda timeout=None: client,
            )
            result = await model_service.detect_models(
                provider_id="__detect__",
                api_host="https://api.example.com",
                api_key="sk",
                models_url="https://api.example.com/custom/models",
            )

        assert called_urls == ["https://api.example.com/custom/models"]
        assert [m["id"] for m in result["models"]] == ["custom-model"]
