"""Admin model-service catalog endpoints.

Only the catalog CRUD + health check + (pre-create) detect survive
this refactor. The multi-key sub-router, builtin/reconcile/model
endpoints are removed.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.algorithm.model_service import model_service
from app.auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/providers", tags=["admin-providers"])


class AddProviderInput(BaseModel):
    provider_id: str
    name: str
    notes: str = ""
    api_host: str
    api_key: str
    api_model: str = ""
    protocol: str = "openai"


class UpdateProviderInput(BaseModel):
    name: str | None = None
    notes: str | None = None
    api_host: str | None = None
    api_key: str | None = None
    api_model: str | None = None
    is_enabled: bool | None = None
    protocol: str | None = None


class DetectInput(BaseModel):
    api_host: str
    api_key: str


class CheckConnectionInput(BaseModel):
    model: str | None = None


@router.get("")
def list_providers(user: dict = Depends(require_admin)) -> dict:
    return {"data": model_service.list_all(), "message": "success"}


@router.post("")
def add_provider(body: AddProviderInput, user: dict = Depends(require_admin)) -> dict:
    if model_service.get(body.provider_id):
        raise HTTPException(status_code=400, detail="供应商已存在")
    result = model_service.upsert(
        provider_id=body.provider_id,
        name=body.name,
        notes=body.notes,
        api_host=body.api_host,
        api_key_plaintext=body.api_key,
        api_model=body.api_model,
        protocol=body.protocol,
    )
    return {"data": result, "message": "供应商已添加"}


@router.put("/{provider_id}")
def update_provider(
    provider_id: str,
    body: UpdateProviderInput,
    user: dict = Depends(require_admin),
) -> dict:
    update_kwargs: dict = {}
    if body.name is not None:
        update_kwargs["name"] = body.name
    if body.notes is not None:
        update_kwargs["notes"] = body.notes
    if body.api_host is not None:
        update_kwargs["api_host"] = body.api_host
    if body.api_model is not None:
        update_kwargs["api_model"] = body.api_model
    if body.is_enabled is not None:
        update_kwargs["is_enabled"] = body.is_enabled
    if body.protocol is not None:
        update_kwargs["protocol"] = body.protocol

    current = model_service.get(provider_id)
    if current is None:
        raise HTTPException(status_code=404, detail="供应商不存在")

    if body.api_key:
        model_service.upsert(
            provider_id=provider_id,
            name=update_kwargs.get("name", current["name"]),
            notes=update_kwargs.get("notes", current["notes"]),
            api_host=update_kwargs.get("api_host", current["apiHost"]),
            api_key_plaintext=body.api_key,
            api_model=update_kwargs.get("api_model", current["apiModel"]),
            protocol=update_kwargs.get("protocol", current["protocol"]),
        )
    elif update_kwargs:
        model_service.update(provider_id, **update_kwargs)

    return {"data": model_service.get(provider_id), "message": "更新成功"}


@router.delete("/{provider_id}")
def delete_provider(provider_id: str, user: dict = Depends(require_admin)) -> dict:
    model_service.delete(provider_id)
    return {"message": "删除成功"}


@router.post("/detect")
async def detect_models_pre_create(
    body: DetectInput, user: dict = Depends(require_admin)
) -> dict:
    """Pre-create detect: accept api_host + api_key, return upstream model list."""
    result = await model_service.detect_models(
        provider_id="__detect__",
        api_host=body.api_host,
        api_key=body.api_key,
    )
    return {"data": result, "message": "success"}


@router.post("/{provider_id}/detect-models")
async def detect_models(provider_id: str, user: dict = Depends(require_admin)) -> dict:
    result = await model_service.detect_models(provider_id=provider_id)
    return {"data": result, "message": "success"}


@router.post("/{provider_id}/check")
async def check_connection(
    provider_id: str,
    body: CheckConnectionInput = CheckConnectionInput(),
    user: dict = Depends(require_admin),
) -> dict:
    result = await model_service.check_connection(provider_id, body.model)
    return {"data": result, "message": result.get("status", "unknown")}
