"""成果转化 API — 专利侵权风险分析 + 规避设计建议"""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException

from app.algorithm.ai_client import chat_completion
from app.algorithm.base import parse_ai_json
from app.auth import get_current_user
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/conversion", tags=["conversion"])

INFRINGEMENT_SYSTEM = """你是一个专利侵权分析专家。分析解决方案与参考专利之间的侵权风险。

分析要求：
1. 仔细对比解决方案的技术特征与专利的技术方案
2. 识别可能侵权的技术点（全面覆盖原则、等同原则）
3. 评估侵权风险等级
4. 给出具体的规避设计建议

返回JSON格式：
{
  "riskLevel": "高/中/低",
  "riskScore": 0-100,
  "analysisSummary": "总体分析结论",
  "claimOverlaps": [
    {"feature": "解决方案中的技术特征", "patentClaim": "专利对应的权利要求", "risk": "风险描述", "suggestion": "修改建议"}
  ],
  "designArounds": ["规避设计建议1", "规避设计建议2", ...],
  "keyRecommendations": ["关键建议1", "关键建议2", ...]
}"""


def _get_solution_data(db, solution_id: int, user_id: int) -> dict | None:
    """获取方案和关联的专利信息"""
    row = db.execute(
        """SELECT s.*, t.user_id FROM solutions s
           JOIN tasks t ON s.task_id = t.id
           WHERE s.id = ?""",
        (solution_id,),
    ).fetchone()
    if not row or row["user_id"] != user_id:
        return None
    return {
        "id": row["id"],
        "task_id": row["task_id"],
        "title": row["title"],
        "description": row["description"],
        "patent_references": json.loads(row["patent_references"]),
    }


def _get_patent_details(db, task_id: int, patent_titles: list[str]) -> list[dict]:
    """从 workflow agent5 输出中获取专利详细信息"""
    wf = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if not wf:
        return []
    steps = json.loads(wf["steps"])
    agent5 = next((s for s in steps if s["agent_id"] == "agent5"), None)
    if not agent5 or not agent5.get("output"):
        return []
    try:
        output = json.loads(agent5["output"])
        patents = output.get("patents", []) if isinstance(output, dict) else output
    except (json.JSONDecodeError, TypeError):
        return []

    if not patent_titles:
        return patents[:10]  # fallback: return recent patents

    matched = []
    for p in patents:
        title = (p.get("title") or p.get("_title") or "").strip()
        if any(pt.strip() in title or title in pt.strip() for pt in patent_titles):
            matched.append(p)
    return matched


@router.get("/{task_id}")
async def get_conversion_data(task_id: int, user: dict = Depends(get_current_user)):
    """获取成果转化页面所需的所有数据"""
    db = get_db()

    # 验证任务归属
    task = db.execute("SELECT * FROM tasks WHERE id=? AND user_id=?", (task_id, user["id"])).fetchone()
    if not task:
        db.close()
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取方案
    solutions = db.execute("SELECT * FROM solutions WHERE task_id=?", (task_id,)).fetchall()

    # 获取评估数据
    eval_rows = db.execute(
        """SELECT e.solution_id, e.dimension, e.score, e.details
           FROM evaluations e
           JOIN solutions s ON e.solution_id = s.id
           WHERE s.task_id=?""",
        (task_id,),
    ).fetchall()

    # 获取 workflow 中 agent5 的专利数据
    patent_details: list[dict] = []
    wf = db.execute("SELECT steps FROM workflows WHERE task_id=?", (task_id,)).fetchone()
    if wf:
        steps = json.loads(wf["steps"])
        agent5 = next((s for s in steps if s["agent_id"] == "agent5"), None)
        if agent5 and agent5.get("output"):
            try:
                output = json.loads(agent5["output"])
                patent_details = output.get("patents", []) if isinstance(output, dict) else []
            except (json.JSONDecodeError, TypeError):
                pass

    db.close()

    # 组织方案数据
    solution_list = []
    for s in solutions:
        # 匹配该方案的评估分数
        solution_eval = {}
        for er in eval_rows:
            if er["solution_id"] == s["id"]:
                solution_eval[er["dimension"]] = er["score"]

        patent_refs = json.loads(s["patent_references"])

        # 匹配专利详情
        ref_patents = []
        for pr in patent_refs:
            for pd in patent_details:
                pd_title = (pd.get("title") or pd.get("_title") or "").strip()
                if pr.strip() in pd_title or pd_title in pr.strip():
                    ref_patents.append(pd)
                    break

        solution_list.append(
            {
                "id": str(s["id"]),
                "title": s["title"],
                "description": s["description"],
                "principles": json.loads(s["principles"]),
                "confidenceScore": s["confidence_score"],
                "patentReferences": patent_refs,
                "refPatents": ref_patents,
                "rating": s["rating"],
                "evaluation": solution_eval,
            }
        )

    return {
        "data": {
            "taskId": str(task["id"]),
            "taskTitle": task["title"],
            "taskDescription": task["description"],
            "solutions": solution_list,
        },
        "message": "success",
        "code": 200,
    }


@router.post("/{solution_id}/check-infringement")
async def check_infringement(solution_id: int, user: dict = Depends(get_current_user)):
    """AI 侵权风险分析"""
    db = get_db()
    sol = _get_solution_data(db, solution_id, user["id"])
    if not sol:
        db.close()
        raise HTTPException(status_code=404, detail="方案不存在")

    task_id = sol["task_id"]
    patent_titles = sol["patent_references"]

    # 获取专利详情
    patents = _get_patent_details(db, task_id, patent_titles)
    db.close()

    if not patents:
        return {
            "data": {
                "riskLevel": "无法分析",
                "riskScore": 0,
                "analysisSummary": "未找到关联的专利信息，无法进行侵权分析",
                "claimOverlaps": [],
                "designArounds": [],
                "keyRecommendations": ["请确保该方案有关联的参考专利数据"],
            },
            "message": "success",
            "code": 200,
        }

    # 构建分析上下文
    patent_context_parts = []
    for i, p in enumerate(patents, 1):
        patent_context_parts.append(
            f"专利{i}: {p.get('title') or p.get('_title') or '未知'}\n"
            f"  专利号: {p.get('patent_number', '未知')}\n"
            f"  申请人: {p.get('applicants', '未知')}\n"
            f"  摘要: {(p.get('abstract') or p.get('description', '') or '')[:500]}"
        )

    user_prompt = f"""【解决方案】
标题：{sol["title"]}
描述：{sol["description"] or "无详细描述"}

【参考专利】
{chr(10).join(patent_context_parts)}

请分析该解决方案与以上专利的侵权风险，给出规避设计建议。"""

    try:
        result = await chat_completion(
            user_id=user["id"],
            purpose="conversion",
            messages=[
                {"role": "system", "content": INFRINGEMENT_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        parsed = parse_ai_json((result.get("content") or "").strip())
        if not isinstance(parsed, dict):
            parsed = {"riskLevel": "分析失败", "riskScore": 0, "analysisSummary": (result.get("content") or "").strip()}
        return {"data": parsed, "message": "success", "code": 200}
    except Exception as e:
        logger.warning(f"AI 侵权分析失败（返回友好提示）: {e}")
        return {
            "data": {
                "riskLevel": "无法分析",
                "riskScore": 0,
                "analysisSummary": f"AI 分析服务暂不可用（{str(e)[:80]}），请确认已配置可用的对话模型",
                "claimOverlaps": [],
                "designArounds": [],
                "keyRecommendations": ["配置 AI 模型服务后重新分析"],
            },
            "message": "success",
            "code": 200,
        }
