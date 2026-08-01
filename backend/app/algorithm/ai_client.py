"""AI 客户端 — 统一聊天调用入口(per-user failover via FailoverRouter).

Usage:
    await chat_completion(
        *, user_id, purpose, messages, model_override=None,
        temperature=0.3, max_tokens=None, response_format=None,
    ) -> dict  # {content, provider_id, model_id, input_tokens, output_tokens, ...}

    # Synchronous variant:
    chat_completion_sync(...)

    # FailoverAIWrapper — 与旧 AIBase 接口兼容的 duck-typed 包装器(供分析器使用):
    wrapper = FailoverAIWrapper(user_id=..., purpose=...)
    wrapper.call_ai(system_prompt, user_prompt, ...)

Both chat entry points delegate to `FailoverRouter` for the per-user queue walk +
circuit-breaker + usage log.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.algorithm.base import parse_ai_json, strip_think_tags
from app.services.failover_router import (
    FailoverRouter,
    NoProvidersConfiguredError,
)

logger = logging.getLogger(__name__)


async def chat_completion(
    *,
    user_id: int,
    purpose: str = "chat",
    messages: list[dict[str, str]],
    model_override: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    response_format: dict | None = None,
) -> dict[str, Any]:
    """Walk the user's failover queue, return the first success.

    Returns the raw response envelope: ``{"content": str, "provider_id": ...,
    "model_id": ..., "input_tokens": ..., "output_tokens": ...}`` — the caller
    is responsible for parsing ``content`` (e.g. via ``parse_ai_json``).

    Raises:
      NoProvidersConfiguredError: the user has no enabled providers.
      AllProvidersFailedError: every entry was tried and failed.
    """
    router = FailoverRouter()
    return await router.call(
        user_id=user_id,
        purpose=purpose,
        messages=messages,
        model_override=model_override,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )


def chat_completion_sync(
    *,
    user_id: int,
    purpose: str = "chat",
    messages: list[dict[str, str]],
    model_override: str | None = None,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    response_format: dict | None = None,
) -> dict[str, Any]:
    """Synchronous wrapper for non-async callers (analyzers)."""
    return asyncio.run(
        chat_completion(
            user_id=user_id,
            purpose=purpose,
            messages=messages,
            model_override=model_override,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
    )


# ── AIBase-compatible wrapper ──


class FailoverAIWrapper:
    """与旧 AIBase 接口兼容的包装器，内部使用 FailoverRouter。

    分析器通过 duck typing 接收任意实现了 call_ai() / call_ai_async() 的对象；
    本包装器把旧的 (system_prompt, user_prompt, ...) 调用形态适配到
    chat_completion_sync() 的新签名。

    当用户没有任何已启用的模型服务时，NoProvidersConfiguredError 会以面向
    用户的错误重新抛出（而不是静默返回 None），避免需求分析"成功"但结果为 0。
    """

    def __init__(self, user_id: int, purpose: str = "chat"):
        self.user_id = user_id
        self.purpose = purpose
        self.enabled = True

    def call_ai(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        logger_prefix: str = "",
        raw: bool = False,
        json_mode: bool = False,
    ) -> str | dict | None:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        try:
            result = chat_completion_sync(
                user_id=self.user_id,
                purpose=self.purpose,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if json_mode else None,
            )
        except NoProvidersConfiguredError as exc:
            raise RuntimeError("AI 模型未配置，请联系管理员开通 AI 功能") from exc
        except Exception as e:
            logger.error("[%s] FailoverRouter 调用失败: %s", logger_prefix or "AI", e)
            return None

        content = (result.get("content") or "").strip()
        content = strip_think_tags(content)

        if not content:
            logger.warning("[%s] 空响应", logger_prefix or "AI")
            return None

        if raw:
            return content

        parsed = parse_ai_json(content)
        if json_mode and not isinstance(parsed, dict):
            logger.warning(
                "[%s] 返回非 JSON 格式（%s）",
                logger_prefix or "AI",
                type(parsed).__name__,
            )
            return None

        return parsed

    async def call_ai_async(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        logger_prefix: str = "",
        raw: bool = False,
        json_mode: bool = False,
    ) -> str | dict | None:
        return await asyncio.to_thread(
            self.call_ai,
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            logger_prefix=logger_prefix,
            raw=raw,
            json_mode=json_mode,
        )
