import asyncio
import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.algorithm.analyzers.demand_portrait import DemandPortraitAnalyzer
from app.algorithm.base import parse_ai_json, strip_think_tags
from app.algorithm.zr_ipm import ZRIPMEngine
from app.auth import get_current_user
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analysis", tags=["analysis"])

# 保持对后台任务的引用，防止被垃圾回收
_background_tasks: set[asyncio.Task] = set()

# 并发锁：防止同一个 task_id 的多个后台任务同时执行
_running_workflows: set[int] = set()

# task_id → asyncio.Task 映射，用于取消运行中的任务
_task_map: dict[int, asyncio.Task] = {}


def _cleanup_task(task_id: int, task: asyncio.Task) -> None:
    """任务完成后的清理——从跟踪集合中移除，失败时更新状态"""
    _background_tasks.discard(task)
    _task_map.pop(task_id, None)

    # 如果任务失败（取消或异常），更新状态为 failed
    if task.cancelled():
        logger.warning(f"Task {task_id} was cancelled")
        _update_task_status(task_id, "failed")
    elif task.exception():
        logger.error(f"Task {task_id} failed: {task.exception()}")
        _update_task_status(task_id, "failed")


def _update_task_status(task_id: int, status: str) -> None:
    """更新任务状态（异步安全）"""
    try:
        db = get_db()
        db.execute(
            "UPDATE tasks SET status=?, updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
            (status, task_id),
        )
        db.commit()
        db.close()
        logger.info(f"Updated task {task_id} status to {status}")
    except Exception as e:
        logger.error(f"Failed to update task {task_id} status: {e}")

WORKFLOW_AGENTS = [
    {
        "agent_id": "agent1",
        "agent_type": "problem_analysis",
        "agent_label": "需求洞察Agent",
        "description": "理解用户需求，提取关键要素",
    },
    {
        "agent_id": "agent2",
        "agent_type": "patent_search",
        "agent_label": "问题建模Agent",
        "description": "构建问题模型，识别核心冲突",
    },
    {
        "agent_id": "agent5",
        "agent_type": "patent_search",
        "agent_label": "专利分析Agent",
        "description": "检索相关专利，分析技术方案",
    },
    {
        "agent_id": "agent3",
        "agent_type": "solution_gen",
        "agent_label": "方案生成Agent",
        "description": "生成创新方案，整合多源知识",
    },
    {
        "agent_id": "agent4",
        "agent_type": "evaluation",
        "agent_label": "方案评估Agent",
        "description": "评估方案可行性与创新性",
    },
    {
        "agent_id": "agent6",
        "agent_type": "evaluation",
        "agent_label": "成果转化Agent",
        "description": "输出结构化成果，支持转化",
    },
]


def create_workflow(db, task_id: int):
    steps = []
    for agent in WORKFLOW_AGENTS:
        steps.append(
            {
                **agent,
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "duration": None,
                "output": None,
            }
        )

    cursor = db.execute(
        "INSERT INTO workflows (task_id, status, steps) VALUES (?, ?, ?) RETURNING id",
        (task_id, "idle", json.dumps(steps)),
    )
    db.commit()
    return cursor.fetchone()["id"]


def update_workflow_step(
    db,
    task_id: int,
    agent_id: str,
    status: str,
    description: str | None = None,
    duration: str | None = None,
    output: str | None = None,
):
    from datetime import datetime

    now = datetime.now().isoformat()

    row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        logger.debug(f"Workflow not found for task_id={task_id}")
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
            logger.debug(f"Updated step {agent_id} to status={status} for task_id={task_id}")
            break

    has_running = any(s["status"] == "running" for s in steps)
    all_completed = all(s["status"] in ("completed", "failed") for s in steps)
    any_failed = any(s["status"] == "failed" for s in steps)
    has_pending = any(s["status"] == "pending" for s in steps)

    if any_failed:
        workflow_status = "failed"
    elif all_completed:
        workflow_status = "completed"
    elif has_running or has_pending:
        # 有正在运行的步骤，或有等待执行的步骤 → 工作流仍在进行中
        # awaiting_rating 仅在显式调用处设置（demand_portrait / problem_modeling / patent_search 完成后）
        workflow_status = "running"
    else:
        workflow_status = "idle"

    db.execute(
        "UPDATE workflows SET status=?, steps=? WHERE task_id=?",
        (workflow_status, json.dumps(steps), task_id),
    )
    db.commit()
    logger.debug(f"Committed workflow status={workflow_status} for task_id={task_id}")


