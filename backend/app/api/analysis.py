import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from app.algorithm.zr_ipm import ZRIPMEngine

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/{task_id}")
def get_analysis(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")

    row = db.execute("SELECT * FROM analyses WHERE task_id=?", (task_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Analysis not yet generated. Trigger analysis first.")

    return {
        "data": {
            "id": str(row["id"]),
            "taskId": str(row["task_id"]),
            "centerNode": json.loads(row["center_node"]),
            "satelliteNodes": json.loads(row["satellite_nodes"]),
            "edges": json.loads(row["edges"]),
            "principles": json.loads(row["principles"]),
        },
        "message": "success", "code": 200,
    }


@router.post("/{task_id}/trigger")
async def trigger_analysis(task_id: int, user: dict = Depends(get_current_user)):
    """触发AI分析"""
    db = get_db()

    task = db.execute(
        "SELECT * FROM tasks WHERE id=? AND user_id=?",
        (task_id, user["id"])
    ).fetchone()

    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    # 检查是否已有分析结果
    existing = db.execute(
        "SELECT * FROM analyses WHERE task_id=?",
        (task_id,)
    ).fetchone()

    if existing:
        db.close()
        return {
            "data": {
                "id": str(existing["id"]),
                "taskId": str(existing["task_id"]),
                "centerNode": json.loads(existing["center_node"]),
                "satelliteNodes": json.loads(existing["satellite_nodes"]),
                "edges": json.loads(existing["edges"]),
                "principles": json.loads(existing["principles"]),
            },
            "message": "已有分析结果",
            "code": 200,
        }

    # 更新任务状态为分析中
    db.execute(
        "UPDATE tasks SET status='analyzing', updated_at=datetime('now') WHERE id=?",
        (task_id,)
    )
    db.commit()

    try:
        # 调用AI分析
        engine = ZRIPMEngine()
        result = await engine.analyze(task["description"])

        # 保存分析结果
        db.execute(
            """INSERT INTO analyses (task_id, center_node, satellite_nodes, edges, principles)
               VALUES (?, ?, ?, ?, ?)""",
            (
                task_id,
                json.dumps(result["centerNode"]),
                json.dumps(result["satelliteNodes"]),
                json.dumps(result["edges"]),
                json.dumps(result["principles"]),
            )
        )

        # 更新任务状态
        db.execute(
            "UPDATE tasks SET status='completed', updated_at=datetime('now') WHERE id=?",
            (task_id,)
        )
        db.commit()

        return {
            "data": {
                "id": str(task_id),
                "taskId": str(task_id),
                "centerNode": result["centerNode"],
                "satelliteNodes": result["satelliteNodes"],
                "edges": result["edges"],
                "principles": result["principles"],
            },
            "message": "分析完成",
            "code": 200,
        }

    except Exception as e:
        # 分析失败，更新任务状态
        db.execute(
            "UPDATE tasks SET status='failed', updated_at=datetime('now') WHERE id=?",
            (task_id,)
        )
        db.commit()
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")

    finally:
        db.close()
