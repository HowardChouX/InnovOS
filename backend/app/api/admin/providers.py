"""统一供应商管理 API — 供应商 + Key 池融合"""
from fastapi import APIRouter, Depends, HTTPException
from app.auth import require_admin
from app.algorithm.model_service import model_service
from app.algorithm.crypto import encrypt_key
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/providers", tags=["providers"])


class AddProviderInput(BaseModel):
    provider_id: str
    name: str
    protocol: str = "openai"
    api_host: str
    api_key: str = ""
    api_model: str = ""
    models: list[str] = []
    priority: int = 0
    max_rpm: int = 60


class UpdateProviderInput(BaseModel):
    name: Optional[str] = None
    api_host: Optional[str] = None
    api_key: Optional[str] = None
    api_model: Optional[str] = None
    models: Optional[list[str]] = None
    is_enabled: Optional[bool] = None
    priority: Optional[int] = None
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
