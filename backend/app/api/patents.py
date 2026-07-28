"""
专利检索 API — PatentHub 主数据源 + 本地数据库降级
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patents", tags=["patents"])


@router.get("/search")
async def search(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    ipc_code: str = "",
    applicant: str = "",
    source: str = "local",  # local | patenthub（默认本地数据库）
):
    """
    专利搜索接口（默认本地数据库，可选 PatentHub）。

    支持 PatentHub 搜索语法（source=patenthub 时）：
      q=title:石墨烯 AND ipc:H01M
      q=summary:电池热管理
      q=applicant:华为
    """
    if not q.strip():
        # 无关键词时返回全部本地专利（分页）
        db = get_db()
        try:
            total_row = db.execute("SELECT COUNT(*) AS cnt FROM patents").fetchone()
            total = total_row["cnt"] if total_row else 0
            offset = (page - 1) * page_size
            rows = db.execute(
                "SELECT * FROM patents ORDER BY relevance_score DESC LIMIT ? OFFSET ?",
                (page_size, offset),
            ).fetchall()
        finally:
            db.close()
        items = [_row_to_patent_dict(r) for r in rows]
        return {
            "data": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
            "message": "success",
            "code": 200,
        }

    try:
        if source == "patenthub":
            # PatentHub 外部数据源
            query = q.strip()
            if ipc_code.strip():
                query = f"{query} AND ipc:{ipc_code.strip()}"
            if applicant.strip():
                query = f"{query} AND applicant:{applicant.strip()}"

            from app.algorithm.patent_hub_client import search_patents as ph_search

            result = await ph_search(
                q=query,
                page=page,
                page_size=min(page_size, 50),
            )
            items = result.get("patents", [])
            total = result.get("total", 0)
        else:
            # 本地数据库搜索（默认）
            from app.algorithm.patent_service import _local_like_search

            items = _local_like_search(q.strip(), [q.strip()])
            total = len(items)

    except Exception as e:
        logger.error(f"专利检索异常: {e}")
        raise HTTPException(status_code=502, detail=f"专利检索服务暂时不可用: {e}") from e

    return {
        "data": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "message": "success",
        "code": 200,
    }


def _row_to_patent_dict(r) -> dict:
    """将 patents 表行转为前端期望的字典格式"""
    import json as _json

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

    ipc_codes = r["ipc_codes"]
    if isinstance(ipc_codes, str):
        try:
            ipc_codes = _json.loads(ipc_codes)
        except (ValueError, TypeError):
            ipc_codes = [ipc_codes] if ipc_codes else []

    return {
        "id": r["id"],
        "title": r["title"],
        "summary": r["abstract"] or "",
        "abstract": r["abstract"] or "",
        "applicant": ", ".join(applicants) if isinstance(applicants, list) else str(applicants),
        "inventor": ", ".join(inventors) if isinstance(inventors, list) else str(inventors),
        "applicants": applicants if isinstance(applicants, list) else [applicants] if applicants else [],
        "inventors": inventors if isinstance(inventors, list) else [inventors] if inventors else [],
        "mainIpc": ipc_codes[0] if isinstance(ipc_codes, list) and ipc_codes else "",
        "ipc": ", ".join(ipc_codes) if isinstance(ipc_codes, list) else "",
        "ipcCodes": ipc_codes if isinstance(ipc_codes, list) else [],
        "legalStatus": "",
        "type": "",
        "documentNumber": r["patent_number"] or "",
        "patentNumber": r["patent_number"] or "",
        "patent_number": r["patent_number"] or "",
        "relevance_score": r["relevance_score"] or 0,
        "relevance": r["relevance_score"] or 0,
        "relevanceScore": r["relevance_score"] or 0,
        "filingDate": r["filing_date"] or "",
        "filing_date": r["filing_date"] or "",
        "publicationDate": r["publication_date"] or "",
        "publication_date": r["publication_date"] or "",
        "applicationDate": r["filing_date"] or "",
        "documentDate": r["publication_date"] or "",
        "source": "local",
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
        raise HTTPException(status_code=502, detail=f"专利详情服务暂时不可用: {e}") from e

    if not patent:
        raise HTTPException(status_code=404, detail="未找到该专利详情")

    return {
        "data": patent,
        "message": "success",
        "code": 200,
    }
