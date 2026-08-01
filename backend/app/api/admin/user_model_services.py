"""Per-user model service enable + failover order."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import require_admin
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users/{user_id}/model-services", tags=["admin-user-model-services"])

VALID_CAPABILITIES = {"chat", "embedding", "rerank", "image", "video"}


def _check_capability(capability: str) -> None:
    """校验 capability 取值，非法值返回 400。"""
    if capability not in VALID_CAPABILITIES:
        raise HTTPException(status_code=400, detail=f"invalid capability: {capability}")


class AddBody(BaseModel):
    provider_id: str
    capability: str = "chat"


class OrderBody(BaseModel):
    provider_ids: list[str]
    capability: str = "chat"


class ToggleBody(BaseModel):
    is_enabled: bool
    capability: str = "chat"


def _row_to_dict(r) -> dict[str, Any]:
    return dict(r) if not isinstance(r, dict) else r


def _load(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
                ums.capability,
                ums.failover_order,
                ums.is_enabled,
                mp.name,
                mp.api_host,
                mp.api_model,
                COALESCE(ph.is_healthy, TRUE) AS is_healthy,
                COALESCE(ph.consecutive_failures, 0) AS consecutive_failures,
                ph.cooldown_until
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            LEFT JOIN provider_health ph ON ph.provider_id = ums.provider_id
            WHERE ums.user_id = %s AND ums.capability = %s
            ORDER BY ums.failover_order ASC
            """,
            (user_id, capability),
        ).fetchall()
    finally:
        db.close()
    return [_row_to_dict(r) for r in rows]


def _load_available(user_id: int, capability: str = "chat") -> list[dict[str, Any]]:
    """返回可开通的供应商列表（尚未开通该能力的）"""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                mp.provider_id,
                mp.name,
                mp.api_host,
                mp.api_model,
                COALESCE(ph.is_healthy, TRUE) AS is_healthy,
                EXISTS (
                    SELECT 1 FROM user_model_services ums2
                    WHERE ums2.user_id = %s
                      AND ums2.provider_id = mp.provider_id
                      AND ums2.capability = %s
                ) AS already_enabled
            FROM model_providers mp
            LEFT JOIN provider_health ph ON ph.provider_id = mp.provider_id
            ORDER BY mp.name ASC
            """,
            (user_id, capability),
        ).fetchall()
    finally:
        db.close()
    return [_row_to_dict(r) for r in rows]


def _next_order(user_id: int, capability: str = "chat") -> int:
    db = get_db()
    try:
        row = db.execute(
            """SELECT COALESCE(MAX(failover_order), 0) + 1 AS next
               FROM user_model_services
               WHERE user_id=%s AND capability=%s""",
            (user_id, capability),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return 1
    n = row["next"] if isinstance(row, dict) else row[0]
    return int(n or 1)


@router.get("")
def list_user_services(
    user_id: int,
    capability: str = Query("chat", description="能力类型: chat/embedding/rerank"),
    _: dict = Depends(require_admin),
) -> dict:
    _check_capability(capability)
    return {"data": _load(user_id, capability), "message": "success"}


@router.get("/available")
def list_available_services(
    user_id: int,
    capability: str = Query("chat", description="能力类型: chat/embedding/rerank"),
    _: dict = Depends(require_admin),
) -> dict:
    _check_capability(capability)
    return {"data": _load_available(user_id, capability), "message": "success"}


@router.post("")
def add_user_service(
    user_id: int, body: AddBody, _: dict = Depends(require_admin)
) -> dict:
    _check_capability(body.capability)
    db = get_db()
    try:
        existing = db.execute(
            "SELECT failover_order, is_enabled FROM user_model_services "
            "WHERE user_id=%s AND provider_id=%s AND capability=%s",
            (user_id, body.provider_id, body.capability),
        ).fetchone()
        if existing is not None:
            return {"data": _row_to_dict(existing), "message": "already enabled"}
        order = _next_order(user_id, body.capability)
        db.execute(
            "INSERT INTO user_model_services (user_id, provider_id, capability, failover_order, is_enabled) "
            "VALUES (%s, %s, %s, %s, TRUE)",
            (user_id, body.provider_id, body.capability, order),
        )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id, body.capability), "message": "added"}


@router.delete("/{provider_id}", status_code=204)
def remove_user_service(
    user_id: int,
    provider_id: str,
    capability: str = Query("chat"),
    _: dict = Depends(require_admin),
):
    _check_capability(capability)
    db = get_db()
    try:
        db.execute(
            "DELETE FROM user_model_services WHERE user_id=%s AND provider_id=%s AND capability=%s",
            (user_id, provider_id, capability),
        )
        db.commit()
    finally:
        db.close()
    return None


@router.post("/{provider_id}/toggle")
def toggle_user_service(
    user_id: int, provider_id: str, body: ToggleBody, _: dict = Depends(require_admin)
) -> dict:
    _check_capability(body.capability)
    db = get_db()
    try:
        cur = db.execute(
            "UPDATE user_model_services SET is_enabled=%s, updated_at=NOW() "
            "WHERE user_id=%s AND provider_id=%s AND capability=%s",
            (bool(body.is_enabled), user_id, provider_id, body.capability),
        )
        db.commit()
    finally:
        db.close()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="not enabled")
    return {"data": {"is_enabled": body.is_enabled}, "message": "toggled"}


@router.put("/order")
def reorder_user_services(
    user_id: int, body: OrderBody, _: dict = Depends(require_admin)
) -> dict:
    _check_capability(body.capability)
    new_ids = list(body.provider_ids)
    seen: set[str] = set()
    for pid in new_ids:
        if pid in seen:
            raise HTTPException(status_code=409, detail=f"duplicate provider_id: {pid}")
        seen.add(pid)

    db = get_db()
    try:
        if new_ids:
            placeholders = ",".join(["%s"] * len(new_ids))
            db.execute(
                f"DELETE FROM user_model_services "
                f"WHERE user_id=%s AND capability=%s AND provider_id NOT IN ({placeholders})",
                (user_id, body.capability, *new_ids),
            )
        else:
            db.execute(
                "DELETE FROM user_model_services WHERE user_id=%s AND capability=%s",
                (user_id, body.capability),
            )
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "INSERT INTO user_model_services (user_id, provider_id, capability, failover_order, is_enabled) "
                "VALUES (%s, %s, %s, %s, TRUE) "
                "ON CONFLICT (user_id, provider_id, capability) DO UPDATE SET updated_at=NOW()",
                (user_id, pid, body.capability, offset + 1_000_000),
            )
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "UPDATE user_model_services SET failover_order=%s, updated_at=NOW() "
                "WHERE user_id=%s AND provider_id=%s AND capability=%s",
                (offset, user_id, pid, body.capability),
            )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id, body.capability), "message": "reordered"}
