"""视频生成 API — 多供应商协议驱动。

POST /api/video/options   获取当前用户已开通视频供应商的能力元数据
POST /api/video/generate  创建任务（立即返回 taskId，后台轮询推进）
GET  /api/video/tasks      当前用户任务列表
GET  /api/video/tasks/{id} 单任务详情
DELETE /api/video/tasks/{id} 删除本地任务记录
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.algorithm.clients.video_base import (
    VideoAdapterError,
    VideoProtocolError,
    VideoRegistry,
)
from app.auth import get_current_user
from app.database import db_session
from app.services.api_key_service import get_api_key_service
from app.services.video_task_service import video_task_service

router = APIRouter(prefix="/api/video", tags=["video"])


class GenerateInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=7000)
    resolution: str = "768P"
    duration: int = Field(default=5, ge=1, le=60)
    ratio: str = "16:9"


def _select_user_video_provider(user_id: int) -> dict | None:
    """查用户开通的视频供应商队列，返回第一个可用的 provider 行（含 protocol/api_host/api_model）。"""
    with db_session() as db:
        row = db.execute(
            """
            SELECT ums.provider_id, mp.protocol, mp.api_host, mp.api_model
            FROM user_model_services ums
            JOIN model_providers mp ON mp.provider_id = ums.provider_id
            WHERE ums.user_id = ? AND ums.capability = 'video' AND ums.is_enabled = TRUE
            ORDER BY ums.failover_order ASC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def _lease_key(provider_id: str) -> str | None:
    """租用指定 provider 的密钥明文。"""
    svc = get_api_key_service()
    lease = svc.lease_key(provider_id=provider_id)
    return lease.plaintext if lease else None


def _get_adapter(protocol: str):
    """从注册表取 adapter，未注册协议抛 400。"""
    try:
        return VideoRegistry.get(protocol)
    except VideoProtocolError:
        raise HTTPException(
            status_code=400, detail=f"不支持的视频协议: {protocol}"
        )


@router.get("/options")
async def get_options(user: dict = Depends(get_current_user)):
    provider = _select_user_video_provider(user["id"])
    if not provider:
        raise HTTPException(status_code=403, detail="未开通视频生成服务，请联系管理员")
    adapter = _get_adapter(provider["protocol"])
    capabilities = adapter.capabilities()
    model = provider["api_model"] or adapter.default_model
    return {
        "data": {
            "providerId": provider["provider_id"],
            "providerName": provider["provider_id"],
            "protocol": provider["protocol"],
            "model": model,
            "capabilities": capabilities,
        },
        "message": "success",
        "code": 200,
    }


@router.post("/generate")
async def generate(body: GenerateInput, user: dict = Depends(get_current_user)):
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="prompt 不能为空")

    provider = _select_user_video_provider(user["id"])
    if not provider:
        raise HTTPException(status_code=403, detail="未开通视频生成服务，请联系管理员")

    protocol = provider["protocol"]
    if not protocol.startswith("video_"):
        raise HTTPException(status_code=400, detail="该供应商不是视频模型服务，请联系管理员")

    adapter = _get_adapter(protocol)

    caps = adapter.capabilities()
    if body.resolution not in caps["resolutions"]:
        raise HTTPException(
            status_code=422,
            detail=f"非法分辨率: {body.resolution}，允许值: {', '.join(caps['resolutions'])}",
        )
    if body.ratio not in caps["ratios"]:
        raise HTTPException(
            status_code=422,
            detail=f"非法宽高比: {body.ratio}，允许值: {', '.join(caps['ratios'])}",
        )
    if body.duration < caps["duration"]["min"] or body.duration > caps["duration"]["max"]:
        raise HTTPException(
            status_code=422,
            detail=f"非法时长: {body.duration}，允许范围: {caps['duration']['min']}-{caps['duration']['max']}",
        )

    model = provider["api_model"] or adapter.default_model
    task = video_task_service.create(
        user["id"],
        prompt=body.prompt.strip(),
        resolution=body.resolution,
        duration=body.duration,
        ratio=body.ratio,
        provider_id=provider["provider_id"],
        model=model,
    )

    api_key = _lease_key(provider["provider_id"])
    if not api_key:
        video_task_service.mark_failed(task["id"], "该视频供应商未配置密钥")
        raise HTTPException(status_code=400, detail="该视频供应商未配置密钥")

    try:
        remote_task_id = await adapter.create_task(
            api_key=api_key,
            api_host=provider["api_host"],
            model=model,
            prompt=body.prompt.strip(),
            resolution=body.resolution,
            duration=body.duration,
            ratio=body.ratio,
        )
        video_task_service.set_remote_task(task["id"], remote_task_id)
    except VideoAdapterError as exc:
        video_task_service.mark_failed(task["id"], str(exc))
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        # 远端任务已创建但本地回写失败等意外：标记失败，避免遗留 pending 孤儿任务
        video_task_service.mark_failed(task["id"], f"创建视频任务失败: {exc}")
        raise HTTPException(status_code=500, detail="创建视频任务失败")

    return {"data": {"taskId": task["id"]}, "message": "success", "code": 200}


@router.get("/tasks")
def list_tasks(user: dict = Depends(get_current_user)):
    data = video_task_service.list_by_user(user["id"])
    return {"data": data, "message": "success", "code": 200}


@router.get("/tasks/{task_id}")
def get_task(task_id: str, user: dict = Depends(get_current_user)):
    task = video_task_service.get(task_id)
    if not task or task["userId"] != user["id"]:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"data": task, "message": "success", "code": 200}


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str, user: dict = Depends(get_current_user)):
    deleted = video_task_service.delete(task_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "deleted", "code": 200}
