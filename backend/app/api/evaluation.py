import json

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


def _row_to_dict(r):
    """转换评估记录为字典（包含智枢完整评估维度）"""
    return {
        "id": str(r["id"]),
        "solutionId": str(r["solution_id"]),
        "dimension": r["dimension"],
        "score": r["score"],
        "details": json.loads(r["details"]),
        "status": r["status"],
        "createdAt": r["created_at"],
        # 智枢评估维度
        "rootCauseCut": bool(r["root_cause_cut"]),
        "originalContradictionResolved": bool(r["original_contradiction_resolved"]),
        "newContradictions": json.loads(r["new_contradictions"]),
        "functionDeficitsFilled": json.loads(r["function_deficits_filled"]),
        "newHarmfulInteractions": json.loads(r["new_harmful_interactions"]),
        "ifrDistance": r["ifr_distance"],
        "ifrGapDescription": r["ifr_gap_description"],
        "ifrParametersAchieved": json.loads(r["ifr_parameters_achieved"]),
        "overallVerdict": r["overall_verdict"],
        "evolutionAlignment": r["evolution_alignment"],
        "alignedLaws": json.loads(r["aligned_laws"]),
        "misalignedLaws": json.loads(r["misaligned_laws"]),
        "maturity": r["maturity"],
        "confidence": r["confidence"],
    }


@router.post("/{solution_id}")
async def evaluate_solution(solution_id: int, user: dict = Depends(get_current_user)):
    """对方案进行 AI 四维评估"""
    db = get_db()
    sol = db.execute(
        "SELECT id FROM solutions WHERE id=? AND user_id=?",
        (solution_id, user["id"]),
    ).fetchone()
    if not sol:
        db.close()
        raise HTTPException(status_code=404, detail="方案不存在")

    # Check for existing evaluation
    existing = db.execute(
        "SELECT * FROM evaluations WHERE solution_id=? AND user_id=? ORDER BY created_at DESC LIMIT 1",
        (solution_id, user["id"]),
    ).fetchone()

    db.close()

    if existing:
        return {"data": _row_to_dict(existing), "message": "success", "code": 200}

    # Run AI evaluation
    try:
        from app.algorithm.evaluation_service import evaluate_solution as ai_evaluate

        result = await ai_evaluate(solution_id, user["id"])
        return {
            "data": {
                "solution_title": str(sol["id"]),
                "evaluation": {
                    "scores": result["scores"],
                    "overall": result["overall"],
                    "strengths": result["strengths"],
                    "weaknesses": result["weaknesses"],
                    "recommendations": result["recommendations"],
                },
            },
            "message": "success",
            "code": 200,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.error(f"AI evaluation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"评估失败: {str(e)}") from e


@router.get("/{solution_id}/history")
def get_evaluation_history(solution_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM evaluations WHERE solution_id=? AND user_id=? ORDER BY created_at DESC",
        (solution_id, user["id"]),
    ).fetchall()
    db.close()
    return {
        "data": [_row_to_dict(r) for r in rows],
        "message": "success",
        "code": 200,
    }


@router.get("/{solution_id}/latest")
def get_latest_evaluation(solution_id: int, user: dict = Depends(get_current_user)):
    """获取最新评估结果（智枢完整维度）"""
    db = get_db()
    row = db.execute(
        """SELECT * FROM evaluations
           WHERE solution_id=? AND user_id=?
           ORDER BY created_at DESC LIMIT 1""",
        (solution_id, user["id"]),
    ).fetchone()
    db.close()

    if not row:
        raise HTTPException(status_code=404, detail="No evaluation found")

    return {
        "data": _row_to_dict(row),
        "message": "success",
        "code": 200,
    }
