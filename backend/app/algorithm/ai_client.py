"""AI 客户端 — 统一聊天调用入口(per-user failover via FailoverRouter).

Usage:
    await chat_completion(
        *, user_id, purpose, messages, model_override=None,
    ) -> dict  # {content, provider_id, model_id, input_tokens, output_tokens, ...}

    # Synchronous variant:
    chat_completion_sync(...)

Both delegate to `FailoverRouter` for the per-user queue walk +
circuit-breaker + usage log.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from app.services.failover_router import (
    AllProvidersFailedError,
    FailoverError,
    FailoverRouter,
    NoProvidersConfiguredError,
)

logger = logging.getLogger(__name__)


async def chat_completion(
    *,
    user_id: int,
    purpose: str = "chat",
    messages: list[dict[str, str]],
    model_override: Optional[str] = None,
) -> dict[str, Any]:
    """Walk the user's failover queue, return the first success.

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
    )


def chat_completion_sync(
    *,
    user_id: int,
    purpose: str = "chat",
    messages: list[dict[str, str]],
    model_override: Optional[str] = None,
) -> dict[str, Any]:
    """Synchronous wrapper for non-async callers (analyzers)."""
    return asyncio.run(
        chat_completion(
            user_id=user_id,
            purpose=purpose,
            messages=messages,
            model_override=model_override,
        )
    )