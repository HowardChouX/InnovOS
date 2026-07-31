"""Admin global view of provider health (circuit-breaker state)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from app.auth import require_admin
from app.database import get_db
from app.services import provider_health_service as health_svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/failover", tags=["admin-failover"])


def _row(r):
    return dict(r) if not isinstance(r, dict) else r


@router.get("/health")
def health_overview(_: dict = Depends(require_admin)) -> dict:
    rows = health_svc.list_all()
    db = get_db()
    try:
        providers = db.execute("SELECT provider_id, name FROM model_providers").fetchall()
    finally:
        db.close()
    by_id = {r["provider_id"] if isinstance(r, dict) else r[0]:
             r["name"] if isinstance(r, dict) else r[1]
             for r in providers}
    for h in rows:
        h["name"] = by_id.get(h.get("provider_id"), "")
    return {"data": rows, "message": "success"}


@router.post("/{provider_id}/reset")
def reset_provider(provider_id: str, _: dict = Depends(require_admin)) -> dict:
    health_svc.reset(provider_id=provider_id)
    return {"data": {"provider_id": provider_id, "is_healthy": True}, "message": "reset"}
