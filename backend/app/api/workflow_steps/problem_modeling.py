"""问题建模 API — 功能分析、因果链、矛盾、裁剪、进化趋势"""
from fastapi import APIRouter, Depends
from app.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/modeling", tags=["problem-modeling"])


class InnovationRatingInput(BaseModel):
    task_id: int
    ratings: list[dict]


@router.post("/{task_id}/analyze")
async def run_problem_modeling(task_id: int, user: dict = Depends(get_current_user)):
    """启动问题建模分析"""
    return {"task_id": task_id, "status": "started", "message": "问题建模分析已启动"}


@router.get("/{task_id}/results")
async def get_modeling_results(task_id: int, user: dict = Depends(get_current_user)):
    """获取问题建模结果"""
    return {"task_id": task_id, "innovations": [], "message": "success"}


@router.post("/{task_id}/rate")
async def rate_innovations(task_id: int, body: InnovationRatingInput, user: dict = Depends(get_current_user)):
    """提交创新方向评分"""
    return {"task_id": task_id, "message": "评分已保存"}
