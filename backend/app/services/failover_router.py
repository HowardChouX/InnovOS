"""Per-user failover queue walker.

At request time, given `(user_id, purpose)`, walks the user's enabled
`user_model_services` queue (ordered by `failover_order ASC`) and tries
each entry's underlying OpenAI-compatible API. A 3-failure streak on
the same provider flips `provider_health.is_healthy=false` and sets
`cooldown_until = NOW() + 5 minutes` (provider is skipped during
cooldown).

The first successful response wins; one `model_call_log` row is
written per attempt (so the full failover chain is auditable).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import Any, Optional

import httpx

from app.core.key_crypto import load_api_key_cipher
from app.database import get_db
from app.services import provider_health_service as health_svc
from app.services import usage_logger

logger = logging.getLogger(__name__)


# ── Errors ──


class FailoverError(RuntimeError):
    """Base class for runtime errors from the router."""


class NoProvidersConfiguredError(FailoverError):
    """The user has no enabled providers in their queue."""


class AllProvidersFailedError(FailoverError):
    """Every entry in the queue was tried and failed."""


# ── Constants ──

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_COOLDOWN_SECONDS = 300
DEFAULT_MAX_ATTEMPTS = 4
DEFAULT_TIMEOUT_SECONDS = 30.0

# Purpose → user_model_services.capability. 文本类用途都走 chat 队列,
# 向量类用途分别走 embedding / rerank 队列。
PURPOSE_TO_CAPABILITY: dict[str, str] = {
    "chat": "chat",
    "evaluation": "chat",
    "conversion": "chat",
    "extract": "chat",
    "ocr": "chat",
    "embedding": "embedding",
    "rerank": "rerank",
}


# ── Internal helpers ──


def _classify_error(exc: Exception) -> str:
    """Return category: 'provider', 'auth', 'rate_limit', 'timeout', 'client', 'unknown'."""
    msg = str(exc).lower()
    if re.search(r"\b5\d{2}\b", msg) or "internal server error" in msg or "bad gateway" in msg:
        return "provider"
    if re.search(r"\b401\b", msg) or re.search(r"\b403\b", msg) or "unauthorized" in msg:
        return "auth"
    if re.search(r"\b429\b", msg) or "rate limit" in msg or "too many" in msg:
        return "rate_limit"
    if "timeout" in msg or "timed out" in msg or "connection" in msg:
        return "timeout"
    if re.search(r"\b4\d{2}\b", msg):
        return "client"
    return "unknown"


def _status_code_for(category: str) -> int:
    return {
        "provider": 500,
        "auth": 401,
        "rate_limit": 429,
        "timeout": 504,
        "client": 400,
        "unknown": 500,
    }.get(category, 500)


def _purpose_to_capability(purpose: str) -> str:
    return PURPOSE_TO_CAPABILITY.get(purpose, "chat")


def _load_queue(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    """Return the user's enabled queue for a given capability, joined with provider + key + health."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
                ums.capability,
                mp.api_host,
                mp.api_model,
                ak.id              AS key_id,
                ak.key_ciphertext  AS api_key_ciphertext,
                ak.key_nonce       AS api_key_nonce,
                ak.encryption_version,
                ph.is_healthy,
                ph.cooldown_until
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            JOIN api_keys ak
                 ON ak.provider_id = ums.provider_id
                AND ak.is_active = TRUE
            LEFT JOIN provider_health ph ON ph.provider_id = ums.provider_id
            WHERE ums.user_id = %s
              AND ums.capability = %s
              AND ums.is_enabled = TRUE
              AND mp.is_enabled = 1
              AND ak.priority = 0
            ORDER BY ums.failover_order ASC
            """,
            (user_id, capability),
        ).fetchall()
    finally:
        db.close()

    out: list[dict[str, Any]] = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        if not health_svc.is_available(provider_id=d["provider_id"]):
            continue
        out.append(d)
    return out


async def _call_one(
    provider_id: str,
    model_id: str,
    messages: list[dict],
    *,
    api_host: str,
    api_key_plaintext: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Make a single upstream non-streaming chat call. Returns parsed content + usage."""
    if not api_host or not api_key_plaintext:
        raise RuntimeError("missing api_host or api_key for provider")

    base = api_host.rstrip("/")
    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    body = {
        "model": model_id,
        "messages": messages,
        "stream": False,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key_plaintext}"},
            json=body,
        )
        if r.status_code >= 400:
            # raise so the router can record failure and try next
            raise RuntimeError(f"upstream HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()

    content = ""
    choices = data.get("choices") or []
    if choices:
        msg = choices[0].get("message") or {}
        content = msg.get("content", "") or ""
    usage = data.get("usage") or {}
    return {
        "content": content,
        "input_tokens": int(usage.get("prompt_tokens", 0) or 0),
        "output_tokens": int(usage.get("completion_tokens", 0) or 0),
    }


# ── Router ──


class FailoverRouter:
    def __init__(
        self,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.max_attempts = max_attempts

    async def call(
        self,
        *,
        user_id: int,
        purpose: str,
        messages: list[dict],
        model_override: Optional[str] = None,
    ) -> dict[str, Any]:
        # purpose → capability 映射,让 embedding / rerank 走各自队列
        capability = _purpose_to_capability(purpose)
        queue = _load_queue(user_id, capability=capability)
        if not queue:
            raise NoProvidersConfiguredError(
                f"user {user_id} has no enabled model services for purpose {purpose!r}"
            )

        attempts = 0
        previous_provider_id: Optional[str] = None
        last_error: Optional[Exception] = None

        cipher = load_api_key_cipher()

        for entry in queue:
            if attempts >= self.max_attempts:
                break
            attempts += 1
            provider_id = entry["provider_id"]
            model_id = model_override or entry.get("api_model") or ""
            started = time.perf_counter()
            status_code = 0
            is_success = False
            error_category: Optional[str] = None
            error_message: Optional[str] = None
            result: Optional[dict[str, Any]] = None

            try:
                # Decrypt the API key (sync, fast; do it inline).
                key_plain = cipher.decrypt(
                    ciphertext=bytes(entry["api_key_ciphertext"]),
                    nonce=bytes(entry["api_key_nonce"]),
                    encryption_version=int(entry["encryption_version"]),
                    provider_id=provider_id,
                    key_id=int(entry["key_id"]),
                )
                result = await _call_one(
                    provider_id,
                    model_id,
                    messages,
                    api_host=entry["api_host"],
                    api_key_plaintext=key_plain,
                )
                is_success = True
                status_code = 200
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                error_category = _classify_error(exc)
                error_message = str(exc)[:500]
                status_code = _status_code_for(error_category)
                try:
                    health_svc.record_failure(
                        provider_id=provider_id,
                        error_code=error_category,
                        failure_threshold=self.failure_threshold,
                        cooldown_seconds=self.cooldown_seconds,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("record_failure failed for %s", provider_id)

            latency_ms = int((time.perf_counter() - started) * 1000)
            input_tokens = int((result or {}).get("input_tokens", 0))
            output_tokens = int((result or {}).get("output_tokens", 0))
            content = (result or {}).get("content", "")

            usage_logger.record_call(
                user_id=user_id,
                provider_id=provider_id,
                model_id=model_id,
                purpose=purpose,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                latency_ms=latency_ms,
                status_code=status_code,
                is_success=is_success,
                error_category=error_category,
                error_message=error_message,
                failover_from_provider=previous_provider_id,
                failover_attempt=attempts,
            )

            if is_success and result is not None:
                try:
                    health_svc.record_success(provider_id=provider_id)
                except Exception:  # noqa: BLE001
                    logger.exception("record_success failed for %s", provider_id)
                return {
                    "content": content,
                    "provider_id": provider_id,
                    "model_id": model_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_ms": latency_ms,
                    "failover_attempts": attempts,
                }

            previous_provider_id = provider_id

        raise AllProvidersFailedError(
            f"all {attempts} provider(s) failed for user {user_id} (purpose={purpose!r}); "
            f"last error: {last_error!r}"
        )
