"""
统一专利检索服务 — PatentHub 主数据源 + 本地数据库降级
自动关键词提取 → 查询生成 → 相关度评分 → 结果合并
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import get_db

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
#  统一检索入口
# ══════════════════════════════════════════════════════════

async def patent_search(
    innovations: list[dict],
    task_description: str = "",
    max_results: int = 50,
) -> dict[str, Any]:
    """
    统一专利检索：PatentHub 主数据源 + 本地数据库降级。

    Args:
        innovations: 创新方向列表（含 description, user_rating）
        task_description: 任务描述（用于 fallback）
        max_results: 最大返回数

    Returns:
        {
            "patents": list[dict],         # 专利列表（含 relevance_score）
            "direction_patents": dict,      # 创新方向 → 专利标题映射
            "source": str,                  # "patenthub" | "local" | "mixed"
            "total_found": int,
        }
    """
    patent_info: list[dict] = []
    direction_patents: dict[str, list[str]] = {}
    source = "patenthub"

    # ── 1. 尝试 PatentHub 智能搜索 ──
    try:
        from app.algorithm.patent_search_optimizer import optimized_patent_search

        if innovations:
            logger.info(f"PatentHub 智能搜索: {len(innovations)} 个创新方向")
            patent_info = await optimized_patent_search(innovations, max_results=max_results)
        else:
            # 无创新方向，用任务描述兜底
            from app.algorithm.patent_hub_client import search_patents as ph_search

            logger.info("无创新方向数据，使用任务描述进行 PatentHub 搜索")
            fallback_result = await ph_search(
                q=f"title:{task_description[:30]}", page_size=10
            )
            patent_info = fallback_result.get("patents", [])

        # 按创新方向分组
        for patent in patent_info:
            source_inn = patent.get("source_innovation", "")
            if source_inn:
                direction_patents.setdefault(source_inn, []).append(
                    patent.get("title", "未命名专利")
                )

        logger.info(f"PatentHub 搜索完成: 找到 {len(patent_info)} 条相关专利")

    except Exception as e:
        logger.warning(f"PatentHub 专利检索失败: {e}")

        # ── 2. 降级到本地数据库 ──
        try:
            logger.info("降级到本地数据库搜索...")
            patent_keywords = [
                inn.get("description", "")[:30] for inn in (innovations or [])
            ][:3]
            if not patent_keywords:
                patent_keywords = [task_description[:50]]

            patent_info = _local_like_search(task_description, patent_keywords)
            source = "local"
            logger.info(f"本地数据库搜索完成: 找到 {len(patent_info)} 条相关专利")
        except Exception as fallback_e:
            logger.warning(f"本地数据库搜索也失败: {fallback_e}")
            source = "none"

    return {
        "patents": patent_info,
        "direction_patents": direction_patents,
        "source": source,
        "total_found": len(patent_info),
    }


# ══════════════════════════════════════════════════════════
#  本地数据库降级搜索
# ══════════════════════════════════════════════════════════

def _local_like_search(task_description: str, keywords: list[str]) -> list[dict]:
    """
    本地数据库 LIKE 搜索（降级策略）。
    在已上传的专利中进行关键词匹配。
    """
    import json as _json

    db = get_db()
    try:
        or_conditions = []
        params = []
        for kw in keywords[:3]:
            like = f"%{kw}%"
            or_conditions.append("(title LIKE ? OR abstract LIKE ?)")
            params.extend([like, like])

        if not or_conditions:
            return []

        sql = f"SELECT * FROM patents WHERE {' OR '.join(or_conditions)} ORDER BY created_at DESC LIMIT 10"
        rows = db.execute(sql, params).fetchall()
    finally:
        db.close()

    results = []
    for r in rows:
        applicants = r["applicants"]
        if isinstance(applicants, str):
            try:
                applicants = _json.loads(applicants)
            except (ValueError, TypeError):
                applicants = [applicants] if applicants else []

        inventors = r["inventors"]
        if isinstance(inventors, str):
            try:
                inventors = _json.loads(inventors)
            except (ValueError, TypeError):
                inventors = [inventors] if inventors else []

        results.append({
            "id": r["id"],
            "title": r["title"],
            "summary": r["abstract"] or "",
            "applicant": ", ".join(applicants) if isinstance(applicants, list) else str(applicants),
            "inventor": ", ".join(inventors) if isinstance(inventors, list) else str(inventors),
            "mainIpc": "",
            "ipc": "",
            "legalStatus": "",
            "type": "",
            "documentNumber": r["patent_number"] or "",
            "relevance_score": 0.5,
            "source": "local",
        })

    return results


# ══════════════════════════════════════════════════════════
#  专利详情获取（统一接口）
# ══════════════════════════════════════════════════════════

async def get_patent_detail(patent_id: str) -> dict[str, Any] | None:
    """
    获取专利完整详情（PatentHub 优先，本地数据库兜底）。
    """
    # 优先从 PatentHub 获取
    try:
        from app.algorithm.patent_hub_client import get_patent_full

        patent = await get_patent_full(patent_id)
        if patent:
            patent["source"] = "patenthub"
            return patent
    except Exception as e:
        logger.warning(f"PatentHub 获取详情失败(id={patent_id}): {e}")

    # 降级到本地数据库
    return _get_local_patent(patent_id)


def _get_local_patent(patent_id: str) -> dict[str, Any] | None:
    """从本地数据库获取专利详情"""
    import json as _json

    db = get_db()
    try:
        row = db.execute("SELECT * FROM patents WHERE id = ?", [patent_id]).fetchone()
    finally:
        db.close()

    if not row:
        return None

    applicants = row["applicants"]
    if isinstance(applicants, str):
        try:
            applicants = _json.loads(applicants)
        except (ValueError, TypeError):
            applicants = [applicants] if applicants else []

    inventors = row["inventors"]
    if isinstance(inventors, str):
        try:
            inventors = _json.loads(inventors)
        except (ValueError, TypeError):
            inventors = [inventors] if inventors else []

    ipc_codes = row["ipc_codes"]
    if isinstance(ipc_codes, str):
        try:
            ipc_codes = _json.loads(ipc_codes)
        except (ValueError, TypeError):
            ipc_codes = [ipc_codes] if ipc_codes else []

    return {
        "id": str(row["id"]),
        "title": row["title"],
        "summary": row["abstract"] or "",
        "applicant": ", ".join(applicants) if isinstance(applicants, list) else str(applicants),
        "inventor": ", ".join(inventors) if isinstance(inventors, list) else str(inventors),
        "mainIpc": ipc_codes[0] if isinstance(ipc_codes, list) and ipc_codes else "",
        "ipc": ", ".join(ipc_codes) if isinstance(ipc_codes, list) else "",
        "legalStatus": "",
        "type": "",
        "documentNumber": row["patent_number"] or "",
        "claims": row["claims"] or "",
        "description": row["description"] or "",
        "source": "local",
    }
