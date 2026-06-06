import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from app.algorithm.zr_ipm import ZRIPMEngine

router = APIRouter(prefix="/api/modeling", tags=["modeling"])


def row_to_modeling(r):
    return {
        "id": str(r["id"]),
        "taskId": str(r["task_id"]),
        "problemElements": json.loads(r["problem_elements"]),
        "conflicts": json.loads(r["conflicts"]),
        "recommendedPrinciples": json.loads(r["recommended_principles"]),
        "innovationDirections": json.loads(r["innovation_directions"]),
        "modelStructure": json.loads(r["model_structure"]),
    }


@router.get("/{task_id}")
async def get_modeling(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT id FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    row = db.execute("SELECT * FROM problem_modelings WHERE task_id=?", (task_id,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="问题建模尚未生成，请先触发分析")

    return {"data": row_to_modeling(row), "message": "success", "code": 200}


@router.post("/{task_id}/generate")
async def generate_modeling(task_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    existing = db.execute("SELECT * FROM problem_modelings WHERE task_id=?", (task_id,)).fetchone()
    if existing:
        db.close()
        return {"data": row_to_modeling(existing), "message": "已有问题建模", "code": 200}

    engine = ZRIPMEngine()

    try:
        # AI分析问题
        analysis_result = await engine.analyze(task["description"])

        # 构建问题建模数据
        problem_elements = {
            "coreGoal": analysis_result.get("centerNode", {}).get("description", ""),
            "techObject": task["description"][:50],
            "constraints": [
                "成本约束",
                "性能约束",
                "安全约束"
            ],
            "potentialConflicts": analysis_result.get("satelliteNodes", []),
        }

        conflicts = []
        satellites = analysis_result.get("satelliteNodes", [])
        if len(satellites) >= 2:
            conflicts.append({
                "type": "技术矛盾",
                "description": f"{satellites[0].get('label', '')} 与 {satellites[1].get('label', '')} 之间的冲突",
                "parameters": [
                    {"name": satellites[0].get('label', ''), "direction": "提高"},
                    {"name": satellites[1].get('label', ''), "direction": "降低"}
                ],
                "severity": "高"
            })

        if len(satellites) >= 3:
            conflicts.append({
                "type": "物理矛盾",
                "description": f"{satellites[2].get('label', '')} 需要同时满足相反要求",
                "parameters": [
                    {"name": satellites[2].get('label', ''), "requirement": "大"},
                    {"name": satellites[2].get('label', ''), "requirement": "小"}
                ],
                "severity": "中"
            })

        recommended_principles = analysis_result.get("principles", [])

        innovation_directions = [
            {
                "direction": "结构优化",
                "description": f"优化{satellites[0].get('label', '系统')}的结构设计",
                "confidence": 85
            },
            {
                "direction": "材料创新",
                "description": f"采用新材料改善{satellites[1].get('label', '性能')}",
                "confidence": 78
            },
            {
                "direction": "工艺改进",
                "description": "改进制造工艺以消除冲突",
                "confidence": 72
            }
        ]

        model_structure = {
            "problemType": "技术矛盾" if len(satellites) >= 2 else "单一问题",
            "complexity": "中等" if len(satellites) <= 3 else "复杂",
            "keyFactors": [s.get("label", "") for s in satellites[:3]],
            "rootCause": analysis_result.get("centerNode", {}).get("description", ""),
            "solutionSpace": "多方案可行",
        }

        db.execute(
            """INSERT INTO problem_modelings 
               (task_id, problem_elements, conflicts, recommended_principles, innovation_directions, model_structure)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                task_id,
                json.dumps(problem_elements, ensure_ascii=False),
                json.dumps(conflicts, ensure_ascii=False),
                json.dumps(recommended_principles, ensure_ascii=False),
                json.dumps(innovation_directions, ensure_ascii=False),
                json.dumps(model_structure, ensure_ascii=False),
            )
        )
        db.commit()

        row = db.execute("SELECT * FROM problem_modelings WHERE task_id=?", (task_id,)).fetchone()
        db.close()

        return {"data": row_to_modeling(row), "message": "问题建模生成成功", "code": 200}

    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=f"问题建模生成失败: {str(e)}")
