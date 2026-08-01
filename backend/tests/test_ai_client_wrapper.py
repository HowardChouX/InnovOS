"""
测试 ai_client.FailoverAIWrapper — 旧 AIBase 接口到新 chat_completion 的适配。

覆盖:
1. NoProvidersConfiguredError → 重新抛出用户可见错误（不再静默返回 None）
2. 返回信封 content 的 JSON 解析
3. temperature / max_tokens / response_format 透传到 chat_completion_sync
4. json_mode=True → response_format={"type": "json_object"}
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.algorithm.ai_client import FailoverAIWrapper
from app.services.failover_router import NoProvidersConfiguredError


class TestFailoverAIWrapper:
    def test_no_providers_re_raises_user_facing_error(self):
        """用户没有任何已启用的模型服务时，必须抛出用户可见错误而非返回 None。"""
        with patch(
            "app.algorithm.ai_client.chat_completion_sync",
            side_effect=NoProvidersConfiguredError("user 1 has no enabled model services"),
        ):
            wrapper = FailoverAIWrapper(user_id=1)
            with pytest.raises(RuntimeError, match="AI 模型未配置"):
                wrapper.call_ai("system", "user")

    def test_parses_json_content_from_envelope(self):
        """call_ai 应解析返回信封中的 content 字段为 dict。"""
        payload = {"demands": [{"id": "d1", "description": "需求1"}]}
        with patch(
            "app.algorithm.ai_client.chat_completion_sync",
            return_value={"content": json.dumps(payload, ensure_ascii=False)},
        ) as mock_call:
            wrapper = FailoverAIWrapper(user_id=1)
            result = wrapper.call_ai("system", "user")

        assert result == payload
        mock_call.assert_called_once()

    def test_passes_temperature_max_tokens_and_json_mode(self):
        """temperature/max_tokens/json_mode 必须透传到 chat_completion_sync。"""
        with patch(
            "app.algorithm.ai_client.chat_completion_sync",
            return_value={"content": json.dumps({"ok": True})},
        ) as mock_call:
            wrapper = FailoverAIWrapper(user_id=1, purpose="evaluation")
            wrapper.call_ai(
                "system", "user",
                temperature=0.7, max_tokens=512, raw=True, json_mode=True,
            )

        kwargs = mock_call.call_args[1]
        assert kwargs["user_id"] == 1
        assert kwargs["purpose"] == "evaluation"
        assert kwargs["temperature"] == 0.7
        assert kwargs["max_tokens"] == 512
        assert kwargs["response_format"] == {"type": "json_object"}

    def test_no_json_mode_means_no_response_format(self):
        """json_mode=False 时不应传 response_format。"""
        with patch(
            "app.algorithm.ai_client.chat_completion_sync",
            return_value={"content": "raw text"},
        ) as mock_call:
            wrapper = FailoverAIWrapper(user_id=1)
            wrapper.call_ai("system", "user", raw=True)

        kwargs = mock_call.call_args[1]
        assert kwargs["response_format"] is None

    @pytest.mark.asyncio
    async def test_call_ai_async_delegates(self):
        """call_ai_async 应委托给 call_ai（经 to_thread）。"""
        with patch.object(
            FailoverAIWrapper, "call_ai", return_value={"ok": True}
        ) as mock_sync:
            wrapper = FailoverAIWrapper(user_id=1)
            result = await wrapper.call_ai_async("sys", "user", json_mode=True)

        assert result == {"ok": True}
        mock_sync.assert_called_once()
