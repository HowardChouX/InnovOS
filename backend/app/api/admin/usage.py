"""Read-only usage stats over the `model_call_log` table."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth import require_admin
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/usage", tags=["admin-usage"])


_RANGE_DAYS = {"1d": 1, "7d": 7, "30d": 30, "90d": 90}


def _range_days(range_: str) -> int:
    return _RANGE_DAYS.get(range_, 7)


def _row(r) -> dict[str, Any]:
    return dict(r) if not isinstance(r, dict) else r


@router.get("/summary")
def summary(
    range: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    days = _range_days(range)
    sql = [
        "SELECT COUNT(*) AS total, "
        "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
        "COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms, "
        "COALESCE(SUM(CASE WHEN is_success THEN 1 ELSE 0 END), 0) AS success_count "
        "FROM model_call_log "
        "WHERE created_at > NOW() - (%s || ' days')::interval"
    ]
    params: list[Any] = [str(days)]
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    db = get_db()
    try:
        row = _row(db.execute(" ".join(sql), tuple(params)).fetchone())
    finally:
        db.close()
    total = int(row.get("total", 0))
    success = int(row.get("success_count", 0))
    rate = (success / total) if total else 0.0
    return {
        "data": {
            "total_requests": total,
            "total_tokens": int(row.get("total_tokens", 0)),
            "avg_latency_ms": int(row.get("avg_latency_ms", 0)),
            "success_rate": round(rate, 4),
            "range": range,
        },
        "message": "success",
    }


@router.get("/by-provider")
def by_provider(
    range: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    days = _range_days(range)
    sql = [
        "SELECT provider_id, COUNT(*) AS requests, "
        "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
        "COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms, "
        "COALESCE(SUM(CASE WHEN is_success THEN 1 ELSE 0 END), 0) AS success_count "
        "FROM model_call_log "
        "WHERE created_at > NOW() - (%s || ' days')::interval"
    ]
    params: list[Any] = [str(days)]
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    sql.append("GROUP BY provider_id ORDER BY requests DESC")
    db = get_db()
    try:
        rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    finally:
        db.close()
    out = []
    for r in rows:
        d = _row(r)
        total = int(d.get("requests", 0))
        succ = int(d.get("success_count", 0))
        out.append({
            "provider_id": d.get("provider_id"),
            "requests": total,
            "total_tokens": int(d.get("total_tokens", 0)),
            "avg_latency_ms": int(d.get("avg_latency_ms", 0)),
            "success_rate": round(succ / total, 4) if total else 0.0,
        })
    return {"data": out, "message": "success"}


@router.get("/by-model")
def by_model(
    range: str = Query("7d", pattern="^(1d|7d|30d|90d)$"),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    days = _range_days(range)
    sql = [
        "SELECT model_id, COUNT(*) AS requests, "
        "COALESCE(SUM(input_tokens), 0) AS input_tokens, "
        "COALESCE(SUM(output_tokens), 0) AS output_tokens, "
        "COALESCE(SUM(total_tokens), 0) AS total_tokens, "
        "COALESCE(AVG(latency_ms), 0)::int AS avg_latency_ms, "
        "COALESCE(SUM(CASE WHEN is_success THEN 1 ELSE 0 END), 0) AS success_count "
        "FROM model_call_log "
        "WHERE created_at > NOW() - (%s || ' days')::interval"
    ]
    params: list[Any] = [str(days)]
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    sql.append("GROUP BY model_id ORDER BY requests DESC")
    db = get_db()
    try:
        rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    finally:
        db.close()
    out = []
    for r in rows:
        d = _row(r)
        total = int(d.get("requests", 0))
        succ = int(d.get("success_count", 0))
        out.append({
            "model_id": d.get("model_id"),
            "requests": total,
            "input_tokens": int(d.get("input_tokens", 0)),
            "output_tokens": int(d.get("output_tokens", 0)),
            "total_tokens": int(d.get("total_tokens", 0)),
            "avg_latency_ms": int(d.get("avg_latency_ms", 0)),
            "success_rate": round(succ / total, 4) if total else 0.0,
        })
    return {"data": out, "message": "success"}


@router.get("/recent")
def recent(
    limit: int = Query(50, ge=1, le=500),
    user_id: int | None = Query(None),
    _: dict = Depends(require_admin),
) -> dict:
    sql = [
        "SELECT id, user_id, provider_id, model_id, purpose, "
        "input_tokens, output_tokens, total_tokens, latency_ms, "
        "status_code, is_success, error_category, error_message, "
        "is_streaming, failover_from_provider, failover_attempt, created_at "
        "FROM model_call_log WHERE TRUE"
    ]
    params: list[Any] = []
    if user_id is not None:
        sql.append("AND user_id = %s")
        params.append(user_id)
    sql.append("ORDER BY created_at DESC LIMIT %s")
    params.append(limit)
    db = get_db()
    try:
        rows = db.execute(" ".join(sql), tuple(params)).fetchall()
    finally:
        db.close()
    return {"data": [_row(r) for r in rows], "message": "success"}
