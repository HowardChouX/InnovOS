"""Thin model service layer (post-refactor).

Stores the catalog of model service entries (rows in `model_providers`).
Each entry has exactly one encrypted API key in `api_keys`
(priority=0, name='default') created/updated via `ApiKeyService`.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from app.core.key_crypto import load_api_key_cipher
from app.database import get_db
from app.services.api_key_service import ApiKeyService

logger = logging.getLogger(__name__)


class ModelService:
    # ── Read ──

    def list_all(self) -> list[dict[str, Any]]:
        db = get_db()
        try:
            rows = db.execute(
                "SELECT provider_id, name, notes, api_host, api_model, protocol, is_enabled, "
                "created_at, updated_at "
                "FROM model_providers ORDER BY id ASC"
            ).fetchall()
        finally:
            db.close()
        return [self._row_to_dict(r) for r in rows]

    def get(self, provider_id: str) -> Optional[dict[str, Any]]:
        db = get_db()
        try:
            row = db.execute(
                "SELECT provider_id, name, notes, api_host, api_model, protocol, is_enabled, "
                "created_at, updated_at "
                "FROM model_providers WHERE provider_id=%s",
                (provider_id,),
            ).fetchone()
        finally:
            db.close()
        return self._row_to_dict(row) if row else None

    # ── Write ──

    def upsert(
        self,
        *,
        provider_id: str,
        name: str,
        notes: str = "",
        api_host: str,
        api_key_plaintext: str,
        api_model: str = "",
        protocol: str = "openai",
    ) -> dict[str, Any]:
        if not provider_id or not provider_id.strip():
            raise ValueError("provider_id is required")
        if not name.strip():
            raise ValueError("name is required")
        if not api_host.strip():
            raise ValueError("api_host is required")
        if not api_key_plaintext:
            raise ValueError("api_key is required")

        VALID_PROTOCOLS = {"openai", "video_minimax", "video_dashscope"}
        if protocol not in VALID_PROTOCOLS:
            raise ValueError(f"invalid protocol: {protocol}")

        db = get_db()
        try:
            existing = db.execute(
                "SELECT id FROM model_providers WHERE provider_id=%s",
                (provider_id,),
            ).fetchone()
            if existing is None:
                db.execute(
                    "INSERT INTO model_providers (provider_id, name, notes, api_host, "
                    "api_model, protocol, models, max_rpm, is_enabled) "
                    "VALUES (%s, %s, %s, %s, %s, %s, '[]', 60, 1)",
                    (provider_id, name, notes or "", api_host, api_model or "", protocol),
                )
            else:
                db.execute(
                    "UPDATE model_providers SET name=%s, notes=%s, api_host=%s, "
                    "api_model=%s, protocol=%s WHERE provider_id=%s",
                    (name, notes or "", api_host, api_model or "", protocol, provider_id),
                )
            db.commit()
        finally:
            db.close()

        self._upsert_api_key(provider_id=provider_id, plaintext=api_key_plaintext)
        return self.get(provider_id)  # type: ignore[return-value]

    def update(
        self,
        provider_id: str,
        *,
        name: Optional[str] = None,
        notes: Optional[str] = None,
        api_host: Optional[str] = None,
        api_model: Optional[str] = None,
        is_enabled: Optional[bool] = None,
        protocol: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        current = self.get(provider_id)
        if current is None:
            return None
        if protocol is not None:
            VALID_PROTOCOLS = {"openai", "video_minimax", "video_dashscope"}
            if protocol not in VALID_PROTOCOLS:
                raise ValueError(f"invalid protocol: {protocol}")
        merged = {
            "name": name if name is not None else current["name"],
            "notes": notes if notes is not None else current["notes"],
            "api_host": api_host if api_host is not None else current["apiHost"],
            "api_model": api_model if api_model is not None else current["apiModel"],
            "is_enabled": is_enabled if is_enabled is not None else current["isEnabled"],
            "protocol": protocol if protocol is not None else current["protocol"],
        }
        db = get_db()
        try:
            db.execute(
                "UPDATE model_providers SET name=%s, notes=%s, api_host=%s, "
                "api_model=%s, is_enabled=%s, protocol=%s WHERE provider_id=%s",
                (merged["name"], merged["notes"], merged["api_host"],
                 merged["api_model"], int(bool(merged["is_enabled"])),
                 merged["protocol"], provider_id),
            )
            db.commit()
        finally:
            db.close()
        return self.get(provider_id)

    def delete(self, provider_id: str) -> bool:
        db = get_db()
        try:
            cur = db.execute(
                "DELETE FROM model_providers WHERE provider_id=%s",
                (provider_id,),
            )
            db.commit()
            return (cur.rowcount or 0) > 0
        finally:
            db.close()

    # ── Internal helpers ──

    def _upsert_api_key(self, *, provider_id: str, plaintext: str) -> None:
        key_svc = ApiKeyService(db=get_db(), cipher=load_api_key_cipher())
        existing = key_svc.list_keys(provider_id=provider_id)
        if existing:
            key_svc.replace_secret(
                key_id=existing[0]["id"],
                plaintext=plaintext,
                actor_id=None,
            )
        else:
            key_svc.create_key(
                provider_id=provider_id,
                name="default",
                plaintext=plaintext,
                priority=0,
                max_rpm=None,
                actor_id=None,
            )

    def _lease_key_plaintext(self, provider_id: str) -> Optional[str]:
        key_svc = ApiKeyService(db=get_db(), cipher=load_api_key_cipher())
        lease = key_svc.lease_key(provider_id=provider_id)
        return lease.plaintext if lease else None

    # ── Async operations: detect / check ──

    async def detect_models(
        self,
        provider_id: str,
        *,
        api_host: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> dict[str, Any]:
        host = api_host
        key = api_key
        if host is None or key is None:
            current = self.get(provider_id)
            if current is None:
                raise LookupError(f"provider {provider_id!r} not found")
            if host is None:
                host = current["apiHost"]
            if key is None:
                key = self._lease_key_plaintext(provider_id)
        if not host or not key:
            raise ValueError("api_host and api_key are required for detect")

        base = host.rstrip("/")
        if base.endswith("/v1/models") or "/v1/models" in base:
            url = base
        else:
            url = f"{base}/v1/models"

        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(
                url, headers={"Authorization": f"Bearer {key}"}
            )
            r.raise_for_status()
            data = r.json()
        models = []
        for entry in data.get("data", []) or []:
            mid = entry.get("id")
            if mid:
                models.append({"id": mid, "name": mid})
        return {"models": models}

    async def check_connection(
        self,
        provider_id: str,
        model: Optional[str] = None,
    ) -> dict[str, Any]:
        import time
        current = self.get(provider_id)
        if current is None:
            return {"status": "not_found"}
        key = self._lease_key_plaintext(provider_id)
        if not key:
            return {"status": "no_key"}
        model_id = model or current.get("apiModel") or ""
        if not model_id:
            return {"status": "no_model"}
        base = current["apiHost"].rstrip("/")
        url = f"{base}/v1/chat/completions" if not base.endswith("/chat/completions") else base
        body = {
            "model": model_id,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1,
        }
        started = time.perf_counter()
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                resp = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {key}"},
                    json=body,
                )
            except Exception as exc:  # noqa: BLE001
                return {"status": "error", "message": str(exc)[:200]}
        latency_ms = int((time.perf_counter() - started) * 1000)
        return {
            "status": "ok" if resp.status_code < 400 else "error",
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "model": model_id,
        }

    # ── Internal: row → dict ──

    @staticmethod
    def _row_to_dict(row) -> dict[str, Any]:
        d = dict(row) if not isinstance(row, dict) else row
        return {
            "providerId": d.get("provider_id"),
            "name": d.get("name") or "",
            "notes": d.get("notes") or "",
            "apiHost": d.get("api_host") or "",
            "apiModel": d.get("api_model") or "",
            "protocol": d.get("protocol") or "openai",
            "isEnabled": bool(d.get("is_enabled", True)),
            "createdAt": str(d.get("created_at") or ""),
            "updatedAt": str(d.get("updated_at") or ""),
        }


model_service = ModelService()
