"""
专利检索 API — PatentHub 主数据源 + 本地数据库降级
"""

import logging

from fastapi import APIRouter, Query, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patents", tags=["patents"])


@router.get("/search")
async def search(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    ipc_code: str = "",
    applicant: str = "",
    source: str = "patenthub",  # patenthub | local
):
    """
    专利搜索接口（PatentHub 为主数据源）。

    支持 PatentHub 搜索语法：
      q=title:石墨烯 AND ipc:H01M
      q=summary:电池热管理
      q=applicant:华为
    """
    if not q.strip():
        return {
            "data": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
            "message": "请输入搜索关键词",
            "code": 200,
        }

    # 构建 PatentHub 查询
    query = q.strip()
    if ipc_code.strip():
        query = f"{query} AND ipc:{ipc_code.strip()}"
    if applicant.strip():
        query = f"{query} AND applicant:{applicant.strip()}"

    try:
        if source == "local":
            # 本地数据库搜索
            from app.algorithm.patent_service import _local_like_search

            items = _local_like_search(q.strip(), [q.strip()])
            total = len(items)
        else:
            # PatentHub 主数据源
            from app.algorithm.patent_hub_client import search_patents as ph_search

            result = await ph_search(
                q=query,
                page=page,
                page_size=min(page_size, 50),
            )
            items = result.get("patents", [])
            total = result.get("total", 0)

    except Exception as e:
        logger.error(f"专利检索异常: {e}")
        raise HTTPException(status_code=502, detail=f"专利检索服务暂时不可用: {e}")

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
    """获取专利详情（PatentHub 优先，本地数据库兜底）"""
    if not pid.strip():
        raise HTTPException(status_code=400, detail="缺少专利 ID")

    try:
        from app.algorithm.patent_service import get_patent_detail

        patent = await get_patent_detail(pid.strip())
    except Exception as e:
        logger.error(f"获取专利详情异常: {e}")
        raise HTTPException(status_code=502, detail=f"专利详情服务暂时不可用: {e}")

    if not patent:
        raise HTTPException(status_code=404, detail="未找到该专利详情")

    return {
        "data": patent,
        "message": "success",
        "code": 200,
    }
