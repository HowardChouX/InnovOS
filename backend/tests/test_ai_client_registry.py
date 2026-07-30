"""
TDD 测试: AIClientRegistry + openai_compatible adapter

覆盖:
1. Registry.get("openai") 返 adapter 实例
2. Registry.get("anthropic") 抛 NotImplementedError
3. OpenAICompatibleAdapter 不持有长期 api_key(只在 chat/embedding 调用时接收)
4. Adapter.chat 调 OpenAI SDK 并返 content
5. Adapter.embedding 调 OpenAI SDK 并返 vectors
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest


@dataclass
class _ChatResult:
    content: str


class TestRegistry:
    def test_get_openai_returns_adapter(self):
        from app.algorithm.client_registry import AIClientRegistry

        adapter = AIClientRegistry.get("openai")
        assert adapter is not None

    def test_get_unknown_protocol_raises(self):
        from app.algorithm.client_registry import AIClientRegistry

        with pytest.raises(NotImplementedError, match="anthropic|protocol"):
            AIClientRegistry.get("anthropic")

    def test_get_dashscope_raises_unless_implemented(self):
        from app.algorithm.client_registry import AIClientRegistry

        # 暂未实现 dashscope — 应当抛错
        with pytest.raises(NotImplementedError):
            AIClientRegistry.get("dashscope")


class TestOpenAICompatibleAdapter:
    def test_adapter_does_not_hold_long_term_api_key(self):
        """Adapter 实例不应缓存 api_key(避免泄漏 + 轮询失败)。"""
        from app.algorithm.clients.openai_compatible import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter()
        # 实例属性不应有 api_key
        assert not hasattr(adapter, "api_key") or adapter.__dict__.get("api_key") is None

    @patch("app.algorithm.clients.openai_compatible.OpenAI")
    def test_chat_calls_openai_and_returns_content(self, mock_openai_class):
        """adapter.chat(api_key=..., ...) → 调 OpenAI SDK,返 content。"""
        # mock OpenAI 客户端响应
        mock_choice = MagicMock()
        mock_choice.message.content = "hello world"
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_resp
        mock_openai_class.return_value = mock_client

        from app.algorithm.clients.openai_compatible import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter()
        result = adapter.chat(
            api_key="sk-test",
            api_host="https://api.example.com/v1",
            model_id="gpt-4",
            messages=[{"role": "user", "content": "hi"}],
            temperature=0.3,
        )
        assert result == "hello world"
        # 验证 OpenAI client 用正确的 key/host 构造
        call_kwargs = mock_openai_class.call_args.kwargs
        assert call_kwargs.get("api_key") == "sk-test"
        assert "example.com" in call_kwargs.get("base_url", "")

    @patch("app.algorithm.clients.openai_compatible.OpenAI")
    def test_embedding_calls_openai_and_returns_vectors(self, mock_openai_class):
        mock_item = MagicMock()
        mock_item.embedding = [0.1, 0.2, 0.3]
        mock_resp = MagicMock()
        mock_resp.data = [mock_item]
        mock_client = MagicMock()
        mock_client.embeddings.create.return_value = mock_resp
        mock_openai_class.return_value = mock_client

        from app.algorithm.clients.openai_compatible import OpenAICompatibleAdapter

        adapter = OpenAICompatibleAdapter()
        result = adapter.embedding(
            api_key="sk-test",
            api_host="https://api.example.com/v1",
            model_id="text-embedding-3-small",
            texts=["hello"],
        )
        assert result == [[0.1, 0.2, 0.3]]