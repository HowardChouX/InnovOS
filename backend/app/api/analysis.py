import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from app.algorithm.zr_ipm import ZRIPMEngine

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

WORKFLOW_AGENTS = [
    {"agent_id": "agent1", "agent_type": "problem_analysis", "agent_label": "需求洞察Agent", "description": "理解用户需求，提取关键要素"},
    {"agent_id": "agent2", "agent_type": "patent_search", "agent_label": "问题建模Agent", "description": "构建问题模型，识别核心冲突"},
    {"agent_id": "agent5", "agent_type": "patent_search", "agent_label": "专利分析Agent", "description": "检索相关专利，分析技术方案"},
    {"agent_id": "agent3", "agent_type": "solution_gen", "agent_label": "方案生成Agent", "description": "生成创新方案，整合多源知识"},
    {"agent_id": "agent4", "agent_type": "evaluation", "agent_label": "方案评估Agent", "description": "评估方案可行性与创新性"},
    {"agent_id": "agent6", "agent_type": "evaluation", "agent_label": "成果转化Agent", "description": "输出结构化成果，支持转化"},
]


def create_workflow(db, task_id: int):
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
    return cursor.lastrowid


def update_workflow_step(db, task_id: int, agent_id: str, status: str, description: str = None, duration: str = None, output: str = None):
    from datetime import datetime
    now = datetime.now().isoformat()

    row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        return

    steps = json.loads(row["steps"])
    for step in steps:
        if step["agent_id"] == agent_id:
            step["status"] = status
            if status == "running" and not step.get("started_at"):
                step["started_at"] = now
            elif status in ("completed", "failed"):
                step["completed_at"] = now
                if step.get("started_at"):
                    start = datetime.fromisoformat(step["started_at"])
                    end = datetime.fromisoformat(now)
                    elapsed = (end - start).total_seconds()
                    step["duration"] = f"{elapsed:.1f}s"
            if description:
                step["description"] = description
            if duration:
                step["duration"] = duration
            if output:
                step["output"] = output
            break

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
    db = get_db()

    task = db.execute(
        "SELECT * FROM tasks WHERE id=? AND user_id=?",
        (task_id, user["id"])
    ).fetchone()

    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

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

    db.execute(
        "UPDATE tasks SET status='analyzing', updated_at=datetime('now') WHERE id=?",
        (task_id,)
    )
    db.commit()

    existing_workflow = db.execute("SELECT id FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not existing_workflow:
        create_workflow(db, task_id)

    engine = ZRIPMEngine()

    try:
        # Step 1: 需求洞察 - AI分析问题
        update_workflow_step(db, task_id, "agent1", "running")
        db.commit()

        analysis_result = await engine.analyze(task["description"])

        update_workflow_step(db, task_id, "agent1", "completed",
                           description="理解用户需求，提取关键要素",
                           output=json.dumps(analysis_result, ensure_ascii=False))
        db.commit()

        # Step 2: 问题建模 - 基于分析结果构建模型
        update_workflow_step(db, task_id, "agent2", "running")
        db.commit()

        conflict_graph = engine._build_conflict_graph({
            "centerConflict": analysis_result.get("centerNode", {}).get("description", ""),
            "satellites": [
                {"label": s["label"], "sublabel": s.get("sublabel", ""), "description": s["description"]}
                for s in analysis_result.get("satelliteNodes", [])
            ],
            "principles": analysis_result.get("principles", []),
        })

        update_workflow_step(db, task_id, "agent2", "completed",
                           description="构建问题模型，识别核心冲突",
                           output=json.dumps(conflict_graph, ensure_ascii=False))
        db.commit()

        # Step 3: 专利分析 - 检索相关专利
        update_workflow_step(db, task_id, "agent5", "running")
        db.commit()

        patent_keywords = analysis_result.get("patentKeywords",
            [task["description"][:20]])

        db_patents = db.execute(
            "SELECT * FROM patents WHERE title LIKE ? OR abstract LIKE ? LIMIT 5",
            (f"%{patent_keywords[0]}%", f"%{patent_keywords[0]}%")
        ).fetchall() if patent_keywords else []

        patent_info = []
        for p in db_patents:
            patent_info.append({
                "title": p["title"],
                "abstract": p["abstract"],
                "relevance": p["relevance_score"],
            })

        update_workflow_step(db, task_id, "agent5", "completed",
                           description=f"检索到 {len(patent_info)} 条相关专利",
                           output=json.dumps(patent_info, ensure_ascii=False))
        db.commit()

        # Step 4: 方案生成 - AI生成解决方案
        update_workflow_step(db, task_id, "agent3", "running")
        db.commit()

        solutions = await engine.generate_solutions(task["description"])

        for sol in solutions:
            db.execute(
                """INSERT INTO solutions (task_id, title, description, principles, confidence_score, patent_references, rating)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    task_id,
                    sol.get("title", ""),
                    sol.get("description", ""),
                    json.dumps(sol.get("principles", [])),
                    sol.get("confidenceScore", 0),
                    json.dumps(sol.get("patentReferences", [])),
                    0,
                )
            )
        db.commit()

        update_workflow_step(db, task_id, "agent3", "completed",
                           description=f"生成 {len(solutions)} 个创新方案",
                           output=json.dumps(solutions, ensure_ascii=False))
        db.commit()

        # Step 5: 方案评估 - AI评估方案
        update_workflow_step(db, task_id, "agent4", "running")
        db.commit()

        evaluations = []
        for sol in solutions:
            eval_result = await engine.evaluate(sol.get("description", ""))
            evaluations.append({
                "solution_title": sol.get("title", ""),
                "evaluation": eval_result,
            })

            if eval_result and "scores" in eval_result:
                scores = eval_result["scores"]
                for dim, score_data in scores.items():
                    if isinstance(score_data, dict):
                        score_val = score_data.get("score", 0)
                    else:
                        score_val = score_data
                    db.execute(
                        """INSERT INTO evaluations (solution_id, user_id, dimension, score, details, status)
                           VALUES (?, ?, ?, ?, ?, ?)""",
                        (0, user["id"], dim, score_val, json.dumps(eval_result), "completed")
                    )
        db.commit()

        update_workflow_step(db, task_id, "agent4", "completed",
                           description=f"评估 {len(evaluations)} 个方案",
                           output=json.dumps(evaluations, ensure_ascii=False))
        db.commit()

        # Step 6: 成果转化 - 保存分析结果
        update_workflow_step(db, task_id, "agent6", "running")
        db.commit()

        db.execute(
            """INSERT INTO analyses (task_id, center_node, satellite_nodes, edges, principles)
               VALUES (?, ?, ?, ?, ?)""",
            (
                task_id,
                json.dumps(conflict_graph["centerNode"]),
                json.dumps(conflict_graph["satelliteNodes"]),
                json.dumps(conflict_graph["edges"]),
                json.dumps(conflict_graph["principles"]),
            )
        )

        update_workflow_step(db, task_id, "agent6", "completed",
                           description="输出结构化成果，支持转化")
        db.commit()

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
                "centerNode": conflict_graph["centerNode"],
                "satelliteNodes": conflict_graph["satelliteNodes"],
                "edges": conflict_graph["edges"],
                "principles": conflict_graph["principles"],
            },
            "message": "分析完成",
            "code": 200,
        }

    except Exception as e:
        db.execute(
            "UPDATE tasks SET status='failed', updated_at=datetime('now') WHERE id=?",
            (task_id,)
        )
        db.commit()

        row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
        if row:
            steps = json.loads(row["steps"])
            for step in steps:
                if step["status"] == "running":
                    update_workflow_step(db, task_id, step["agent_id"], "failed",
                                       description=f"执行失败: {str(e)}")
                    break
        db.commit()

        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(e)}")

    finally:
        db.close()
