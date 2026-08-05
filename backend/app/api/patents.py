"""
专利检索 API — 纯本地数据库

专利搜索与详情均基于本地 PostgreSQL patents 表，
不再对接任何外部专利 API。
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.algorithm.patent_service import (
    get_patent_detail,
    row_to_patent_dict,
)
from app.database import db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patents", tags=["patents"])

# 排序字段/方向白名单，禁止直接拼接客户端输入
_SORT_COLUMNS = {
    "relevance_score": "relevance_score",
    "filing_date": "filing_date",
    "publication_date": "publication_date",
    "created_at": "created_at",
}
_SORT_DIRECTIONS = {"asc": "ASC", "desc": "DESC"}


@router.get("/search")
async def search(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    ipc_code: str = "",
    applicant: str = "",
    sort_by: str = "relevance_score",
    order: str = "desc",
):
    """
    本地专利搜索。

    支持关键词（title/abstract）、IPC 分类号、申请人筛选，
    排序字段与方向白名单校验，分页总数与列表使用相同筛选条件。
    """
    conditions: list[str] = []
    params: list[str] = []

    keyword = q.strip()
    if keyword:
        conditions.append("(title LIKE ? OR abstract LIKE ?)")
        like = f"%{keyword}%"
        params.extend([like, like])
    if ipc_code.strip():
        conditions.append("ipc_codes LIKE ?")
        params.append(f"%{ipc_code.strip()}%")
    if applicant.strip():
        conditions.append("applicants LIKE ?")
        params.append(f"%{applicant.strip()}%")

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    order_dir = _SORT_DIRECTIONS.get(order.strip().lower(), "DESC")
    order_col = _SORT_COLUMNS.get(sort_by.strip(), "relevance_score")
    offset = (page - 1) * page_size

    try:
        with db_session() as db:
            total_row = db.execute(f"SELECT COUNT(*) AS cnt FROM patents {where_clause}", params).fetchone()
            total = total_row["cnt"] if total_row else 0
            rows = db.execute(
                f"SELECT * FROM patents {where_clause} ORDER BY {order_col} {order_dir} LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            ).fetchall()
    except Exception as e:
        logger.error(f"专利检索异常: {e}")
        raise HTTPException(status_code=502, detail="专利检索服务暂时不可用") from e

    items = [row_to_patent_dict(r) for r in rows]
    return {
        "data": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "message": "success",
        "code": 200,
    }


@router.get("/detail/{pid}")
async def detail(pid: str):
    """获取专利详情（本地数据库，按内部 ID、专利号或公开号查找）"""
    if not pid.strip():
        raise HTTPException(status_code=400, detail="缺少专利 ID")

    try:
        patent = get_patent_detail(pid.strip())
    except Exception as e:
        logger.error(f"获取专利详情异常: {e}")
        raise HTTPException(status_code=502, detail="专利详情服务暂时不可用") from e

    if not patent:
        raise HTTPException(status_code=404, detail="未找到该专利")

    return {
        "data": patent,
        "message": "success",
        "code": 200,
    }
