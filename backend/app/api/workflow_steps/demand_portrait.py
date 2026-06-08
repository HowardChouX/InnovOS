"""需求画像 API — 需求列表、用户评分"""
from fastapi import APIRouter, Depends
from app.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/demand", tags=["demand-portrait"])


class DemandRatingInput(BaseModel):
    task_id: int
    ratings: list[dict]


@router.post("/{task_id}/analyze")
async def run_demand_portrait(task_id: int, user: dict = Depends(get_current_user)):
    """启动需求画像分析"""
    return {"task_id": task_id, "status": "started", "message": "需求画像分析已启动"}


@router.get("/{task_id}/results")
async def get_demand_results(task_id: int, user: dict = Depends(get_current_user)):
    """获取需求画像结果"""
    return {"task_id": task_id, "demands": [], "message": "success"}


@router.post("/{task_id}/rate")
async def rate_demands(task_id: int, body: DemandRatingInput, user: dict = Depends(get_current_user)):
    """提交需求评分"""
    return {"task_id": task_id, "message": "评分已保存"}