async def _update_problem_modeling(
    db, task_id: int, task_description: str, analysis_result: dict, step: str, extra_data: dict | None = None
):
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
                    (json.dumps(problem_elements, ensure_ascii=False), task_id),
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
                    ),
                )
            db.commit()

        elif step == "agent2":
            # Agent2: 问题建模 - 更新冲突和模型结构
            satellites = analysis_result.get("satelliteNodes", [])

            conflicts = []
            if len(satellites) >= 2:
                conflicts.append(
                    {
                        "type": "技术矛盾",
                        "description": f"{satellites[0].get('label', '')} 与 {satellites[1].get('label', '')} 之间的冲突",
                        "parameters": [
                            {"name": satellites[0].get("label", ""), "direction": "提高"},
                            {"name": satellites[1].get("label", ""), "direction": "降低"},
                        ],
                        "severity": "高",
                    }
                )

            if len(satellites) >= 3:
                conflicts.append(
                    {
                        "type": "物理矛盾",
                        "description": f"{satellites[2].get('label', '')} 需要同时满足相反要求",
                        "parameters": [
                            {"name": satellites[2].get("label", ""), "requirement": "大"},
                            {"name": satellites[2].get("label", ""), "requirement": "小"},
                        ],
                        "severity": "中",
                    }
                )

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
                ),
            )
            db.commit()

        elif step == "agent3":
            # Agent3: 方案生成 - 更新创新方向
            satellites = analysis_result.get("satelliteNodes", [])
            solutions = extra_data.get("solutions", []) if extra_data else []

            innovation_directions = []
            if solutions:
                for i, sol in enumerate(solutions[:3]):
                    innovation_directions.append(
                        {
                            "direction": sol.get("title", f"方向{i + 1}"),
                            "description": sol.get("description", "")[:100],
                            "confidence": sol.get("confidenceScore", 80),
                        }
                    )
            else:
                innovation_directions = [
                    {
                        "direction": "结构优化",
                        "description": f"优化{satellites[0].get('label', '系统')}的结构设计",
                        "confidence": 85,
                    },
                    {
                        "direction": "材料创新",
                        "description": f"采用新材料改善{satellites[1].get('label', '性能')}",
                        "confidence": 78,
                    },
                    {"direction": "工艺改进", "description": "改进制造工艺以消除冲突", "confidence": 72},
                ]

            db.execute(
                "UPDATE problem_modelings SET innovation_directions=? WHERE task_id=?",
                (json.dumps(innovation_directions, ensure_ascii=False), task_id),
            )
            db.commit()

        elif step == "agent4":
            # Agent4: 方案评估 - 更新模型复杂度
            evaluations = extra_data.get("evaluations", []) if extra_data else []

            # 读取现有模型结构
            row = db.execute("SELECT model_structure FROM problem_modelings WHERE task_id=?", (task_id,)).fetchone()
            model_structure = json.loads(row["model_structure"]) if row and row["model_structure"] else {}

            avg_score: float = 0.0
            if evaluations:
                scores = []
                for ev in evaluations:
                    eval_data = ev.get("evaluation", {})
                    if "scores" in eval_data:
                        for _dim, score_data in eval_data["scores"].items():
                            if isinstance(score_data, dict):
                                scores.append(score_data.get("score", 0))
                            else:
                                scores.append(score_data)
                avg_score = sum(scores) / len(scores) if scores else 0

            model_structure["solutionSpace"] = "多方案可行" if avg_score > 70 else "需优化"
            model_structure["avgScore"] = round(avg_score, 1)

            db.execute(
                "UPDATE problem_modelings SET model_structure=? WHERE task_id=?",
                (json.dumps(model_structure, ensure_ascii=False), task_id),
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
                (json.dumps(recommended_principles[:5], ensure_ascii=False), task_id),
            )
            db.commit()

    except Exception as e:
        logger.error(f"Problem modeling update error for {step}: {e}")
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
                all_results.append(
                    {
                        "base_id": base_id,
                        "item_id": r.get("item_id", ""),
                        "content": r.get("text", ""),
                        "score": r.get("score", 0),
                    }
                )
        except Exception as e:
            logger.warning(f"KB search failed for base {base_id}: {e}")

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


