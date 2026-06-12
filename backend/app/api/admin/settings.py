"""
Admin settings API — 全局键值配置（模型分配、系统偏好等）

借鉴 Cherry Studio Preference 层概念：
  settings = { "chat_model": "providerId::modelId", "embedding_model": "...", "rerank_model": "..." }
"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_admin
from app.database import get_db
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["admin-settings"])

MODEL_KEYS = ["chat_model", "embedding_model", "rerank_model", "ocr_model"]


class AssignedModelsInput(BaseModel):
    chat_model: Optional[str] = None
    embedding_model: Optional[str] = None
    rerank_model: Optional[str] = None
    ocr_model: Optional[str] = None


class RagConfigInput(BaseModel):
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None
    search_mode: Optional[str] = None
    hybrid_alpha: Optional[float] = None
    threshold: Optional[float] = None
    document_count: Optional[int] = None
    file_processor: Optional[str] = None
    rerank_model: Optional[str] = None


RAG_KEYS = ["chunk_size", "chunk_overlap", "search_mode", "hybrid_alpha", "threshold", "document_count", "file_processor", "rag_rerank_model"]


@router.get("/models/assigned")
def get_assigned_models(user: dict = Depends(require_admin)) -> dict:
    """获取全局模型分配配置"""
    db = get_db()
    rows = db.execute(
        "SELECT key, value FROM system_settings WHERE key IN (?, ?, ?, ?)",
        ("chat_model", "embedding_model", "rerank_model", "ocr_model"),
    ).fetchall()
    db.close()
    result = {k: None for k in MODEL_KEYS}
    for r in rows:
        result[r["key"]] = r["value"]
    return {"data": result}


@router.put("/models/assigned")
def set_assigned_models(body: AssignedModelsInput, user: dict = Depends(require_admin)) -> dict:
    """设置全局模型分配配置"""
    db = get_db()
    for key in MODEL_KEYS:
        val = getattr(body, key, None)
        if val is not None:
            # Upsert
            existing = db.execute("SELECT id FROM system_settings WHERE key=?", (key,)).fetchone()
            if existing:
                db.execute("UPDATE system_settings SET value=?, updated_at=CURRENT_TIMESTAMP WHERE key=?", (val, key))
            else:
                db.execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", (key, val))
    db.commit()
    db.close()
    return {"message": "saved"}


def _upsert_setting(key: str, value: str):
    db = get_db()
    existing = db.execute("SELECT id FROM system_settings WHERE key=?", (key,)).fetchone()
    if existing:
        db.execute("UPDATE system_settings SET value=?, updated_at=CURRENT_TIMESTAMP WHERE key=?", (value, key))
    else:
        db.execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", (key, value))
    db.commit()
    db.close()


def _get_settings(keys: list[str]) -> dict:
    db = get_db()
    rows = db.execute(
        f"SELECT key, value FROM system_settings WHERE key IN ({','.join('?' * len(keys))})",
        keys,
    ).fetchall()
    db.close()
    result = {k: None for k in keys}
    for r in rows:
        result[r["key"]] = r["value"]
    return result


@router.get("/rag")
def get_rag_config(user: dict = Depends(require_admin)) -> dict:
    """获取全局 RAG 默认配置"""
    raw = _get_settings(RAG_KEYS)
    return {"data": raw}


@router.put("/rag")
def set_rag_config(body: RagConfigInput, user: dict = Depends(require_admin)) -> dict:
    """设置全局 RAG 默认配置"""
    mapping = {
        "chunk_size": body.chunk_size,
        "chunk_overlap": body.chunk_overlap,
        "search_mode": body.search_mode,
        "hybrid_alpha": body.hybrid_alpha,
        "threshold": body.threshold,
        "document_count": body.document_count,
        "file_processor": body.file_processor,
        "rag_rerank_model": body.rerank_model,
    }
    for key, val in mapping.items():
        if val is not None:
            _upsert_setting(key, str(val))
    return {"message": "saved"}


@router.get("/models/available")
def get_available_models(user: dict = Depends(require_admin)) -> dict:
    """获取所有可用模型（按能力分组），供管理后台选择器使用

    返回结构：
    {
      chat: [{ providerId, modelId, name, capabilities }],
      embedding: [...],
      rerank: [...]
    }
    """
    from app.algorithm.model_service import model_service
    from app.algorithm.providers_registry import get_model_id, get_model_capabilities, CAPABILITY_EMBEDDING, CAPABILITY_RERANK, CAPABILITY_VISION

    providers = model_service.list_all()
    chat_models = []
    embedding_models = []
    rerank_models = []
    vision_models = []

    for p in providers:
        if not p["isEnabled"]:
            continue
        provider_id = p["providerId"]
        for m in p.get("models", []):
            mid = get_model_id(m)
            if not mid:
                continue
            caps = get_model_capabilities(m)
            entry = {"providerId": provider_id, "modelId": mid, "name": mid, "capabilities": caps}
            chat_models.append(entry)
            if CAPABILITY_EMBEDDING in caps:
                embedding_models.append(entry)
            if CAPABILITY_RERANK in caps:
                rerank_models.append(entry)
            if CAPABILITY_VISION in caps:
                vision_models.append(entry)

    return {
        "data": {
            "chat": sorted(chat_models, key=lambda x: x["modelId"]),
            "embedding": sorted(embedding_models, key=lambda x: x["modelId"]),
            "rerank": sorted(rerank_models, key=lambda x: x["modelId"]),
            "vision": sorted(vision_models, key=lambda x: x["modelId"]),
        }
    }
