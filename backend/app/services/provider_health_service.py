"""Provider-level circuit-breaker state machine.

Reads and writes the `provider_health` table. Health is provider-level
(not per-user): if DeepSeek is down it is down for everyone.

A row is created lazily on the first failure or success; the table
itself has no required existence precondition because the schema is
created in `pg_schema.init_provider_health`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.database import get_db

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _upsert_success_sql() -> str:
    return """
        INSERT INTO provider_health (
            provider_id, is_healthy, consecutive_failures,
            last_success_at, updated_at
        ) VALUES (%s, TRUE, 0, NOW(), NOW())
        ON CONFLICT (provider_id) DO UPDATE SET
            is_healthy = TRUE,
            consecutive_failures = 0,
            last_success_at = NOW(),
            cooldown_until = NULL,
            updated_at = NOW()
    """


def _upsert_failure_sql(threshold: int, cooldown_seconds: int) -> str:
    return f"""
        WITH inc AS (
            INSERT INTO provider_health (
                provider_id, is_healthy, consecutive_failures,
                last_failure_at, last_error_code, updated_at
            ) VALUES (%s, TRUE, 1, NOW(), %s, NOW())
            ON CONFLICT (provider_id) DO UPDATE SET
                consecutive_failures = provider_health.consecutive_failures + 1,
                last_failure_at = NOW(),
                last_error_code = EXCLUDED.last_error_code,
                updated_at = NOW()
            RETURNING provider_id, consecutive_failures
        )
        UPDATE provider_health ph
           SET is_healthy = (NOT (inc.consecutive_failures >= {int(threshold)})),
               cooldown_until = CASE
                   WHEN inc.consecutive_failures >= {int(threshold)}
                       THEN NOW() + INTERVAL '{int(cooldown_seconds)} seconds'
                   ELSE ph.cooldown_until
               END,
               updated_at = NOW()
          FROM inc
         WHERE ph.provider_id = inc.provider_id
    """


def record_success(*, provider_id: str) -> None:
    """Reset the breaker for a provider on a successful call."""
    db = get_db()
    try:
        db.execute(_upsert_success_sql(), (provider_id,))
        db.commit()
    finally:
        db.close()


def record_failure(
    *,
    provider_id: str,
    error_code: str,
    failure_threshold: int = 3,
    cooldown_seconds: int = 300,
) -> int:
    """Increment the failure counter; flip to unhealthy if at/over threshold.

    Returns the new consecutive_failures count.
    """
    db = get_db()
    try:
        cur = db.execute(
            _upsert_failure_sql(failure_threshold, cooldown_seconds),
            (provider_id, error_code),
        )
        row = cur.fetchone() if hasattr(cur, "fetchone") else None
        db.commit()
        if row is None:
            return 0
        return int(row["consecutive_failures"]) if isinstance(row, dict) else int(row[0])
    finally:
        db.close()


def reset(*, provider_id: str) -> None:
    """Manual admin reset: clear cooldown and counter, mark healthy."""
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO provider_health (
                provider_id, is_healthy, consecutive_failures,
                last_success_at, updated_at
            ) VALUES (%s, TRUE, 0, NOW(), NOW())
            ON CONFLICT (provider_id) DO UPDATE SET
                is_healthy = TRUE,
                consecutive_failures = 0,
                cooldown_until = NULL,
                updated_at = NOW()
            """,
            (provider_id,),
        )
        db.commit()
    finally:
        db.close()


def is_available(*, provider_id: str) -> bool:
    """Return True if a provider may be used right now.

    A provider is unavailable if its `cooldown_until` is in the future.
    """
    db = get_db()
    try:
        row = db.execute(
            "SELECT cooldown_until FROM provider_health WHERE provider_id=%s",
            (provider_id,),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return True
    cu = row["cooldown_until"] if isinstance(row, dict) else row[0]
    if cu is None:
        return True
    return cu <= _now()


def list_all() -> list[dict[str, Any]]:
    """Return health for every provider that has a row."""
    db = get_db()
    try:
        rows = db.execute(
            "SELECT provider_id, is_healthy, consecutive_failures, "
            "last_success_at, last_failure_at, cooldown_until, last_error_code "
            "FROM provider_health"
        ).fetchall()
    finally:
        db.close()
    out = []
    for r in rows:
        d = dict(r) if not isinstance(r, dict) else r
        out.append({
            "provider_id": d.get("provider_id"),
            "is_healthy": d.get("is_healthy"),
            "consecutive_failures": d.get("consecutive_failures"),
            "last_success_at": d.get("last_success_at"),
            "last_failure_at": d.get("last_failure_at"),
            "cooldown_until": d.get("cooldown_until"),
            "last_error_code": d.get("last_error_code"),
        })
    return out