def _create_ai_base(user_id: int):
    """创建使用 FailoverRouter 的 AI 包装器（替代旧 AIBase + key_provider 路径）。

    New (per-user) 路径:
      每次调用通过 chat_completion_sync() → FailoverRouter → user_model_services 队列
      → 逐个尝试供应商 → 失败自动降级 → 记录 model_call_log

    不再读取 system_settings / model_resolver（旧路径，现已废弃）。
    """
    from app.algorithm.ai_client import chat_completion_sync

    class FailoverAIWrapper:
        """与 AIBase 接口兼容的包装器，内部使用 FailoverRouter。"""

        def __init__(self, uid: int, purpose: str = "chat"):
            self.user_id = uid
            self.purpose = purpose
            self.enabled = True

        def call_ai(
            self,
            system_prompt: str,
            user_prompt: str,
            temperature: float = 0.3,
            max_tokens: int | None = None,
            logger_prefix: str = "",
            raw: bool = False,
            json_mode: bool = False,
        ) -> str | dict | None:
            messages: list[dict[str, str]] = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            try:
                result = chat_completion_sync(
                    user_id=self.user_id,
                    purpose=self.purpose,
                    messages=messages,
                )
            except Exception as e:
                logger.error("[%s] FailoverRouter 调用失败: %s", logger_prefix or "AI", e)
                return None

            content = (result.get("content") or "").strip()
            content = strip_think_tags(content)

            if not content:
                logger.warning("[%s] 空响应", logger_prefix or "AI")
                return None

            if raw:
                return content

            parsed = parse_ai_json(content)
            if json_mode and not isinstance(parsed, dict):
                logger.warning(
                    "[%s] 返回非 JSON 格式（%s）",
                    logger_prefix or "AI",
                    type(parsed).__name__,
                )
                return None

            return parsed

        async def call_ai_async(
            self,
            system_prompt: str,
            user_prompt: str,
            temperature: float = 0.3,
            max_tokens: int | None = None,
            logger_prefix: str = "",
            raw: bool = False,
            json_mode: bool = False,
        ) -> str | dict | None:
            import asyncio

            return await asyncio.to_thread(
                self.call_ai,
                system_prompt,
                user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                logger_prefix=logger_prefix,
                raw=raw,
                json_mode=json_mode,
            )

    return FailoverAIWrapper(uid=user_id)


async def run_demand_portrait(
    task_id: int, user_id: int, task_description: str, knowledge_base_ids: list[str] | None = None
):
    """只运行需求洞察步骤，等待用户评分"""
    logger.debug(f"Demand portrait started for task_id={task_id}")
    db = get_db()

    # 搜索知识库
    kb_context = ""
    if knowledge_base_ids:
        logger.debug(f"Searching knowledge bases: {knowledge_base_ids}")
        update_workflow_step(db, task_id, "agent1", "running", description="正在检索知识库...")
        kb_context = await _search_knowledge_bases(user_id, knowledge_base_ids, task_description)

    enriched = task_description
    if kb_context:
        enriched = f"{kb_context}\n\n【用户问题】\n{task_description}"

    try:
        update_workflow_step(db, task_id, "agent1", "running", description="正在进行需求分析...")

        ai_base = _create_ai_base(user_id)
        if not ai_base:
            raise RuntimeError("AI 模型未配置，请联系管理员开通 AI 功能")

        analyzer = DemandPortraitAnalyzer(ai_base)
        result = await analyzer.analyze(enriched)

        demands = result.get("demands", [])
        update_workflow_step(
            db,
            task_id,
            "agent1",
            "completed",
            description=f"识别 {len(demands)} 个需求",
            output=json.dumps(result, ensure_ascii=False),
        )

        # 设置 workflow 为等待评分状态
        db.execute(
            "UPDATE workflows SET status=? WHERE task_id=?",
            ("awaiting_rating", task_id),
        )
        # 更新任务状态为 pending（等待用户下一步操作）
        db.execute(
            "UPDATE tasks SET status='pending', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
            (task_id,),
        )
        db.commit()

        logger.debug(f"Demand portrait completed for task_id={task_id}, {len(demands)} demands")
        return result

    except Exception as e:
        logger.error(f"Demand portrait failed: {e}")
        update_workflow_step(db, task_id, "agent1", "failed", description=f"执行失败: {str(e)}")
        # 显式更新任务状态为 failed
        db.execute(
            "UPDATE tasks SET status='failed', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
            (task_id,),
        )
        db.commit()
        return None
    finally:
        db.close()


def _is_step_pending(db, task_id: int, agent_id: str) -> bool:
    """检查某个步骤是否为 pending 状态"""
    import json

    row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        return False
    steps = json.loads(row[0])
    step = next((s for s in steps if s["agent_id"] == agent_id), None)
    return step is not None and step["status"] == "pending"


