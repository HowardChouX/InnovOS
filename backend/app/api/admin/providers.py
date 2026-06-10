"""统一供应商管理 API — 供应商 + Key 池融合"""
import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_admin
from app.algorithm.model_service import model_service
from app.algorithm.crypto import encrypt_key
from app.algorithm.providers_registry import get_model_id
from pydantic import BaseModel
from typing import Optional, Union

router = APIRouter(prefix="/providers", tags=["providers"])


# 模型条目：兼容旧格式字符串和新格式对象
ModelEntry = Union[str, dict]


class AddProviderInput(BaseModel):
    provider_id: str
    name: str
    protocol: str = "openai"
    api_host: str
    api_key: str = ""
    api_model: str = ""
    models: list[ModelEntry] = []
    max_rpm: int = 60


class UpdateProviderInput(BaseModel):
    name: Optional[str] = None
    api_host: Optional[str] = None
    api_key: Optional[str] = None
    api_model: Optional[str] = None
    models: Optional[list[ModelEntry]] = None
    is_enabled: Optional[bool] = None
    max_rpm: Optional[int] = None


@router.get("/builtin")
def list_builtin_providers(user: dict = Depends(require_admin)):
    return {"data": model_service.list_builtin(), "message": "success"}


@router.get("")
def list_providers(user: dict = Depends(require_admin)):
    return {"data": model_service.list_all(), "message": "success"}


@router.post("")
def add_provider(body: AddProviderInput, user: dict = Depends(require_admin)):
    existing = model_service.get(body.provider_id)
    if existing:
        raise HTTPException(status_code=400, detail="供应商已存在")
    provider = model_service.add(body.model_dump())
    return {"data": provider, "message": "供应商已添加"}


@router.put("/{provider_id}")
def update_provider(provider_id: str, body: UpdateProviderInput, user: dict = Depends(require_admin)):
    data = {k: v for k, v in body.model_dump().items() if v is not None}
    result = model_service.update(provider_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return {"data": result, "message": "更新成功"}


@router.delete("/{provider_id}")
def delete_provider(provider_id: str, user: dict = Depends(require_admin)):
    model_service.delete(provider_id)
    return {"message": "删除成功"}


@router.put("/{provider_id}/toggle")
def toggle_provider(provider_id: str, user: dict = Depends(require_admin)):
    result = model_service.toggle(provider_id)
    if not result:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return {"data": result, "message": "状态已切换"}


class CheckConnectionInput(BaseModel):
    model: Optional[str] = None

@router.post("/{provider_id}/check")
async def check_connection(provider_id: str, body: CheckConnectionInput = CheckConnectionInput(), user: dict = Depends(require_admin)):
    result = await model_service.check_connection(provider_id, body.model)
    return {"data": result, "message": result.get("status", "unknown")}


class DetectModelsInput(BaseModel):
    api_key: Optional[str] = None


@router.post("/{provider_id}/detect-models")
async def detect_models(provider_id: str, body: DetectModelsInput = DetectModelsInput(), user: dict = Depends(require_admin)):
    """从供应商 API 获取可用模型列表"""
    result = await model_service.detect_models(provider_id, body.api_key)
    return {"data": result, "message": "success"}


class ReconcileApplyInput(BaseModel):
    to_add: list[str] = []
    to_remove: list[str] = []


@router.post("/{provider_id}/models/reconcile")
async def reconcile_models(provider_id: str, user: dict = Depends(require_admin)):
    """比较 API 发现模型 vs 已存储模型，返回差异"""
    detected = await model_service.detect_models(provider_id)
    result = model_service.reconcile_models(provider_id, detected.get("models", []))
    if result is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return {"data": result, "message": "success"}


@router.post("/{provider_id}/models/reconcile-apply")
def reconcile_apply(provider_id: str, body: ReconcileApplyInput, user: dict = Depends(require_admin)):
    """应用 reconcile diff: 添加/删除模型"""
    result = model_service.reconcile_apply(provider_id, body.to_add, body.to_remove)
    if result is None:
        raise HTTPException(status_code=404, detail="供应商不存在")
    return {"data": result, "message": "模型列表已同步"}


class BatchCheckInput(BaseModel):
    models: list[str]

@router.post("/{provider_id}/models/check")
async def batch_check_models(provider_id: str, body: BatchCheckInput, user: dict = Depends(require_admin)):
    """批量检查多个模型的连通性。"""
    results = await model_service.batch_check_models(provider_id, body.models)
    return {"data": results, "message": "success"}


@router.get("/{provider_id}/models")
def list_provider_models(provider_id: str, user: dict = Depends(require_admin)):
    """获取供应商的模型列表（从 models 表）。"""
    from app.algorithm.models_crud import ModelsCrudService
    crud = ModelsCrudService()
    models = crud.list_by_provider(provider_id)
    return {"data": models, "message": "success"}


@router.put("/{provider_id}/models/{model_id}")
def update_provider_model(
    provider_id: str, model_id: str,
    body: dict, user: dict = Depends(require_admin),
):
    """更新单个模型的配置。"""
    from app.algorithm.models_crud import ModelsCrudService
    crud = ModelsCrudService()
    result = crud.update(provider_id, model_id, body)
    if not result:
        raise HTTPException(status_code=404, detail="模型不存在")
    return {"data": result, "message": "更新成功"}


@router.delete("/{provider_id}/models/{model_id}")
def delete_provider_model(
    provider_id: str, model_id: str,
    body: dict, user: dict = Depends(require_admin),
):
    """删除单个模型。"""
    from app.algorithm.models_crud import ModelsCrudService
    crud = ModelsCrudService()
    crud.delete(provider_id, model_id)
    # Also remove from JSON column
    from app.database import get_db
    db = get_db()
    row = db.execute("SELECT models FROM model_providers WHERE provider_id=?", (provider_id,)).fetchone()
    if row:
        stored = row["models"] if isinstance(row["models"], list) else (json.loads(row["models"]) if row["models"] else [])
        filtered = [m for m in stored if get_model_id(m) != model_id]
        db.execute("UPDATE model_providers SET models=? WHERE provider_id=?", (json.dumps(filtered), provider_id))
        db.commit()
    db.close()
    return {"message": "模型已删除"}
