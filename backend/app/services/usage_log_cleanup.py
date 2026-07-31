"""Daily 03:00 retention sweep for `model_call_log`.

Deletes rows older than `MODEL_CALL_LOG_RETENTION_DAYS` (default 90).
Called from `backup_service` alongside the existing DB snapshot.
"""
from __future__ import annotations

import logging
import os

from app.database import get_db

logger = logging.getLogger(__name__)


def _retention_days() -> int:
    try:
        return int(os.environ.get("MODEL_CALL_LOG_RETENTION_DAYS", "90"))
    except (TypeError, ValueError):
        return 90


def run() -> int:
    days = _retention_days()
    db = get_db()
    try:
        cur = db.execute(
            "DELETE FROM model_call_log "
            "WHERE created_at < NOW() - (%s || ' days')::interval",
            (str(days),),
        )
        deleted = cur.rowcount or 0
        db.commit()
        logger.info("model_call_log retention: deleted %d rows older than %d days", deleted, days)
        return int(deleted)
    finally:
        db.close()
