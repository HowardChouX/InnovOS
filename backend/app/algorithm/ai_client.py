"""
AI 客户端 — 统一聊天调用入口(messages 风格 + Provider Key Pool failover)。

合并了旧的 _chat_with_model + _chat_with_key_manager 双路径:
- model_id 优先 → 解析 ResolvedModel
- purpose → ModelResolver.resolve_for_purpose()
- 二者皆无 → RuntimeError

Failover:
- ProviderKeyPool.lease_key 选一把 Key(公平轮询,DB FOR UPDATE SKIP LOCKED)
- 调用 OpenAI 兼容协议(_call_openai_chat)
- 失败分类:
    auth(401/403) → 长 cooldown,切下一把
    rate_limit(429) → 短 cooldown,切下一把
    provider(5xx)  → 长 cooldown,**不切** Key(整 Provider 故障)
    4xx(参数)      → 不切 Key
    timeout/network → 切下一把
- 总尝试上限:min(可用 Key 数, 3)
- 解密失败 → 禁用 Key + 报告 failure,继续切下一把
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.core.key_crypto import ApiKeyDecryptionError

logger = logging.getLogger(__name__)


# ── 错误分类 ──


@dataclass
class CallOutcome:
    """单次调用的分类结果。"""

    should_failover: bool
    category: str  # "auth" / "rate_limit" / "provider" / "client" / "timeout" / "unknown"
    cooldown_seconds: int


def classify_error(exc: Exception) -> CallOutcome:
    """根据异常信息分类,决定是否切 Key + cooldown 时长。"""
    msg = str(exc).lower()

    # 5xx(Provider 故障)— 不切 Key,长 cooldown
    if re.search(r"\b5\d{2}\b", msg) or "internal server error" in msg or "bad gateway" in msg:
        return CallOutcome(should_failover=False, category="provider", cooldown_seconds=900)

    # 401/403(鉴权)— 切 Key,15 分钟 cooldown
    if re.search(r"\b401\b", msg) or re.search(r"\b403\b", msg) or "unauthorized" in msg or "forbidden" in msg:
        return CallOutcome(should_failover=True, category="auth", cooldown_seconds=900)

    # 429(限流)— 切 Key,默认 60s cooldown
    if (
        re.search(r"\b429\b", msg)
        or re.search(r"rate\s*limit", msg, re.IGNORECASE)
        or re.search(r"too\s*many", msg, re.IGNORECASE)
    ):
        return CallOutcome(should_failover=True, category="rate_limit", cooldown_seconds=60)

    # 4xx(参数错误)— 不切 Key
    if re.search(r"\b4\d{2}\b", msg):
        return CallOutcome(should_failover=False, category="client", cooldown_seconds=0)

    # 超时 / 网络 — 切 Key
    if "timeout" in msg or "timed out" in msg or "connection" in msg:
        return CallOutcome(should_failover=True, category="timeout", cooldown_seconds=30)

    # 解密失败 — 切 Key(已由 lease_key 内部禁用)
    if isinstance(exc, ApiKeyDecryptionError):
        return CallOutcome(should_failover=True, category="auth", cooldown_seconds=1800)

    return CallOutcome(should_failover=False, category="unknown", cooldown_seconds=0)


# ── Provider Key Pool(轻量包装 ApiKeyService) ──


class ProviderKeyPool:
    """runtime 用的 Key 池门面。

    内部委托 ApiKeyService.lease_key / mark_success / mark_failure。
    对 chat_completion 屏蔽底层实现细节。

    所有方法 async 以支持在 FastAPI 事件循环中调用,同时便于测试用
    AsyncMock 替换。
    """

    def __init__(self, api_key_service: Any = None) -> None:
        self._svc = api_key_service

    def _get_service(self):
        if self._svc is None:
            from app.database import get_db
            from app.core.key_crypto import load_api_key_cipher
            from app.services.api_key_service import ApiKeyService

            self._svc = ApiKeyService(db=get_db(), cipher=load_api_key_cipher())
        return self._svc

    async def lease_key(
        self,
        *,
        provider_id: str,
        exclude_key_ids: set[int] | None = None,
    ):
        return self._get_service().lease_key(
            provider_id=provider_id, exclude_key_ids=exclude_key_ids
        )

    async def report_success(self, *, key_id: int) -> None:
        self._get_service().mark_success(key_id=key_id)

    async def report_failure(
        self,
        *,
        key_id: int,
        category: str,
        cooldown_until: datetime | None = None,
    ) -> None:
        self._get_service().mark_failure(
            key_id=key_id, category=category, cooldown_until=cooldown_until
        )


# ── OpenAI 协议调用(唯一封装) ──


def _call_openai_chat(
    *,
    api_key: str,
    api_host: str,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float = 0.3,
    response_format: type = str,
    timeout: float = 30.0,
) -> Any:
    """同步调用 OpenAI-compatible /chat/completions。

    返回 content 字符串;若 response_format=dict 则返回已解析 dict。
    通过 AIClientRegistry 委派 OpenAICompatibleAdapter(唯一 OpenAI 构造点)。
    """
    from app.algorithm.client_registry import AIClientRegistry

    adapter = AIClientRegistry.get("openai")
    rf: dict | None = {"type": "json_object"} if response_format is dict else None
    content = adapter.chat(
        api_key=api_key,
        api_host=api_host,
        model_id=model_id,
        messages=messages,
        temperature=temperature,
        response_format=rf,
        timeout=timeout,
    )
    if response_format is dict:
        return json.loads(content)
    return content


# ── 统一入口 ──


MAX_ATTEMPTS = 3


def _resolve_endpoint(model_id: str | None, purpose: str | None):
    """model_id 或 purpose 二选一,返回 ResolvedModelConfig 或 None。

    两者都未传 → 返回 None(由调用方报错)。
    """
    from app.algorithm.model_resolver import model_resolver

    if model_id:
        return model_resolver.resolve(model_id)
    if purpose:
        return model_resolver.resolve_for_purpose(purpose)
    return None


def _messages_to_legacy(system_prompt: str, user_prompt: str) -> list[dict[str, str]]:
    """(system_prompt + user_prompt) → messages 列表。向后兼容旧调用方式。"""
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    if user_prompt:
        msgs.append({"role": "user", "content": user_prompt})
    return msgs


async def chat_completion(
    messages: list[dict[str, str]] | None = None,
    *,
    model_id: str | None = None,
    purpose: str | None = None,
    temperature: float = 0.3,
    response_format: type = str,
    timeout: float = 30.0,
    # 旧签名兼容 — 接收 system_prompt / user_prompt
    system_prompt: str = "",
    user_prompt: str = "",
    **_legacy: Any,
) -> Any:
    """统一聊天调用入口。

    用法:
        await chat_completion(
            messages=[{"role": "system", "content": "..."}, {"role": "user", "content": "..."}],
            model_id="openai:gpt-4",
        )

        # 或按用途(由管理员在 system_settings 中分配):
        await chat_completion(messages=msgs, purpose="chat")

    旧形式也支持(传入 system_prompt + user_prompt 字符串):
        await chat_completion(system_prompt=..., user_prompt=..., purpose="evaluation")

    行为:
    - 都不传 model_id 和 purpose → RuntimeError
    - Provider 没有 active Key → RuntimeError
    - 总尝试 ≤ min(可用 Key 数, 3)
    - 401/403/429/timeout → 切下一把 Key
    - 5xx → 不切 Key(Provider 故障)
    - 4xx → 不切 Key(参数错误)
    """
    # 兼容性:旧调用形式 system_prompt + user_prompt
    if messages is None and (system_prompt or user_prompt):
        messages = _messages_to_legacy(system_prompt, user_prompt)
    if not messages:
        raise RuntimeError(
            "chat_completion requires either messages=[...] or system_prompt/user_prompt"
        )

    resolved = _resolve_endpoint(model_id, purpose)
    if not resolved:
        raise RuntimeError(
            f"failed to resolve model: model_id={model_id!r}, purpose={purpose!r}; "
            "check system_settings and Provider configuration"
        )

    pool = ProviderKeyPool()
    exclude: set[int] = set()
    last_error: Exception | None = None

    for attempt in range(MAX_ATTEMPTS):
        lease = await pool.lease_key(
            provider_id=resolved.provider_id, exclude_key_ids=exclude
        )
        if not lease:
            # 没有可用 Key 了
            if last_error:
                raise RuntimeError(
                    f"all keys exhausted for provider '{resolved.provider_id}': {last_error}"
                ) from last_error
            raise RuntimeError(
                f"no active API key for provider '{resolved.provider_id}'"
            )

        try:
            result = _call_openai_chat(
                api_key=lease.plaintext,
                api_host=resolved.api_host,
                model_id=resolved.model_id,
                messages=messages,
                temperature=temperature,
                response_format=response_format,
                timeout=timeout,
            )
        except Exception as exc:
            last_error = exc
            outcome = classify_error(exc)
            cooldown_until = (
                datetime.now(timezone.utc) + timedelta(seconds=outcome.cooldown_seconds)
                if outcome.cooldown_seconds > 0
                else None
            )
            await pool.report_failure(
                key_id=lease.key_id,
                category=outcome.category,
                cooldown_until=cooldown_until,
            )
            logger.warning(
                "chat_completion: key=%s failed category=%s cooldown=%ss; attempt %d/%d",
                lease.key_id,
                outcome.category,
                outcome.cooldown_seconds,
                attempt + 1,
                MAX_ATTEMPTS,
            )
            if not outcome.should_failover:
                raise
            exclude.add(lease.key_id)
            if attempt < MAX_ATTEMPTS - 1:
                await asyncio.sleep(min(2 ** attempt, 4))
            continue

        # 成功
        await pool.report_success(key_id=lease.key_id)
        return result

    raise RuntimeError(
        f"all {MAX_ATTEMPTS} attempts failed for provider '{resolved.provider_id}': {last_error}"
    )