async def run_analysis_background(
    task_id: int,
    user_id: int,
    task_description: str,
    knowledge_base_ids: list[str] | None = None,
    start_from: str = "agent1",
):
    """后台执行分析任务"""
    # 并发锁：防止同一个 task_id 的多个后台任务同时执行
    if task_id in _running_workflows:
        logger.warning(f"Workflow {task_id} already running, skipping duplicate")
        return
    _running_workflows.add(task_id)

    logger.debug(f"Background task started for task_id={task_id}, start_from={start_from}")
    db = get_db()

    # 崩溃恢复：将之前卡在 "running" 状态的步骤重置为 "pending"
    row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if row:
        steps = json.loads(row["steps"])
        recovered = False
        for step in steps:
            if step["status"] == "running" and step["agent_id"] != start_from:
                logger.warning(f"Resetting stuck step {step['agent_id']} from running to pending")
                step["status"] = "pending"
                step["started_at"] = None
                step["completed_at"] = None
                step["duration"] = None
                recovered = True
        if recovered:
            db.execute("UPDATE workflows SET steps=? WHERE task_id=?", (json.dumps(steps), task_id))
            db.commit()

    engine = ZRIPMEngine()

    # 构建带知识库上下文的任务描述（仅首次运行需要）
    enriched_description = task_description
    if start_from == "agent1" and knowledge_base_ids:
        logger.debug(f"Searching knowledge bases: {knowledge_base_ids}")
        update_workflow_step(db, task_id, "agent1", "running", description="正在检索知识库...")
        kb_context = await _search_knowledge_bases(user_id, knowledge_base_ids, task_description)
        if kb_context:
            enriched_description = f"{kb_context}\n\n【用户问题】\n{task_description}"

    try:
        # Step 1: 需求洞察（仅 first run，proceed 时跳过）
        if start_from == "agent1":
            logger.debug(f"Setting agent1 to running for task_id={task_id}")
            update_workflow_step(db, task_id, "agent1", "running")
            logger.debug("Agent1 set to running successfully")

            analysis_result = await engine.analyze(enriched_description)

            # 增量更新：问题要素
            await _update_problem_modeling(db, task_id, task_description, analysis_result, "agent1")

            update_workflow_step(
                db,
                task_id,
                "agent1",
                "completed",
                description="理解用户需求，提取关键要素",
                output=json.dumps(analysis_result, ensure_ascii=False),
            )
        else:
            # 从 proceed 恢复时，从 workflow 读取之前 agent1 的输出
            row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
            steps = json.loads(row["steps"]) if row else []
            agent1_step = next((s for s in steps if s["agent_id"] == "agent1"), None)
            analysis_result = {}
            if agent1_step and agent1_step.get("output"):
                try:
                    analysis_result = json.loads(agent1_step["output"])
                except (json.JSONDecodeError, TypeError):
                    analysis_result = {}

        # Step 2: 问题建模（如果已完成则跳过）
        if _is_step_pending(db, task_id, "agent2"):
            update_workflow_step(db, task_id, "agent2", "running")
            try:
                from app.algorithm.analyzers.problem_modeling import ProblemModelingAnalyzer

                ai_base = _create_ai_base(user_id)
                if ai_base:
                    pm_analyzer = ProblemModelingAnalyzer(ai_base)
                    # 读取 Step 1 的用户评分，传入作为分析参考
                    demand_results = None
                    if isinstance(analysis_result, dict):
                        demands = analysis_result.get("demands", [])
                        if demands:
                            demand_results = {
                                "demands": [
                                    {
                                        "description": d.get("description", ""),
                                        "category": d.get("category", ""),
                                        "rating": d.get("user_rating", None),
                                    }
                                    for d in demands
                                ]
                            }
                    pm_result = await pm_analyzer.analyze(enriched_description, demand_results=demand_results)
                    innovations = pm_result.get("innovations", [])

                    update_workflow_step(
                        db,
                        task_id,
                        "agent2",
                        "completed",
                        description=f"生成 {len(innovations)} 个创新方向",
                        output=json.dumps(pm_result, ensure_ascii=False),
                    )
                else:
                    raise RuntimeError("AI 模型未配置，请联系管理员开通 AI 功能")
            except Exception as e:
                logger.error(f"问题建模分析失败: {e}")
                update_workflow_step(db, task_id, "agent2", "failed", description=f"执行失败: {str(e)}")
                return

            # 来自 proceed 流程，暂停等评分
            if start_from != "agent1":
                db.execute("UPDATE workflows SET status=? WHERE task_id=?", ("awaiting_rating", task_id))
                db.execute(
                    "UPDATE tasks SET status='pending', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
                    (task_id,),
                )
                db.commit()
                return

        # Step 3: 专利分析 - 统一检索服务（PatentHub 主数据源 + 本地降级）
        if _is_step_pending(db, task_id, "agent5"):
            update_workflow_step(db, task_id, "agent5", "running")

            patent_info: list[dict] = []
            direction_patents: dict[str, list[str]] = {}
            try:
                # 从问题建模结果中获取创新方向
                innovations_with_ratings = []
                row_steps = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
                if row_steps:
                    all_steps = json.loads(row_steps["steps"])
                    agent2 = next((s for s in all_steps if s["agent_id"] == "agent2"), None)
                    if agent2 and agent2.get("output"):
                        try:
                            agent2_out = json.loads(agent2["output"])
                            innovations_with_ratings = agent2_out.get("innovations", [])
                        except (json.JSONDecodeError, TypeError):
                            pass

                # 使用统一专利检索服务
                from app.algorithm.patent_service import patent_search

                search_result = await patent_search(
                    innovations=innovations_with_ratings,
                    task_description=task_description,
                    max_results=50,
                )
                patent_info = search_result["patents"]
                direction_patents = search_result["direction_patents"]

                logger.info(
                    f"专利检索完成(source={search_result['source']}): "
                    f"找到 {search_result['total_found']} 条相关专利"
                )

            except Exception as e:
                logger.error(f"专利检索异常: {e}")

            update_workflow_step(
                db,
                task_id,
                "agent5",
                "completed",
                description=f"检索到 {len(patent_info)} 条相关专利",
                output=json.dumps(
                    {
                        "patents": patent_info,
                        "directionPatents": direction_patents,
                    },
                    ensure_ascii=False,
                ),
            )

            # 暂停等待用户评分，不允许直接继续
            db.execute("UPDATE workflows SET status=? WHERE task_id=?", ("awaiting_rating", task_id))
            db.execute(
                "UPDATE tasks SET status='pending', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
                (task_id,),
            )
            db.commit()

            logger.debug(f"Step 3 completed for task_id={task_id}, patent_info={len(patent_info)}")
            return

        # Step 4: 方案生成 - AI生成解决方案
        if _is_step_pending(db, task_id, "agent3"):
            update_workflow_step(db, task_id, "agent3", "running")

            # 读取创新方向和专利数据
            innovations = []
            patent_info = []
            direction_patents = {}
            patent_ratings = {}  # patent index -> rating score
            row_steps = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
            if row_steps:
                wf_steps_data = json.loads(row_steps["steps"])
                # 读取创新方向
                agent2_step = next((s for s in wf_steps_data if s["agent_id"] == "agent2"), None)
                if agent2_step and agent2_step.get("output"):
                    try:
                        agent2_out = json.loads(agent2_step["output"])
                        innovations = agent2_out.get("innovations", [])
                    except (json.JSONDecodeError, TypeError):
                        pass
                # 读取专利（含方向映射和用户评分）
                agent5_step = next((s for s in wf_steps_data if s["agent_id"] == "agent5"), None)
                if agent5_step and agent5_step.get("output"):
                    try:
                        agent5_out = json.loads(agent5_step["output"])
                        if isinstance(agent5_out, dict):
                            patent_info = agent5_out.get("patents", [])
                            direction_patents = agent5_out.get("directionPatents", {})
                            # 读取用户对专利的评分
                            ratings_list = agent5_out.get("ratings", [])
                            if ratings_list:
                                for r in ratings_list:
                                    idx = str(r.get("demandId", ""))
                                    score = r.get("score", 0)
                                    if idx.isdigit() and score > 0:
                                        patent_ratings[int(idx)] = score
                        else:
                            patent_info = agent5_out
                    except (json.JSONDecodeError, TypeError):
                        pass

            # 从系统设置读取相关度阈值，默认 0.3
            relevance_threshold = 0.3
            try:
                cfg_row = db.execute("SELECT value FROM system_settings WHERE key='threshold'").fetchone()
                if cfg_row and cfg_row["value"]:
                    relevance_threshold = float(cfg_row["value"])
            except Exception:
                pass

            # 过滤低相关度专利
            patent_info = [p for p in patent_info if p.get("relevance", 0) >= relevance_threshold]

            solutions = await engine.generate_solutions(
                enriched_description,
                patents=patent_info,
                innovations=innovations,
                direction_patents=direction_patents,
                patent_ratings=patent_ratings,
            )

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
                        json.dumps(sol.get("referencedPatents", [])),
                        0,
                    ),
                )

            # 增量更新：创新方向
            await _update_problem_modeling(
                db, task_id, enriched_description, analysis_result, "agent3", extra_data={"solutions": solutions}
            )

            update_workflow_step(
                db,
                task_id,
                "agent3",
                "completed",
                description=f"生成 {len(solutions)} 个创新方案",
                output=json.dumps(solutions, ensure_ascii=False),
            )

            # 暂停等待用户确认方案
            if start_from != "agent1":
                db.execute("UPDATE workflows SET status=? WHERE task_id=?", ("awaiting_rating", task_id))
                db.execute(
                    "UPDATE tasks SET status='pending', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
                    (task_id,),
                )
                db.commit()
                logger.debug(f"Step 4 completed for task_id={task_id}, pausing for user confirmation")
                return

        # Step 5: 方案评估 - AI评估方案
        if _is_step_pending(db, task_id, "agent4"):
            update_workflow_step(db, task_id, "agent4", "running")

            # 获取该任务的所有solution_id
            solution_rows = db.execute("SELECT id, title FROM solutions WHERE task_id=?", (task_id,)).fetchall()
            solution_id_map = {row["title"]: row["id"] for row in solution_rows}

            # 读取方案数据（可能刚生成，也可能已存在）
            solutions_data = []
            if solution_rows:
                for row in solution_rows:
                    solutions_data.append({"title": row["title"]})

            evaluations = []
            for sol in solutions_data:
                eval_result = await engine.evaluate(sol.get("description", "") or sol.get("title", ""))
                evaluations.append(
                    {
                        "solution_title": sol.get("title", ""),
                        "evaluation": eval_result,
                    }
                )

                # 获取对应的solution_id
                sol_id = solution_id_map.get(sol.get("title", ""), 0)

                if eval_result and "scores" in eval_result:
                    scores = eval_result["scores"]
                    overall = eval_result.get("overall", 0)
                    # Compute average of all dimension scores for evolution_alignment
                    dim_scores_list = []
                    for _, sd in scores.items():
                        if isinstance(sd, dict):
                            dim_scores_list.append(sd.get("score", 0))
                        else:
                            dim_scores_list.append(sd)
                    avg_score = sum(dim_scores_list) / len(dim_scores_list) if dim_scores_list else 0

                    for dim, score_data in scores.items():
                        if isinstance(score_data, dict):
                            score_val = score_data.get("score", 0)
                        else:
                            score_val = score_data
                        db.execute(
                            """INSERT INTO evaluations
                               (solution_id, user_id, dimension, score, details, status,
                                root_cause_cut, original_contradiction_resolved,
                                new_contradictions, function_deficits_filled,
                                new_harmful_interactions, ifr_distance, ifr_gap_description,
                                ifr_parameters_achieved, overall_verdict, evolution_alignment,
                                aligned_laws, misaligned_laws, maturity, confidence)
                               VALUES (?, ?, ?, ?, ?, 'completed',
                                       0, 0, '[]', '[]', '[]', 'medium', '', '[]',
                                       CASE WHEN ? >= 70 THEN 'passed' ELSE 'failed' END,
                                       ?, '[]', '[]', '概念阶段', ?)""",
                            (sol_id, user_id, dim, score_val, json.dumps(eval_result),
                             overall, avg_score, None),
                        )

            # 增量更新：评估分数
            await _update_problem_modeling(
                db, task_id, task_description, analysis_result, "agent4", extra_data={"evaluations": evaluations}
            )

            update_workflow_step(
                db,
                task_id,
                "agent4",
                "completed",
                description=f"评估 {len(evaluations)} 个方案",
                output=json.dumps(evaluations, ensure_ascii=False),
            )

            # 暂停等待用户确认评估结果
            if start_from != "agent1":
                db.execute("UPDATE workflows SET status=? WHERE task_id=?", ("awaiting_rating", task_id))
                db.execute(
                    "UPDATE tasks SET status='pending', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
                    (task_id,),
                )
                db.commit()
                logger.debug(f"Step 5 completed for task_id={task_id}, pausing for user confirmation")
                return

        # Step 6: 成果转化 - 生成完整报告
        if _is_step_pending(db, task_id, "agent6"):
            update_workflow_step(db, task_id, "agent6", "running")

            try:
                # 收集前面所有步骤的数据
                innovations = []
                patent_info = []
                solutions_data = []
                evaluations = []

                row_steps = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
                if row_steps:
                    all_steps = json.loads(row_steps["steps"])
                    agent2 = next((s for s in all_steps if s["agent_id"] == "agent2"), None)
                    if agent2 and agent2.get("output"):
                        try:
                            agent2_out = json.loads(agent2["output"])
                            innovations = agent2_out.get("innovations", [])
                        except Exception:
                            pass

                    agent5 = next((s for s in all_steps if s["agent_id"] == "agent5"), None)
                    if agent5 and agent5.get("output"):
                        try:
                            agent5_out = json.loads(agent5["output"])
                            if isinstance(agent5_out, dict):
                                patent_info = agent5_out.get("patents", [])
                            else:
                                patent_info = agent5_out
                        except Exception:
                            pass

                # 读取方案和评估
                sol_rows = db.execute("SELECT title, description FROM solutions WHERE task_id=?", (task_id,)).fetchall()
                solutions_data = [{"title": r["title"], "description": r["description"] or ""} for r in sol_rows]

                eval_rows = db.execute(
                    """SELECT e.dimension, e.score, s.title as solution_title
                       FROM evaluations e JOIN solutions s ON e.solution_id = s.id
                       WHERE s.task_id=?""",
                    (task_id,),
                ).fetchall()
                if eval_rows:
                    eval_map = {}
                    for er in eval_rows:
                        st = er["solution_title"]
                        if st not in eval_map:
                            eval_map[st] = {"solution_title": st, "evaluation": {"scores": {}, "overall": 0}}
                        eval_map[st]["evaluation"]["scores"][er["dimension"]] = er["score"]
                    evaluations = list(eval_map.values())
                    for ev in evaluations:
                        scores = ev["evaluation"].get("scores", {})
                        if scores:
                            ev["evaluation"]["overall"] = round(sum(scores.values()) / len(scores), 1)

                # 生成报告
                engine = ZRIPMEngine()
                report = await engine.generate_report(
                    task_description, innovations, patent_info, solutions_data, evaluations
                )

                update_workflow_step(
                    db,
                    task_id,
                    "agent6",
                    "completed",
                    description=report.get("title", "分析报告"),
                    output=json.dumps(report, ensure_ascii=False),
                )
            except Exception as e:
                logger.error(f"报告生成失败: {e}")
                update_workflow_step(
                    db,
                    task_id,
                    "agent6",
                    "completed",
                    description="报告生成异常",
                    output=json.dumps(
                        {
                            "title": "分析报告",
                            "summary": f"报告生成失败: {e}",
                            "sections": [],
                            "recommendations": [],
                            "topSolutions": [],
                        }
                    ),
                )

        # 更新任务状态
        db.execute(
            "UPDATE tasks SET status='completed', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
            (task_id,),
        )
        db.commit()

    except Exception as e:
        logger.error(f"Background task failed for task_id={task_id}: {e}")
        db.execute(
            "UPDATE tasks SET status='failed', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
            (task_id,),
        )
        db.commit()

        try:
            row = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
            if row:
                steps = json.loads(row["steps"])
                for step in steps:
                    if step["status"] == "running":
                        update_workflow_step(db, task_id, step["agent_id"], "failed", description=f"执行失败: {str(e)}")
                        break
        except Exception:
            pass

    finally:
        _running_workflows.discard(task_id)
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
        "message": "success",
        "code": 200,
    }


