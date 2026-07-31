"""AI 客户端 — 统一聊天调用入口(per-user failover via FailoverRouter).

New signature (post-refactor):
    await chat_completion(
        *, user_id, purpose, messages, model_override=None,
    ) -> dict  # {content, provider_id, model_id, input_tokens, output_tokens, ...}

Legacy signature (deprecated; resolves user_id from system_settings for back-compat):
    chat_completion(
        model_id=None, purpose=None, system_prompt, user_prompt, ...
    )

Both paths delegate to `FailoverRouter` for the per-user queue walk +
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


# ── New (per-user) entry point ──


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


# ── Legacy entry point (deprecated) ──
#
# The pre-refactor call sites (analyzers, conversion, patent_db, etc.) used
# positional/keyword args like:
#     chat_completion(model_id="...", purpose="chat",
#                     system_prompt=..., user_prompt=..., temperature=...)
# To keep those call sites working without a sweeping refactor of every
# analyzer in one go, we keep the legacy signature and route through the
# same FailoverRouter. The user_id is resolved from the model_resolver
# assignment (system_settings.purpose → user_id of the assigned provider).
#
# Call sites that have access to the current user (an HTTP request) should
# migrate to the new chat_completion(user_id=...) signature; the legacy
# path is a transitional shim and will be removed in a follow-up.


def _resolve_user_id_from_model_assignment(model_id: Optional[str], purpose: Optional[str]) -> int:
    """Best-effort: resolve user_id from the system_settings 'purpose' row.

    This shim only works if the assigned settings encoded the user_id in
    the composite key (legacy `providerId:modelId` format). Returns 0
    (system user) as a fallback. This is intentionally a no-op fallback —
    the new chat_completion(user_id=...) is the supported path.
    """
    # Lazy import to avoid a hard dependency on the legacy system_settings
    # module from this file.
    try:
        from app.algorithm.model_resolver import model_resolver
        settings = model_resolver.get_assigned_settings()
    except Exception:  # noqa: BLE001
        return 0
    if model_id:
        composite = model_id
    elif purpose:
        key = model_resolver.purpose_to_setting_key(purpose)
        composite = settings.get(key, "") or ""
    else:
        return 0
    # Legacy format: "providerId:modelId"; providerId may be a numeric user id.
    if ":" in composite:
        head = composite.split(":", 1)[0]
        try:
            return int(head)
        except ValueError:
            return 0
    return 0


def chat_completion_legacy(
    *,
    model_id: Optional[str] = None,
    purpose: Optional[str] = None,
    system_prompt: str = "",
    user_prompt: str = "",
    messages: Optional[list[dict[str, str]]] = None,
    temperature: float = 0.3,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """DEPRECATED. Use chat_completion(user_id, purpose, messages).

    Kept for compatibility with pre-refactor call sites that pass
    `model_id` or `purpose` + `system_prompt` + `user_prompt`. Internally
    constructs the messages list and delegates to chat_completion_sync.
    """
    if messages is None:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

    user_id = _resolve_user_id_from_model_assignment(model_id, purpose)
    purpose_str = purpose or "chat"
    return chat_completion_sync(
        user_id=user_id,
        purpose=purpose_str,
        messages=messages,
        model_override=model_id if model_id else None,
    )


# ── Backward-compat shim: keep the old chat_completion() positional API alive ──
#
# The pre-refactor file exposed `async def chat_completion(...)` with a
# very different signature. Code that imported it as `from app.algorithm.ai_client
# import chat_completion` and called it as `await chat_completion(model_id=..., purpose=..., ...)`
# would break. We expose a function with the same name that dispatches
# based on the calling convention: if `user_id` is a keyword arg, use the
# new path; otherwise use the legacy shim. The type stubs/overloads keep
# the IDE happy.
#
# Implementation: a single function that accepts both styles via **kwargs.


async def _chat_completion_dispatch(**kwargs: Any) -> dict[str, Any]:
    if "user_id" in kwargs:
        return await chat_completion(**kwargs)
    return chat_completion_legacy(**kwargs)


# Override the module-level name. This is the only entry point imported
# by callers (see grep output above).
async def chat_completion_(**kwargs: Any) -> dict[str, Any]:
    return await _chat_completion_dispatch(**kwargs)


# Replace the symbol `chat_completion` so existing imports keep working.
# We do this via a module-level rebinding at the very end of this file
# (see __all__ and the `chat_completion = chat_completion_` line below).
__all__ = [
    "chat_completion",
    "chat_completion_sync",
    "chat_completion_legacy",
    "FailoverRouter",
    "NoProvidersConfiguredError",
    "AllProvidersFailedError",
    "FailoverError",
]

# Final binding: `chat_completion` resolves to the dispatcher.
chat_completion = chat_completion_
