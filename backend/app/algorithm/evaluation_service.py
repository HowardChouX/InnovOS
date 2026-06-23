"""
AI Evaluation Service — 四维方案评估
"""

import json
import logging

from app.algorithm.ai_client import chat_completion

logger = logging.getLogger(__name__)

EVALUATION_SYSTEM_PROMPT = """你是一名专业的创新方案评估专家。请从以下四个维度对创新方案进行全面评估：

1. 创新性 (innovation)：技术新颖度、专利避障能力、技术进化趋势符合度
2. 可行性 (feasibility)：技术可实现性、成本可控性、资源可用性
3. 完整性 (completeness)：推理链完整度、跨领域验证、风险评估全面性
4. 转化潜力 (conversion)：产业契合度、市场化难度、转化周期预期

请严格按照以下 JSON 格式返回评估结果（不要包含 markdown 代码块标记）：
{
  "innovation": {"score": 0-100, "strengths": ["优势1", "优势2"], "weaknesses": ["不足1", "不足2"]},
  "feasibility": {"score": 0-100, "strengths": [], "weaknesses": []},
  "completeness": {"score": 0-100, "strengths": [], "weaknesses": []},
  "conversion": {"score": 0-100, "strengths": [], "weaknesses": []},
  "overall": 0-100,
  "recommendations": ["建议1", "建议2"]
}"""


async def evaluate_solution(solution_id: int, user_id: int) -> dict:
    """对方案进行 AI 四维评估

    Args:
        solution_id: 方案ID
        user_id: 用户ID

    Returns:
        包含 scores, overall, strengths, weaknesses, recommendations 的评估结果

    Raises:
        ValueError: 方案不存在时抛出
        RuntimeError: AI调用失败时抛出
    """
    from app.database import get_db

    db = get_db()
    try:
        row = db.execute(
            """SELECT s.id, s.title, s.description, s.principles, s.patent_references,
                      t.title as task_title, t.description as task_description
               FROM solutions s
               JOIN tasks t ON s.task_id = t.id
               WHERE s.id=? AND s.user_id=?""",
            (solution_id, user_id),
        ).fetchone()
    finally:
        db.close()

    if not row:
        raise ValueError("方案不存在")

    solution = dict(row)
    user_prompt = f"""请评估以下创新方案：

任务描述：{solution.get("task_description", "")}

方案名称：{solution.get("title", "")}
方案描述：{solution.get("description", "")}
创新原理：{solution.get("principles", "[]")}
专利参考：{solution.get("patent_references", "[]")}"""

    try:
        result = await chat_completion(
            system_prompt=EVALUATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            response_format=dict,
        )

        scores = result.get("innovation", {}).get("score", 0)
        feasibility = result.get("feasibility", {}).get("score", 0)
        completeness = result.get("completeness", {}).get("score", 0)
        conversion = result.get("conversion", {}).get("score", 0)
        overall = result.get("overall", 0)

        # Store evaluation in DB
        db = get_db()
        try:
            avg_score = (scores + feasibility + completeness + conversion) / 4
            db.execute(
                """INSERT INTO evaluations
                   (solution_id, user_id, dimension, score, details, status,
                    root_cause_cut, original_contradiction_resolved,
                    new_contradictions, function_deficits_filled,
                    new_harmful_interactions, ifr_distance, ifr_gap_description,
                    ifr_parameters_achieved, overall_verdict, evolution_alignment,
                    aligned_laws, misaligned_laws, maturity, confidence)
                   VALUES (?,?,?,?,?,'completed',0,0,'[]','[]','[]','medium','','[]',
                           CASE WHEN ? >= 70 THEN 'passed' ELSE 'failed' END,
                           ?, '[]','[]','概念阶段',?)""",
                (
                    solution_id,
                    user_id,
                    "comprehensive",
                    overall,
                    json.dumps(result, ensure_ascii=False),
                    overall,
                    avg_score,
                    0.3,
                ),
            )
            db.commit()
        finally:
            db.close()

        # Return in the format expected by the API
        return {
            "scores": {
                "innovation": scores,
                "feasibility": feasibility,
                "completeness": completeness,
                "conversion": conversion,
            },
            "overall": overall,
            "strengths": (
                result.get("innovation", {}).get("strengths", []) + result.get("feasibility", {}).get("strengths", [])
            ),
            "weaknesses": (
                result.get("innovation", {}).get("weaknesses", [])
                + result.get("completeness", {}).get("weaknesses", [])
            ),
            "recommendations": result.get("recommendations", []),
        }

    except ValueError:
        raise
    except Exception as e:
        logger.error(f"AI评估失败: {e}", exc_info=True)
        raise RuntimeError(f"AI评估失败: {e}") from e
