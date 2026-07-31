"""Per-user model service enable + failover order."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_admin
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users/{user_id}/model-services", tags=["admin-user-model-services"])


class AddBody(BaseModel):
    provider_id: str


class OrderBody(BaseModel):
    provider_ids: list[str]


class ToggleBody(BaseModel):
    is_enabled: bool


def _row_to_dict(r) -> dict[str, Any]:
    return dict(r) if not isinstance(r, dict) else r


def _load(user_id: int) -> list[dict[str, Any]]:
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT
                ums.provider_id,
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
            WHERE ums.user_id = %s
            ORDER BY ums.failover_order ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()
    return [_row_to_dict(r) for r in rows]


def _load_available(user_id: int) -> list[dict[str, Any]]:
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
                    WHERE ums2.user_id = %s AND ums2.provider_id = mp.provider_id
                ) AS already_enabled
            FROM model_providers mp
            LEFT JOIN provider_health ph ON ph.provider_id = mp.provider_id
            ORDER BY mp.name ASC
            """,
            (user_id,),
        ).fetchall()
    finally:
        db.close()
    return [_row_to_dict(r) for r in rows]


def _next_order(user_id: int) -> int:
    db = get_db()
    try:
        row = db.execute(
            "SELECT COALESCE(MAX(failover_order), 0) + 1 AS next FROM user_model_services WHERE user_id=%s",
            (user_id,),
        ).fetchone()
    finally:
        db.close()
    if row is None:
        return 1
    n = row["next"] if isinstance(row, dict) else row[0]
    return int(n or 1)


@router.get("")
def list_user_services(user_id: int, _: dict = Depends(require_admin)) -> dict:
    return {"data": _load(user_id), "message": "success"}


@router.get("/available")
def list_available_services(user_id: int, _: dict = Depends(require_admin)) -> dict:
    return {"data": _load_available(user_id), "message": "success"}


@router.post("")
def add_user_service(user_id: int, body: AddBody, _: dict = Depends(require_admin)) -> dict:
    db = get_db()
    try:
        existing = db.execute(
            "SELECT failover_order, is_enabled FROM user_model_services "
            "WHERE user_id=%s AND provider_id=%s",
            (user_id, body.provider_id),
        ).fetchone()
        if existing is not None:
            return {"data": _row_to_dict(existing), "message": "already enabled"}
        order = _next_order(user_id)
        db.execute(
            "INSERT INTO user_model_services (user_id, provider_id, failover_order, is_enabled) "
            "VALUES (%s, %s, %s, TRUE)",
            (user_id, body.provider_id, order),
        )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id), "message": "added"}


@router.delete("/{provider_id}", status_code=204)
def remove_user_service(user_id: int, provider_id: str, _: dict = Depends(require_admin)):
    db = get_db()
    try:
        db.execute(
            "DELETE FROM user_model_services WHERE user_id=%s AND provider_id=%s",
            (user_id, provider_id),
        )
        db.commit()
    finally:
        db.close()
    return None


@router.post("/{provider_id}/toggle")
def toggle_user_service(
    user_id: int, provider_id: str, body: ToggleBody, _: dict = Depends(require_admin)
) -> dict:
    db = get_db()
    try:
        cur = db.execute(
            "UPDATE user_model_services SET is_enabled=%s, updated_at=NOW() "
            "WHERE user_id=%s AND provider_id=%s",
            (bool(body.is_enabled), user_id, provider_id),
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
                f"WHERE user_id=%s AND provider_id NOT IN ({placeholders})",
                tuple([user_id, *new_ids]),
            )
        else:
            db.execute(
                "DELETE FROM user_model_services WHERE user_id=%s",
                (user_id,),
            )
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "INSERT INTO user_model_services (user_id, provider_id, failover_order, is_enabled) "
                "VALUES (%s, %s, %s, TRUE) "
                "ON CONFLICT (user_id, provider_id) DO UPDATE SET updated_at=NOW()",
                (user_id, pid, offset + 1_000_000),
            )
        for offset, pid in enumerate(new_ids, start=1):
            db.execute(
                "UPDATE user_model_services SET failover_order=%s, updated_at=NOW() "
                "WHERE user_id=%s AND provider_id=%s",
                (offset, user_id, pid),
            )
        db.commit()
    finally:
        db.close()
    return {"data": _load(user_id), "message": "reordered"}
