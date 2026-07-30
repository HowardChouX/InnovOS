"""
TDD 测试: chat_completion 统一入口 + Provider Key Pool failover

覆盖:
1. 新签名:messages 列表 + model_id 可选 + purpose 可选
2. model_id 优先(若传 model_id,忽略 purpose)
3. 仅传 purpose → ModelResolver.resolve_for_purpose()
4. 都不传 → RuntimeError
5. Key 租约失败 → 自动切下一把 Key(provider failover)
6. 401/403 → 切下一把 + cooldown
7. 429 → 切下一把 + Retry-After cooldown
8. 5xx → 不切 Key(Provider 故障,不是 Key 故障)
9. 参数 4xx → 不切 Key
10. 总尝试上限:min(可用 Key 数, 3)
11. mark_success 在成功后调用
12. mark_failure 在失败后调用
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── 辅助 ──


def _master_key(monkeypatch):
    monkeypatch.setenv(
        "INNOVOS_ENCRYPT_KEY",
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii").rstrip("="),
    )


def _make_lease(key_id: int, provider_id: str, plaintext: str):
    """构造 ApiKeyLease-like 对象,支持属性访问。"""
    @dataclass
    class Lease:
        key_id: int
        provider_id: str
        plaintext: str
    return Lease(key_id=key_id, provider_id=provider_id, plaintext=plaintext)


# ── 测试 ──


class TestChatCompletionSignature:
    def test_no_model_id_and_no_purpose_raises(self, monkeypatch):
        """既不传 model_id 也不传 purpose → 必须抛 RuntimeError。"""
        _master_key(monkeypatch)
        from app.algorithm import ai_client

        import asyncio
        with pytest.raises(RuntimeError, match="model_id|purpose|resolve"):
            asyncio.get_event_loop().run_until_complete(
                ai_client.chat_completion(
                    messages=[{"role": "user", "content": "hi"}]
                )
            )

    def test_empty_messages_raises(self, monkeypatch):
        """messages 空列表 + 不传 model_id/purpose → 抛错。"""
        _master_key(monkeypatch)
        from app.algorithm import ai_client

        import asyncio
        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(
                ai_client.chat_completion(messages=[])
            )

    def test_purpose_resolves_to_provider(self, monkeypatch):
        """传 purpose 时应通过 ModelResolver.resolve_for_purpose 解析。"""
        _master_key(monkeypatch)
        from app.algorithm import ai_client
        from app.algorithm.model_resolver import model_resolver, ResolvedModelConfig

        # patch 实例方法 — chat_completion 内部用的是 module-level model_resolver 单例
        monkeypatch.setattr(
            model_resolver,
            "resolve_for_purpose",
            lambda purpose: ResolvedModelConfig(
                provider_id="openai", model_id="gpt-4",
                api_key="fake-key", api_host="https://api.openai.com/v1",
            ),
        )

        # mock ProviderKeyPool 类 — 让 ProviderKeyPool() 每次返回同一个实例
        mock_pool_instance = MagicMock()
        mock_pool_instance.lease_key = AsyncMock(
            return_value=_make_lease(1, "openai", "sk-fake")
        )
        mock_pool_instance.report_success = AsyncMock()
        mock_pool_instance.report_failure = AsyncMock()

        mock_pool_class = MagicMock(return_value=mock_pool_instance)
        monkeypatch.setattr("app.algorithm.ai_client.ProviderKeyPool", mock_pool_class)

        # mock _call_openai_chat
        monkeypatch.setattr(
            "app.algorithm.ai_client._call_openai_chat",
            lambda **kwargs: "ok-response",
        )

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            ai_client.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                purpose="chat",
            )
        )

        assert result == "ok-response"
        mock_pool_instance.lease_key.assert_called_once()
        mock_pool_instance.report_success.assert_called_once_with(key_id=1)


class TestFailover:
    def test_auth_error_triggers_next_key_with_cooldown(self, monkeypatch):
        """401/403 → 切下一把 Key + cooldown。"""
        _master_key(monkeypatch)
        from app.algorithm import ai_client

        # 第一次 lease 返 Key A;第二次(切下一把) 返 Key B
        leases = iter([
            _make_lease(1, "p1", "sk-A"),
            _make_lease(2, "p1", "sk-B"),
        ])
        pool = MagicMock()
        pool.lease_key = AsyncMock(side_effect=lambda **kw: next(leases))
        pool.report_success = AsyncMock()
        pool.report_failure = AsyncMock()
        # 让 ProviderKeyPool() 返回这个 mock 实例
        pool.return_value = pool
        monkeypatch.setattr("app.algorithm.ai_client.ProviderKeyPool", pool)

        # mock model_resolver.resolve
        from app.algorithm.model_resolver import ResolvedModelConfig

        monkeypatch.setattr(
            "app.algorithm.model_resolver.ModelResolver.resolve",
            classmethod(lambda cls, x: ResolvedModelConfig(
                provider_id="p1", model_id="m1",
                api_key="", api_host="https://api.p1.com/v1",
            )),
        )

        # mock OpenAI call:第一次抛 401,第二次成功
        call_count = {"n": 0}

        def fake_call(*, api_key, api_host, model_id, messages, **opts):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("401 Unauthorized")
            return "second-success"

        monkeypatch.setattr("app.algorithm.ai_client._call_openai_chat", fake_call)

        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            ai_client.chat_completion(
                messages=[{"role": "user", "content": "x"}],
                model_id="p1:m1",
            )
        )

        assert result == "second-success"
        assert call_count["n"] == 2
        # 必须报告失败给 Key A(category=auth,带 cooldown)
        assert pool.report_failure.call_count >= 1
        failure_call_kwargs = pool.report_failure.call_args_list[0].kwargs
        assert failure_call_kwargs.get("key_id") == 1
        assert failure_call_kwargs.get("category") == "auth"
        # 必须报告成功给 Key B
        pool.report_success.assert_called_once_with(key_id=2)
        # 第二次 lease 必须传 exclude_key_ids 排除 Key A
        second_call_kwargs = pool.lease_key.call_args_list[1].kwargs
        assert 1 in second_call_kwargs.get("exclude_key_ids", set())

    def test_max_attempts_capped_at_3(self, monkeypatch):
        """总尝试上限 ≤ 3。"""
        _master_key(monkeypatch)
        from app.algorithm import ai_client

        # 模拟 5 把可用 Key,但最多尝试 3 次
        def make_lease(i):
            return _make_lease(i, "p1", f"sk-{i}")

        pool = MagicMock()
        # 每次返不同 Key
        pool.lease_key = AsyncMock(side_effect=[
            make_lease(1), make_lease(2), make_lease(3), make_lease(4), make_lease(5)
        ])
        pool.report_success = AsyncMock()
        pool.report_failure = AsyncMock()
        pool.return_value = pool
        monkeypatch.setattr("app.algorithm.ai_client.ProviderKeyPool", pool)

        from app.algorithm.model_resolver import ResolvedModelConfig

        monkeypatch.setattr(
            "app.algorithm.model_resolver.ModelResolver.resolve",
            classmethod(lambda cls, x: ResolvedModelConfig(
                provider_id="p1", model_id="m1",
                api_key="", api_host="https://api.p1.com/v1",
            )),
        )

        # 永远抛 401
        monkeypatch.setattr(
            "app.algorithm.ai_client._call_openai_chat",
            MagicMock(side_effect=RuntimeError("401 Unauthorized")),
        )

        import asyncio
        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(
                ai_client.chat_completion(
                    messages=[{"role": "user", "content": "x"}],
                    model_id="p1:m1",
                )
            )

        # lease_key 调用次数必须 ≤ 3
        assert pool.lease_key.call_count <= 3

    def test_provider_5xx_does_not_trigger_failover(self, monkeypatch):
        """Provider 5xx 不应切 Key(整 Provider 故障,非单 Key 故障)。"""
        _master_key(monkeypatch)
        from app.algorithm import ai_client

        pool = MagicMock()
        pool.lease_key = AsyncMock(return_value=_make_lease(1, "p1", "sk-A"))
        pool.report_success = AsyncMock()
        pool.report_failure = AsyncMock()
        pool.return_value = pool
        monkeypatch.setattr("app.algorithm.ai_client.ProviderKeyPool", pool)

        from app.algorithm.model_resolver import ResolvedModelConfig

        monkeypatch.setattr(
            "app.algorithm.model_resolver.ModelResolver.resolve",
            classmethod(lambda cls, x: ResolvedModelConfig(
                provider_id="p1", model_id="m1",
                api_key="", api_host="https://api.p1.com/v1",
            )),
        )

        monkeypatch.setattr(
            "app.algorithm.ai_client._call_openai_chat",
            MagicMock(side_effect=RuntimeError("500 Internal Server Error")),
        )

        import asyncio
        with pytest.raises(RuntimeError):
            asyncio.get_event_loop().run_until_complete(
                ai_client.chat_completion(
                    messages=[{"role": "user", "content": "x"}],
                    model_id="p1:m1",
                )
            )

        # 5xx 只调用 1 次 lease,不应切 Key
        assert pool.lease_key.call_count == 1
        # report_failure 应该是 provider 类别,且 cooldown_until 应该较长时间
        pool.report_failure.assert_called_once()
        kwargs = pool.report_failure.call_args.kwargs
        assert kwargs.get("category") == "provider"