class TriggerAnalysisInput(BaseModel):
    knowledgeBaseIds: list[str] | None = None
    startFrom: str | None = None  # 从指定步骤开始，用于失败任务继续执行


@router.post("/{task_id}/trigger")
async def trigger_analysis(
    task_id: int, body: TriggerAnalysisInput | None = None, user: dict = Depends(get_current_user)
):
    db = get_db()

    task = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()

    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    existing = db.execute("SELECT * FROM analyses WHERE task_id=?", (task_id,)).fetchone()

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
        "UPDATE tasks SET status='analyzing', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?", (task_id,)
    )
    db.commit()

    existing_workflow = db.execute("SELECT id FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not existing_workflow:
        create_workflow(db, task_id)

    db.close()

    # 后台启动分析（支持从指定步骤开始）
    kb_ids = body.knowledgeBaseIds if body else None
    start_from = body.startFrom if body and body.startFrom else "agent1"

    if start_from != "agent1":
        # 从指定步骤继续，使用 run_analysis_background
        task_obj = asyncio.create_task(
            run_analysis_background(task_id, user["id"], task["description"], kb_ids, start_from=start_from)
        )
    else:
        # 从头开始，使用 run_demand_portrait
        task_obj = asyncio.create_task(run_demand_portrait(task_id, user["id"], task["description"], kb_ids))

    _background_tasks.add(task_obj)
    _task_map[task_id] = task_obj
    task_obj.add_done_callback(lambda t: _cleanup_task(task_id, t))

    return {
        "data": {
            "id": str(task_id),
            "taskId": str(task_id),
            "status": "analyzing",
        },
        "message": "分析已启动",
        "code": 200,
    }


@router.post("/{task_id}/cancel")
def cancel_analysis(task_id: int, user: dict = Depends(get_current_user)):
    """取消正在运行的任务分析"""
    # 验证任务归属
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    if task["status"] not in ("analyzing",):
        db.close()
        raise HTTPException(status_code=400, detail="当前任务不在分析中，无法取消")

    # 取消 asyncio Task（如果有）
    background_task = _task_map.pop(task_id, None)
    if background_task and not background_task.done():
        background_task.cancel()

    # 清理运行锁
    _running_workflows.discard(task_id)

    # 更新 DB：task → failed, workflow 当前步骤 → failed
    db.execute(
        "UPDATE tasks SET status='failed', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
        (task_id,),
    )

    wf = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if wf:
        steps = json.loads(wf["steps"])
        for step in steps:
            if step["status"] == "running":
                step["status"] = "failed"
                step["description"] = "用户手动取消"
                break
        db.execute("UPDATE workflows SET status='failed', steps=? WHERE task_id=?", (json.dumps(steps), task_id))

    db.commit()
    db.close()

    logger.info(f"Task {task_id} cancelled by user {user['id']}")
    return {"data": {"status": "cancelled"}, "message": "分析已取消", "code": 200}


class ProceedInput(BaseModel):
    ratings: list[dict] | None = None


@router.post("/{task_id}/proceed")
async def proceed_workflow(task_id: int, body: ProceedInput | None = None, user: dict = Depends(get_current_user)):
    """用户评分后，继续执行后续工作流步骤"""
    db = get_db()

    task = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    wf = db.execute("SELECT * FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not wf:
        db.close()
        raise HTTPException(status_code=400, detail="工作流未启动")

    if wf["status"] != "awaiting_rating":
        db.close()
        raise HTTPException(status_code=400, detail="工作流当前不需要评分")

    # 在 db.close() 之前读取所有需要的数据
    wf_steps = wf["steps"]
    task_desc = task["description"]
    user_id = user["id"]

    # 保存评分到刚完成的步骤 output 中
    if body and body.ratings:
        steps = json.loads(wf_steps) if isinstance(wf_steps, str) else wf_steps
        # 找到最后一个 completed 的步骤，把评分存进去
        completed_step = None
        for step in reversed(steps):
            if step["status"] == "completed" and step.get("output"):
                completed_step = step
                break
        if completed_step:
            try:
                output = json.loads(completed_step["output"])
                output["ratings"] = body.ratings
                completed_step["output"] = json.dumps(output, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                pass
        db.execute(
            "UPDATE workflows SET steps=? WHERE task_id=?",
            (json.dumps(steps), task_id),
        )
        db.commit()

    # 找下一个待执行的步骤（使用已读取的数据）
    # 同时检查 pending 和 stuck running 状态
    next_agent = None
    agent_phases = ["agent2", "agent5", "agent3", "agent4", "agent6"]
    steps = json.loads(wf_steps) if isinstance(wf_steps, str) else wf_steps
    for agent_id in agent_phases:
        step = next((s for s in steps if s["agent_id"] == agent_id), None)
        if step and step["status"] in ("pending", "running"):
            next_agent = agent_id
            break

    if not next_agent:
        db.close()
        return {"data": {"status": "done"}, "message": "所有步骤已完成", "code": 200}

    # 设置 workflow 状态为 running，让前端显示加载状态
    db.execute(
        "UPDATE workflows SET status='running' WHERE task_id=?",
        (task_id,),
    )
    db.commit()
    db.close()

    # 启动后台任务执行下一步
    remaining = asyncio.create_task(run_analysis_background(task_id, user_id, task_desc, None, start_from=next_agent))
    _background_tasks.add(remaining)
    _task_map[task_id] = remaining
    remaining.add_done_callback(lambda t: _cleanup_task(task_id, t))

    return {
        "data": {"status": "proceeding"},
        "message": "继续执行后续步骤",
        "code": 200,
    }


@router.post("/{task_id}/retry")
async def retry_workflow(task_id: int, user: dict = Depends(get_current_user)):
    """重试失败的步骤，从失败处重新执行"""
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    wf = db.execute("SELECT * FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not wf:
        db.close()
        raise HTTPException(status_code=400, detail="工作流未启动")

    steps = json.loads(wf["steps"])
    failed_step = None
    for step in steps:
        if step["status"] == "failed":
            failed_step = step
            break

    if not failed_step:
        db.close()
        raise HTTPException(status_code=400, detail="没有失败的步骤需要重试")

    reset = False
    for step in steps:
        if step["agent_id"] == failed_step["agent_id"]:
            reset = True
        if reset:
            step["status"] = "pending"
            step["started_at"] = None
            step["completed_at"] = None
            step["duration"] = None
            step["output"] = None

    db.execute(
        "UPDATE workflows SET status='running', steps=? WHERE task_id=?",
        (json.dumps(steps), task_id),
    )
    db.execute(
        "UPDATE tasks SET status='analyzing', updated_at=to_char(NOW(), 'YYYY-MM-DD HH24:MI:SS') WHERE id=?",
        (task_id,),
    )
    db.commit()
    db.close()

    remaining = asyncio.create_task(
        run_analysis_background(task_id, user["id"], task["description"], start_from=failed_step["agent_id"])
    )
    _background_tasks.add(remaining)
    _task_map[task_id] = remaining
    remaining.add_done_callback(lambda t: _cleanup_task(task_id, t))

    return {
        "data": {"status": "retrying", "retryFrom": failed_step["agent_id"]},
        "message": "正在重试",
        "code": 200,
    }
