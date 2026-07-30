"""
TDD 测试: AIBase Runtime 依赖

覆盖:
1. AIBase 不再接受 api_key 形参(必须用 model_id + runtime 或 key_provider)
2. AIBase.call_ai_with_key_provider 通过 callback 取 Key
3. callback 返 None → AIBase.call_ai 返 None
4. 旧签名(api_key=...) 仍兼容,标记 deprecated 但不报错
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class TestAIBaseConstruction:
    def test_new_construction_with_runtime(self):
        """新构造:AIBase(key_provider=..., model_id='...') — 不接受 runtime 形参。"""
        from app.algorithm.base import AIBase

        ai = AIBase(key_provider=MagicMock(), api_host="https://api.example.com/v1", model_id="gpt-4")
        assert ai.model == "gpt-4"
        assert ai.key_provider is not None
        # 新形式:api_key 字段不持有
        assert ai.api_key is None

    def test_legacy_construction_with_api_key_still_works(self):
        """旧构造(测试或迁移期):AIBase(api_key=..., base_url=..., model=...) 仍可用,标 deprecated。"""
        from app.algorithm.base import AIBase

        # 不抛错,能创建实例
        ai = AIBase(api_key="sk-test", base_url="https://api.example.com/v1", model="m1")
        assert ai.enabled is True
        assert ai.api_key == "sk-test"


class TestCallAiWithKeyProvider:
    def test_call_ai_uses_key_provider_for_each_call(self):
        """call_ai_with_key_provider 每次都通过 provider 取 Key。"""
        from app.algorithm.base import AIBase
        from app.algorithm.clients import openai_compatible

        # mock key_provider
        provider = MagicMock(return_value="sk-dynamic")

        ai = AIBase(key_provider=provider, api_host="https://api.example.com/v1", model_id="m1")
        # mock adapter.chat 走真路径但跳过实际 OpenAI SDK
        with patch.object(
            openai_compatible.OpenAICompatibleAdapter, "chat", return_value="ok"
        ) as mock_chat:
            result = ai.call_ai_with_key_provider(
                key_provider=provider,
                api_host="https://api.example.com/v1",
                system_prompt="sys",
                user_prompt="user",
            )

        assert result == {"content": "ok"}
        assert provider.call_count == 1
        provider.assert_called_once()

    def test_call_ai_with_none_provider_returns_none(self):
        """key_provider 返 None → call_ai 返 None,不抛错。"""
        from app.algorithm.base import AIBase

        provider = MagicMock(return_value=None)
        ai = AIBase(key_provider=provider, api_host="https://api.example.com/v1", model_id="m1")
        result = ai.call_ai_with_key_provider(
            key_provider=provider,
            api_host="https://api.example.com/v1",
            system_prompt="sys",
            user_prompt="user",
        )
        assert result is None


from unittest.mock import patch