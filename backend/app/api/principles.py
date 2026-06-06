from fastapi import APIRouter, Depends, Query
from app.auth import get_current_user
from app.data.triz_constants import PRINCIPLE_NAMES, PRINCIPLE_DETAILS

router = APIRouter(prefix="/api/principles", tags=["principles"])


@router.get("")
def list_principles():
    """获取 40 发明原理列表"""
    principles = []
    for pid, name in PRINCIPLE_NAMES.items():
        detail = PRINCIPLE_DETAILS.get(pid, {})
        principles.append({
            "id": pid,
            "name": name,
            "definition": detail.get("definition", ""),
            "category": detail.get("category", ""),
            "examples": detail.get("examples", []),
        })
    return {"data": principles, "message": "success"}


@router.get("/{principle_id}")
def get_principle(principle_id: int):
    """获取单个原理详情"""
    if principle_id not in PRINCIPLE_DETAILS:
        return {"detail": "原理不存在"}
    detail = PRINCIPLE_DETAILS[principle_id]
    return {"data": {"id": principle_id, **detail}, "message": "success"}


@router.get("/recommend/by-task")
def recommend_by_task(task_id: int, user: dict = Depends(get_current_user)):
    """根据任务的分析结果推荐相关原理"""
    from app.database import get_db

    db = get_db()
    analysis = db.execute(
        "SELECT principles FROM analyses WHERE task_id=?", (task_id,)
    ).fetchone()
    db.close()

    if not analysis:
        return {"data": [], "message": "暂无分析数据"}

    import json
    principle_names = json.loads(analysis["principles"])

    recommended = []
    for pid, name in PRINCIPLE_NAMES.items():
        if name in principle_names or any(n in name for n in principle_names):
            detail = PRINCIPLE_DETAILS.get(pid, {})
            recommended.append({"id": pid, "name": name, **detail})

    if not recommended and principle_names:
        for pid, detail in PRINCIPLE_DETAILS.items():
            if any(n in detail.get("definition", "") for n in principle_names):
                recommended.append({"id": pid, "name": detail["name"], **detail})

    return {"data": recommended[:5], "message": "success"}
