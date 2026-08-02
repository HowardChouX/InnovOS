"""视频生成 API — MiniMax 文生视频（异步任务）。

POST /api/video/generate   创建任务（立即返回 taskId，后台轮询推进）
GET  /api/video/tasks      当前用户任务列表
GET  /api/video/tasks/{id} 单任务详情
DELETE /api/video/tasks/{id} 删除本地任务记录
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.algorithm.clients.minimax_video import (
    MinimaxVideoError,
    minimax_video_adapter,
)
from app.auth import get_current_user
from app.services.api_key_service import get_api_key_service
from app.services.video_task_service import video_task_service

router = APIRouter(prefix="/api/video", tags=["video"])

MINIMAX_PROVIDER_ID = "minimax"

ALLOWED_RESOLUTIONS = {"768P", "2K"}
ALLOWED_RATIOS = {"21:9", "16:9", "4:3", "1:1", "3:4", "9:16"}


class GenerateInput(BaseModel):
    prompt: str = Field(min_length=1, max_length=7000)
    resolution: str = "768P"
    duration: int = Field(default=5, ge=4, le=15)
    ratio: str = "16:9"


def _lease_minimax_key() -> tuple[str | None, str | None]:
    """租用 minimax 密钥并读取 api_host。返回 (plaintext, api_host)。"""
    from app.database import db_session

    svc = get_api_key_service()
    lease = svc.lease_key(provider_id=MINIMAX_PROVIDER_ID)
    if not lease:
        return None, None
    with db_session() as db:
        row = db.execute(
            "SELECT api_host FROM model_providers WHERE provider_id = ?",
            (MINIMAX_PROVIDER_ID,),
        ).fetchone()
    api_host = row["api_host"] if row else "https://api.minimaxi.com"
    return lease.plaintext, api_host


@router.post("/generate")
async def generate(body: GenerateInput, user: dict = Depends(get_current_user)):
    if not body.prompt.strip():
        raise HTTPException(status_code=422, detail="prompt 不能为空")
    if body.resolution not in ALLOWED_RESOLUTIONS:
        raise HTTPException(status_code=422, detail=f"非法分辨率: {body.resolution}")
    if body.ratio not in ALLOWED_RATIOS:
        raise HTTPException(status_code=422, detail=f"非法宽高比: {body.ratio}")

    task = video_task_service.create(
        user["id"],
        prompt=body.prompt.strip(),
        resolution=body.resolution,
        duration=body.duration,
        ratio=body.ratio,
    )

    api_key, api_host = _lease_minimax_key()
    if not api_key:
        video_task_service.mark_failed(task["id"], "未配置 MiniMax 密钥")
        raise HTTPException(status_code=400, detail="未配置 MiniMax 密钥")

    try:
        remote_task_id = await minimax_video_adapter.create_task(
            api_key=api_key,
            api_host=api_host,
            prompt=body.prompt.strip(),
            resolution=body.resolution,
            duration=body.duration,
            ratio=body.ratio,
        )
        video_task_service.set_remote_task(task["id"], remote_task_id)
    except MinimaxVideoError as exc:
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
