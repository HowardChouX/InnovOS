"""统一供应商管理 API — 供应商 + Key 全 CRUD（Key 由数据库 AES-256-GCM 加密存储）"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.algorithm.model_service import model_service
from app.algorithm.providers_registry import get_model_id
from app.auth import require_admin

router = APIRouter(prefix="/providers", tags=["providers"])


# ── ApiKeyService 工厂 ──


def _get_api_key_service():
    """运行时工厂:从 db + cipher 构造 ApiKeyService。

    测试可通过 monkeypatch 替换。
    """
    from app.services.api_key_service import get_api_key_service

    return get_api_key_service()


# 模型条目：兼容旧格式字符串和新格式对象
ModelEntry = str | dict


class AddProviderInput(BaseModel):
    provider_id: str
    name: str
    protocol: str = "openai"
    api_host: str
    # API Key 通过 /api/admin/providers/{provider_id}/keys 子路由单独管理,
    # 支持多 Key + 加密存储 + 公平轮询。
    api_model: str = ""
    models: list[ModelEntry] = []
    max_rpm: int = 60


class UpdateProviderInput(BaseModel):
    name: str | None = None
    api_host: str | None = None
    # API Key 通过子路由管理,不在此处更新
    api_model: str | None = None
    models: list[ModelEntry] | None = None
    is_enabled: bool | None = None
    max_rpm: int | None = None


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
    model: str | None = None


@router.post("/{provider_id}/check")
async def check_connection(
    provider_id: str, body: CheckConnectionInput = CheckConnectionInput(), user: dict = Depends(require_admin)
):
    result = await model_service.check_connection(provider_id, body.model)
    return {"data": result, "message": result.get("status", "unknown")}


@router.post("/{provider_id}/detect-models")
async def detect_models(provider_id: str, user: dict = Depends(require_admin)):
    """从供应商 API 获取可用模型列表（Key 通过 ApiKeyService 从数据库读取）"""
    result = await model_service.detect_models(provider_id)
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
    provider_id: str,
    model_id: str,
    body: dict,
    user: dict = Depends(require_admin),
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
    provider_id: str,
    model_id: str,
    body: dict,
    user: dict = Depends(require_admin),
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
        stored = (
            row["models"] if isinstance(row["models"], list) else (json.loads(row["models"]) if row["models"] else [])
        )
        filtered = [m for m in stored if get_model_id(m) != model_id]
        db.execute("UPDATE model_providers SET models=? WHERE provider_id=?", (json.dumps(filtered), provider_id))
        db.commit()
    db.close()
    return {"message": "模型已删除"}


# ═══════════════════════════════════════════════════════════════
#  API Key 管理子路由(挂载到 /{provider_id}/keys)
# ═══════════════════════════════════════════════════════════════


class CreateKeyInput(BaseModel):
    """创建 Key 请求体。plaintext 只在创建/替换时提交,永不返回。"""

    name: str
    apiKey: str
    priority: int = 100
    maxRpm: int | None = None


class UpdateKeyMetadataInput(BaseModel):
    name: str | None = None
    priority: int | None = None
    maxRpm: int | None = None
    isActive: bool | None = None


class ReplaceKeySecretInput(BaseModel):
    apiKey: str


def _current_user_id(user: dict) -> int:
    """从 require_admin 返回的 user dict 取 actor_id。"""
    return int(user.get("user_id") or user.get("id") or 0)


@router.post("/{provider_id}/keys")
def create_api_key(
    provider_id: str,
    body: CreateKeyInput,
    user: dict = Depends(require_admin),
):
    """新建一把供应商 API Key(密文存储)。"""
    if not body.apiKey.strip():
        raise HTTPException(status_code=422, detail="apiKey 不能为空")
    svc = _get_api_key_service()
    try:
        result = svc.create_key(
            provider_id=provider_id,
            name=body.name,
            plaintext=body.apiKey,
            priority=body.priority,
            max_rpm=body.maxRpm,
            actor_id=_current_user_id(user),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"data": result, "message": "Key 已添加"}


@router.get("/{provider_id}/keys")
def list_api_keys(provider_id: str, user: dict = Depends(require_admin)):
    """列出供应商所有 Key(掩码 + 短 fingerprint)。"""
    svc = _get_api_key_service()
    results = svc.list_keys(provider_id=provider_id)
    return {"data": results, "message": "success"}


@router.patch("/{provider_id}/keys/{key_id}")
def update_api_key(
    provider_id: str,
    key_id: int,
    body: UpdateKeyMetadataInput,
    user: dict = Depends(require_admin),
):
    """更新 Key 元数据(name / priority / maxRpm / isActive)。不改密文。"""
    svc = _get_api_key_service()
    result = svc.update_metadata(
        key_id=key_id,
        name=body.name,
        priority=body.priority,
        max_rpm=body.maxRpm,
        is_active=body.isActive,
        actor_id=_current_user_id(user),
    )
    if not result:
        raise HTTPException(status_code=404, detail="Key 不存在")
    return {"data": result, "message": "已更新"}


@router.put("/{provider_id}/keys/{key_id}/secret")
def replace_api_key_secret(
    provider_id: str,
    key_id: int,
    body: ReplaceKeySecretInput,
    user: dict = Depends(require_admin),
):
    """替换 Key 明文(密文 + nonce + fingerprint 全更新,清 cooldown)。"""
    if not body.apiKey.strip():
        raise HTTPException(status_code=422, detail="apiKey 不能为空")
    svc = _get_api_key_service()
    result = svc.replace_secret(
        key_id=key_id, plaintext=body.apiKey, actor_id=_current_user_id(user)
    )
    if not result:
        raise HTTPException(status_code=404, detail="Key 不存在")
    return {"data": result, "message": "Key 已替换"}


@router.post("/{provider_id}/keys/{key_id}/activate")
def activate_api_key(
    provider_id: str, key_id: int, user: dict = Depends(require_admin)
):
    svc = _get_api_key_service()
    result = svc.activate(key_id=key_id, actor_id=_current_user_id(user))
    if not result:
        raise HTTPException(status_code=404, detail="Key 不存在")
    return {"data": result, "message": "已启用"}


@router.post("/{provider_id}/keys/{key_id}/deactivate")
def deactivate_api_key(
    provider_id: str, key_id: int, user: dict = Depends(require_admin)
):
    svc = _get_api_key_service()
    result = svc.deactivate(key_id=key_id, actor_id=_current_user_id(user))
    if not result:
        raise HTTPException(status_code=404, detail="Key 不存在")
    return {"data": result, "message": "已停用"}


@router.delete("/{provider_id}/keys/{key_id}")
def delete_api_key(
    provider_id: str, key_id: int, user: dict = Depends(require_admin)
):
    """软删(is_active=false),保留审计。"""
    svc = _get_api_key_service()
    ok = svc.delete_key(key_id=key_id, actor_id=_current_user_id(user))
    if not ok:
        raise HTTPException(status_code=404, detail="Key 不存在")
    return {"message": "Key 已停用"}
