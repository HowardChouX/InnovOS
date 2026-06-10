import json
import asyncio
import sys
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
from app.database import get_db
from app.algorithm.zr_ipm import ZRIPMEngine

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# 保持对后台任务的引用，防止被垃圾回收
_background_tasks = set()

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
        "INSERT INTO workflows (task_id, status, steps) VALUES (?, ?, ?) RETURNING id",
        (task_id, "idle", json.dumps(steps)),
    )
    db.commit()
    return cursor.fetchone()["id"]


def update_workflow_step(db, task_id: int, agent_id: str, status: str, description: str = None, duration: str = None, output: str = None):
    from datetime import datetime
    now = datetime.now().isoformat()

    row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        print(f"[DEBUG] Workflow not found for task_id={task_id}", flush=True)
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
            print(f"[DEBUG] Updated step {agent_id} to status={status} for task_id={task_id}", flush=True)
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
    print(f"[DEBUG] Committed workflow status={workflow_status} for task_id={task_id}", flush=True)


async def _update_problem_modeling(db, task_id: int, task_description: str, analysis_result: dict, 
                                       step: str, extra_data: dict = None):
    """增量更新问题建模，与Agent步骤对齐"""
    try:
        existing = db.execute("SELECT * FROM problem_modelings WHERE task_id=?", (task_id,)).fetchone()
        
        if step == "agent1":
            # Agent1: 需求洞察 - 初始化问题要素
            satellites = analysis_result.get("satelliteNodes", [])
            problem_elements = {
                "coreGoal": analysis_result.get("centerNode", {}).get("description", ""),
                "techObject": task_description[:50],
                "constraints": ["成本约束", "性能约束", "安全约束"],
                "potentialConflicts": [
                    {"id": f"conflict_{i}", "label": s.get("label", ""), "description": s.get("description", "")}
                    for i, s in enumerate(satellites[:3])
                ],
            }
            
            if existing:
                db.execute(
                    "UPDATE problem_modelings SET problem_elements=? WHERE task_id=?",
                    (json.dumps(problem_elements, ensure_ascii=False), task_id)
                )
            else:
                db.execute(
                    """INSERT INTO problem_modelings 
                       (task_id, problem_elements, conflicts, recommended_principles, innovation_directions, model_structure)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        task_id,
                        json.dumps(problem_elements, ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        json.dumps([], ensure_ascii=False),
                        json.dumps({}, ensure_ascii=False),
                    )
                )
            db.commit()
            
        elif step == "agent2":
            # Agent2: 问题建模 - 更新冲突和模型结构
            satellites = analysis_result.get("satelliteNodes", [])
            
            conflicts = []
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

            model_structure = {
                "problemType": "技术矛盾" if len(satellites) >= 2 else "单一问题",
                "complexity": "中等" if len(satellites) <= 3 else "复杂",
                "keyFactors": [s.get("label", "") for s in satellites[:3]],
                "rootCause": analysis_result.get("centerNode", {}).get("description", ""),
                "solutionSpace": "多方案可行",
            }
            
            db.execute(
                """UPDATE problem_modelings SET conflicts=?, model_structure=? WHERE task_id=?""",
                (
                    json.dumps(conflicts, ensure_ascii=False),
                    json.dumps(model_structure, ensure_ascii=False),
                    task_id,
                )
            )
            db.commit()
            
        elif step == "agent3":
            # Agent3: 方案生成 - 更新创新方向
            satellites = analysis_result.get("satelliteNodes", [])
            solutions = extra_data.get("solutions", []) if extra_data else []
            
            innovation_directions = []
            if solutions:
                for i, sol in enumerate(solutions[:3]):
                    innovation_directions.append({
                        "direction": sol.get("title", f"方向{i+1}"),
                        "description": sol.get("description", "")[:100],
                        "confidence": sol.get("confidenceScore", 80)
                    })
            else:
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
            
            db.execute(
                "UPDATE problem_modelings SET innovation_directions=? WHERE task_id=?",
                (json.dumps(innovation_directions, ensure_ascii=False), task_id)
            )
            db.commit()
            
        elif step == "agent4":
            # Agent4: 方案评估 - 更新模型复杂度
            evaluations = extra_data.get("evaluations", []) if extra_data else []
            
            # 读取现有模型结构
            row = db.execute("SELECT model_structure FROM problem_modelings WHERE task_id=?", (task_id,)).fetchone()
            model_structure = json.loads(row["model_structure"]) if row and row["model_structure"] else {}
            
            avg_score = 0
            if evaluations:
                scores = []
                for ev in evaluations:
                    eval_data = ev.get("evaluation", {})
                    if "scores" in eval_data:
                        for dim, score_data in eval_data["scores"].items():
                            if isinstance(score_data, dict):
                                scores.append(score_data.get("score", 0))
                            else:
                                scores.append(score_data)
                avg_score = sum(scores) / len(scores) if scores else 0
            
            model_structure["solutionSpace"] = "多方案可行" if avg_score > 70 else "需优化"
            model_structure["avgScore"] = round(avg_score, 1)
            
            db.execute(
                "UPDATE problem_modelings SET model_structure=? WHERE task_id=?",
                (json.dumps(model_structure, ensure_ascii=False), task_id)
            )
            db.commit()
            
        elif step == "agent5":
            # Agent5: 专利分析 - 更新推荐原理
            patent_info = extra_data.get("patents", []) if extra_data else []
            principles = analysis_result.get("principles", [])
            
            # 合并专利相关原理
            recommended_principles = list(principles)
            for p in patent_info:
                title = p.get("title", "")
                if title and title not in recommended_principles:
                    recommended_principles.append(title)
            
            db.execute(
                "UPDATE problem_modelings SET recommended_principles=? WHERE task_id=?",
                (json.dumps(recommended_principles[:5], ensure_ascii=False), task_id)
            )
            db.commit()
            
    except Exception as e:
        print(f"Problem modeling update error for {step}: {e}")
        pass


async def _search_knowledge_bases(user_id: int, base_ids: list[str], query: str, top_k: int = 5) -> str:
    """搜索多个知识库，返回格式化的参考内容。"""
    from app.algorithm.knowledge.pipeline import KnowledgePipeline

    all_results = []
    for base_id in base_ids:
        try:
            pipeline = KnowledgePipeline(user_id, base_id)
            results = await pipeline.search(query, top_k=top_k, use_rerank=True)
            for r in results:
                all_results.append({
                    "base_id": base_id,
                    "item_id": r.get("item_id", ""),
                    "content": r.get("text", ""),
                    "score": r.get("score", 0),
                })
        except Exception as e:
            print(f"[WARN] KB search failed for base {base_id}: {e}", flush=True)

    if not all_results:
        return ""

    # 按分数降序排列，取前 10 条
    all_results.sort(key=lambda x: x["score"], reverse=True)
    all_results = all_results[:10]

    lines = ["【知识库参考内容】"]
    for i, r in enumerate(all_results, 1):
        score_pct = round(r["score"] * 100)
        lines.append(f"{i}. 来源: {r['item_id']} (相关度 {score_pct}%)")
        lines.append(f"   {r['content'][:300]}")
        lines.append("")

    return "\n".join(lines)


async def run_analysis_background(task_id: int, user_id: int, task_description: str, knowledge_base_ids: Optional[list[str]] = None):
    """后台执行分析任务"""
    print(f"[DEBUG] Background task started for task_id={task_id}", flush=True)
    db = get_db()
    engine = ZRIPMEngine()

    # 如果选择了知识库，先搜索并注入上下文
    kb_context = ""
    if knowledge_base_ids:
        print(f"[DEBUG] Searching knowledge bases: {knowledge_base_ids}", flush=True)
        update_workflow_step(db, task_id, "agent1", "running",
                           description="正在检索知识库...")
        kb_context = await _search_knowledge_bases(user_id, knowledge_base_ids, task_description)
        print(f"[DEBUG] KB context length: {len(kb_context)}", flush=True)

    # 构建带知识库上下文的任务描述
    enriched_description = task_description
    if kb_context:
        enriched_description = f"{kb_context}\n\n【用户问题】\n{task_description}"

    try:
        # Step 1: 需求洞察 - AI分析问题
        print(f"[DEBUG] Setting agent1 to running for task_id={task_id}", flush=True)
        update_workflow_step(db, task_id, "agent1", "running")
        print(f"[DEBUG] Agent1 set to running successfully", flush=True)
        
        analysis_result = await engine.analyze(enriched_description)
        
        # 增量更新：问题要素
        await _update_problem_modeling(db, task_id, task_description, analysis_result, "agent1")
        
        update_workflow_step(db, task_id, "agent1", "completed",
                           description="理解用户需求，提取关键要素",
                           output=json.dumps(analysis_result, ensure_ascii=False))

        # Step 2: 问题建模 - 基于分析结果构建模型
        update_workflow_step(db, task_id, "agent2", "running")
        
        conflict_graph = engine._build_conflict_graph({
            "centerConflict": analysis_result.get("centerNode", {}).get("description", ""),
            "satellites": [
                {"label": s["label"], "sublabel": s.get("sublabel", ""), "description": s["description"]}
                for s in analysis_result.get("satelliteNodes", [])
            ],
            "principles": analysis_result.get("principles", []),
        })
        
        # 增量更新：冲突分析 + 模型结构
        await _update_problem_modeling(db, task_id, task_description, analysis_result, "agent2")
        
        update_workflow_step(db, task_id, "agent2", "completed",
                           description="构建问题模型，识别核心冲突",
                           output=json.dumps(conflict_graph, ensure_ascii=False))

        # Step 3: 专利分析 - 检索相关专利
        update_workflow_step(db, task_id, "agent5", "running")
        
        # 获取AI提取的关键词，如果没有则使用任务描述
        patent_keywords = analysis_result.get("patentKeywords", [])
        if not patent_keywords:
            # 使用任务描述作为关键词（前50字）
            patent_keywords = [task_description[:50]]
        
        # 使用多关键词 OR 检索（最多3个关键词）
        search_keywords = patent_keywords[:3]
        
        # 构建 OR 条件
        or_conditions = []
        params = []
        for keyword in search_keywords:
            or_conditions.append("(title LIKE ? OR abstract LIKE ?)")
            params.extend([f"%{keyword}%", f"%{keyword}%"])
        
        where_clause = " OR ".join(or_conditions) if or_conditions else "1=1"
        
        sql = f"SELECT * FROM patents WHERE {where_clause} ORDER BY relevance_score DESC LIMIT 10"
        db_patents = db.execute(sql, params).fetchall()

        patent_info = []
        for p in db_patents:
            patent_info.append({
                "title": p["title"],
                "abstract": p["abstract"],
                "relevance": p["relevance_score"],
            })

        # 增量更新：推荐原理
        await _update_problem_modeling(db, task_id, task_description, analysis_result, "agent5",
                                       extra_data={"patents": patent_info})
        
        update_workflow_step(db, task_id, "agent5", "completed",
                           description=f"检索到 {len(patent_info)} 条相关专利",
                           output=json.dumps(patent_info, ensure_ascii=False))

        # Step 4: 方案生成 - AI生成解决方案
        update_workflow_step(db, task_id, "agent3", "running")
        
        solutions = await engine.generate_solutions(enriched_description)

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

        # 增量更新：创新方向
        await _update_problem_modeling(db, task_id, enriched_description, analysis_result, "agent3",
                                       extra_data={"solutions": solutions})
        
        update_workflow_step(db, task_id, "agent3", "completed",
                           description=f"生成 {len(solutions)} 个创新方案",
                           output=json.dumps(solutions, ensure_ascii=False))

        # Step 5: 方案评估 - AI评估方案
        update_workflow_step(db, task_id, "agent4", "running")

        # 获取该任务的所有solution_id
        solution_rows = db.execute(
            "SELECT id, title FROM solutions WHERE task_id=?",
            (task_id,)
        ).fetchall()
        solution_id_map = {row["title"]: row["id"] for row in solution_rows}

        evaluations = []
        for sol in solutions:
            eval_result = await engine.evaluate(sol.get("description", ""))
            evaluations.append({
                "solution_title": sol.get("title", ""),
                "evaluation": eval_result,
            })

            # 获取对应的solution_id
            sol_id = solution_id_map.get(sol.get("title", ""), 0)

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
                        (sol_id, user_id, dim, score_val, json.dumps(eval_result), "completed")
                    )

        # 增量更新：评估分数
        await _update_problem_modeling(db, task_id, task_description, analysis_result, "agent4",
                                       extra_data={"evaluations": evaluations})
        
        update_workflow_step(db, task_id, "agent4", "completed",
                           description=f"评估 {len(evaluations)} 个方案",
                           output=json.dumps(evaluations, ensure_ascii=False))

        # Step 6: 成果转化 - 保存分析结果
        update_workflow_step(db, task_id, "agent6", "running")

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

        # 更新任务状态
        db.execute(
            "UPDATE tasks SET status='completed', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
            (task_id,)
        )
        db.commit()

    except Exception as e:
        print(f"[ERROR] Background task failed for task_id={task_id}: {e}")
        db.execute(
            "UPDATE tasks SET status='failed', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
            (task_id,)
        )
        db.commit()

        try:
            row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
            if row:
                steps = json.loads(row["steps"])
                for step in steps:
                    if step["status"] == "running":
                        update_workflow_step(db, task_id, step["agent_id"], "failed",
                                           description=f"执行失败: {str(e)}")
                        break
        except:
            pass

    finally:
        db.close()


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


class TriggerAnalysisInput(BaseModel):
    knowledgeBaseIds: Optional[list[str]] = None


@router.post("/{task_id}/trigger")
async def trigger_analysis(task_id: int, body: Optional[TriggerAnalysisInput] = None, user: dict = Depends(get_current_user)):
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
        "UPDATE tasks SET status='analyzing', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
        (task_id,)
    )
    db.commit()

    existing_workflow = db.execute("SELECT id FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not existing_workflow:
        create_workflow(db, task_id)

    db.close()

    # 后台启动分析任务
    # 使用 BackgroundTasks 确保任务在响应发送后继续执行
    kb_ids = body.knowledgeBaseIds if body else None
    task = asyncio.create_task(run_analysis_background(task_id, user["id"], task["description"], kb_ids))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)

    return {
        "data": {
            "id": str(task_id),
            "taskId": str(task_id),
            "status": "analyzing",
        },
        "message": "分析已启动",
        "code": 200,
    }
