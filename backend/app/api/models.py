"""嵌入模型和重排模型列表 API — 从 model_providers 表获取可用模型"""
import json
from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.database import get_db
from app.algorithm.providers_registry import CAPABILITY_EMBEDDING, CAPABILITY_RERANK, normalize_model

router = APIRouter(prefix="/api/models", tags=["models"])


@router.get("/embedding")
def list_embedding_models(user: dict = Depends(get_current_user)):
    """返回所有可用的嵌入模型（从已启用的 provider 中筛选）"""
    db = get_db()
    rows = db.execute(
        "SELECT provider_id, name, models FROM model_providers WHERE is_enabled=1"
    ).fetchall()
    db.close()

    result = []
    for row in rows:
        provider_id = row["provider_id"]
        provider_name = row["name"]
        models_raw = row["models"]
        if isinstance(models_raw, str):
            try:
                models_raw = json.loads(models_raw)
            except (json.JSONDecodeError, TypeError):
                models_raw = []
        if not isinstance(models_raw, list):
            models_raw = []

        for model_id in models_raw:
            normalized = normalize_model(model_id)
            if CAPABILITY_EMBEDDING in normalized["capabilities"]:
                result.append({
                    "id": f"{provider_id}::{normalized['id']}",
                    "providerId": provider_id,
                    "providerName": provider_name,
                    "modelId": normalized["id"],
                    "label": f"{normalized['id']} · {provider_name}",
                })

    return {"data": result, "message": "success", "code": 200}


@router.get("/rerank")
def list_rerank_models(user: dict = Depends(get_current_user)):
    """返回所有可用的重排模型"""
    db = get_db()
    rows = db.execute(
        "SELECT provider_id, name, models FROM model_providers WHERE is_enabled=1"
    ).fetchall()
    db.close()

    result = []
    for row in rows:
        provider_id = row["provider_id"]
        provider_name = row["name"]
        models_raw = row["models"]
        if isinstance(models_raw, str):
            try:
                models_raw = json.loads(models_raw)
            except (json.JSONDecodeError, TypeError):
                models_raw = []
        if not isinstance(models_raw, list):
            models_raw = []

        for model_id in models_raw:
            normalized = normalize_model(model_id)
            if CAPABILITY_RERANK in normalized["capabilities"]:
                result.append({
                    "id": f"{provider_id}::{normalized['id']}",
                    "providerId": provider_id,
                    "providerName": provider_name,
                    "modelId": normalized["id"],
                    "label": f"{normalized['id']} · {provider_name}",
                })

    return {"data": result, "message": "success", "code": 200}
