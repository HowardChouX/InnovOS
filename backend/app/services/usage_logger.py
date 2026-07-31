"""Fire-and-forget writer for the model_call_log table.

Used by FailoverRouter to record every attempt (success or failure),
including failover chain metadata. Failures of the writer itself are
logged at WARNING and never raised — usage logging must not block
the user-facing call.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.database import get_db

logger = logging.getLogger(__name__)


_INSERT_SQL = """
    INSERT INTO model_call_log (
        user_id, provider_id, model_id, purpose,
        input_tokens, output_tokens, total_tokens, latency_ms,
        status_code, is_success, error_category, error_message,
        is_streaming, failover_from_provider, failover_attempt
    ) VALUES (
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s, %s,
        %s, %s, %s
    )
"""


def record_call(
    *,
    user_id: Optional[int],
    provider_id: str,
    model_id: str,
    purpose: str = "chat",
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    latency_ms: int = 0,
    status_code: int = 0,
    is_success: bool = False,
    error_category: Optional[str] = None,
    error_message: Optional[str] = None,
    is_streaming: bool = False,
    failover_from_provider: Optional[str] = None,
    failover_attempt: int = 1,
) -> None:
    """Insert one model_call_log row. Never raises."""
    try:
        db = get_db()
        try:
            db.execute(
                _INSERT_SQL,
                (
                    user_id, provider_id, model_id, purpose,
                    input_tokens, output_tokens, total_tokens, latency_ms,
                    status_code, is_success, error_category, error_message,
                    is_streaming, failover_from_provider, failover_attempt,
                ),
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("usage_logger.record_call failed: %s", exc)
