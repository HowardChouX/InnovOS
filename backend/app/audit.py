"""
Audit logging — tracks all destructive operations for security review.
"""

import json
import logging

from app.database import get_db

logger = logging.getLogger(__name__)


def log_audit(
    user_id: int,
    username: str,
    action: str,
    resource_type: str = "",
    resource_id: str = "",
    detail: dict | None = None,
    ip_address: str = "",
) -> None:
    """Write a row to the audit_log table."""
    db = None
    try:
        db = get_db()
        db.execute(
            """INSERT INTO audit_log
               (user_id, username, action, resource_type, resource_id, detail, ip_address)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (user_id, username, action, resource_type, resource_id, json.dumps(detail or {}), ip_address),
        )
        db.commit()
    except Exception as e:
        logger.warning(f"Audit log write failed: {e}")
    finally:
        if db is not None:
            db.close()
