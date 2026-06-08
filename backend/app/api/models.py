"""嵌入模型和重排模型列表 API — 从 model_providers 表获取可用模型"""
from fastapi import APIRouter, Depends
from app.auth import get_current_user
from app.database import get_db
import json

router = APIRouter(prefix="/api/models", tags=["models"])

EMBEDDING_KEYWORDS = ["embedding", "embed", "bge-embed", "e5-", "text-embedding", "gte-", "e5_small", "e5_large"]
RERANK_KEYWORDS = ["rerank", "re-rank", "cross-encoder", "bge-reranker"]


def _is_embedding_model(model_name: str) -> bool:
    name_lower = model_name.lower()
    if any(kw in name_lower for kw in RERANK_KEYWORDS):
        return False
    return any(kw in name_lower for kw in EMBEDDING_KEYWORDS)


def _is_rerank_model(model_name: str) -> bool:
    name_lower = model_name.lower()
    return any(kw in name_lower for kw in RERANK_KEYWORDS)


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
            if _is_embedding_model(model_id):
                result.append({
                    "id": f"{provider_id}::{model_id}",
                    "providerId": provider_id,
                    "providerName": provider_name,
                    "modelId": model_id,
                    "label": f"{model_id} · {provider_name}",
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
            if _is_rerank_model(model_id):
                result.append({
                    "id": f"{provider_id}::{model_id}",
                    "providerId": provider_id,
                    "providerName": provider_name,
                    "modelId": model_id,
                    "label": f"{model_id} · {provider_name}",
                })

    return {"data": result, "message": "success", "code": 200}
