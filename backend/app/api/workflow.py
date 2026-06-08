import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from app.utils import utc_iso
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

WORKFLOW_AGENTS = [
    {"agent_id": "agent1", "agent_type": "problem_analysis", "agent_label": "需求洞察Agent", "description": "理解用户需求，提取关键要素"},
    {"agent_id": "agent2", "agent_type": "patent_search", "agent_label": "问题建模Agent", "description": "构建问题模型，识别核心冲突"},
    {"agent_id": "agent5", "agent_type": "patent_search", "agent_label": "专利分析Agent", "description": "检索相关专利，分析技术方案"},
    {"agent_id": "agent3", "agent_type": "solution_gen", "agent_label": "方案生成Agent", "description": "生成创新方案，整合多源知识"},
    {"agent_id": "agent4", "agent_type": "evaluation", "agent_label": "方案评估Agent", "description": "评估方案可行性与创新性"},
    {"agent_id": "agent6", "agent_type": "evaluation", "agent_label": "成果转化Agent", "description": "输出结构化成果，支持转化"},
]


class UpdateStepInput(BaseModel):
    agent_id: str
    status: str
    description: Optional[str] = None
    duration: Optional[str] = None
    output: Optional[str] = None


@router.get("/{task_id}")
def get_workflow(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")

    row = db.execute("SELECT * FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="Workflow not yet started. Trigger analysis first.")

    steps = json.loads(row["steps"])
    # 将 snake_case 字段转换为 camelCase
    converted_steps = []
    for step in steps:
        converted_steps.append({
            "agentId": step.get("agent_id"),
            "agentType": step.get("agent_type"),
            "agentLabel": step.get("agent_label"),
            "status": step.get("status"),
            "description": step.get("description"),
            "startedAt": step.get("started_at"),
            "completedAt": step.get("completed_at"),
            "duration": step.get("duration"),
            "output": step.get("output"),
        })

    return {
        "data": {
            "id": str(row["id"]), "taskId": str(row["task_id"]),
            "status": row["status"],
            "steps": converted_steps,
            "createdAt": utc_iso(row["created_at"]),
        },
        "message": "success", "code": 200,
    }


@router.post("/{task_id}")
def create_workflow(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")

    existing = db.execute("SELECT id FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if existing:
        db.close()
        raise HTTPException(status_code=400, detail="Workflow already exists")

    steps = []
    for agent in WORKFLOW_AGENTS:
        steps.append({
            **agent,
            "status": "pending",
            "started_at": None,
            "completed_at": None,
            "duration": None,
            "output": None,
        })

    cursor = db.execute(
        "INSERT INTO workflows (task_id, status, steps) VALUES (?, ?, ?)",
        (task_id, "idle", json.dumps(steps)),
    )
    db.commit()

    row = db.execute("SELECT * FROM workflows WHERE id=?", (cursor.lastrowid,)).fetchone()
    db.close()

    return {
        "data": {
            "id": str(row["id"]), "taskId": str(row["task_id"]),
            "status": row["status"],
            "steps": json.loads(row["steps"]),
            "createdAt": utc_iso(row["created_at"]),
        },
        "message": "Workflow created",
        "code": 200,
    }


@router.put("/{task_id}/step")
def update_workflow_step(task_id: int, body: UpdateStepInput, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="Task not found")

    row = db.execute("SELECT * FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="Workflow not found")

    steps = json.loads(row["steps"])
    from datetime import datetime
    now = datetime.now().isoformat()

    step_found = False
    for step in steps:
        if step["agent_id"] == body.agent_id:
            step["status"] = body.status
            if body.status == "running" and not step.get("started_at"):
                step["started_at"] = now
            elif body.status in ("completed", "failed"):
                step["completed_at"] = now
                if step.get("started_at"):
                    start = datetime.fromisoformat(step["started_at"])
                    end = datetime.fromisoformat(now)
                    elapsed = (end - start).total_seconds()
                    step["duration"] = f"{elapsed:.1f}s"
            if body.description:
                step["description"] = body.description
            if body.duration:
                step["duration"] = body.duration
            if body.output:
                step["output"] = body.output
            step_found = True
            break

    if not step_found:
        db.close()
        raise HTTPException(status_code=400, detail=f"Unknown agent_id: {body.agent_id}")

    has_running = any(s["status"] == "running" for s in steps)
    all_completed = all(s["status"] in ("completed", "failed") for s in steps)
    any_failed = any(s["status"] == "failed" for s in steps)

    if any_failed:
        workflow_status = "failed"
    elif all_completed:
        workflow_status = "completed"
    elif has_running:
        workflow_status = "running"
    else:
        workflow_status = "idle"

    db.execute(
        "UPDATE workflows SET status=?, steps=? WHERE task_id=?",
        (workflow_status, json.dumps(steps), task_id),
    )
    db.commit()
    db.close()

    return {
        "data": {
            "status": workflow_status,
            "steps": steps,
        },
        "message": "Step updated",
        "code": 200,
    }
