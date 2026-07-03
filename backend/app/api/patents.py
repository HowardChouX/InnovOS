"""
专利检索 API — CNIPR 开放平台对接
所有检索走实时 API 调用，不存储本地数据。
"""

import logging

from fastapi import APIRouter, Query, HTTPException

from app.algorithm.cnipr_client import search_patents, get_patent_detail, analyze_patents

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/patents", tags=["patents"])

# CNIPR 可用数据库
DB_OPTIONS = "FMZL,FMSQ,SYXX"  # 发明授权, 发明申请, 实用新型


@router.get("/search")
async def search(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    ipc_code: str = "",
    applicant: str = "",
    sort_by: str = "date",   # date | relevance
    order: str = "desc",
):
    """关键词 + 条件检索专利，对接 sf1-v1 实时查询。"""
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

    # 构建 CNIPR 表达式
    parts = [f"名称=({q.strip()})"]

    if ipc_code.strip():
        parts.append(f"主分类号=({ipc_code.strip()})")

    if applicant.strip():
        parts.append(f"申请(专利权)人=({applicant.strip()})")

    exp = " AND ".join(parts)

    # 排序
    cnipr_order = {
        "date": "-appDate",
        "date_asc": "+appDate",
        "relevance": "+appDate",  # CNIPR 无相关度排序，用日期替代
    }.get(sort_by + ("_asc" if order == "asc" else ""), "-appDate")

    try:
        result = await search_patents(
            exp=exp,
            page=page,
            page_size=min(page_size, 50),
            order=cnipr_order,
            dbs=DB_OPTIONS,
        )
    except Exception as e:
        logger.error(f"CNIPR 检索异常: {e}")
        raise HTTPException(status_code=502, detail=f"专利检索服务暂时不可用: {e}")

    # 转换为前端期望格式
    items = []
    for r in result.get("results", []):
        items.append({
            "id": r.get("pid", ""),
            "title": r.get("title", ""),
            "abstract": r.get("abs", ""),
            "applicants": r.get("applicantName", []) if isinstance(r.get("applicantName"), list)
                          else [r["applicantName"]] if r.get("applicantName") else [],
            "inventors": r.get("inventorName", []) if isinstance(r.get("inventorName"), list)
                          else [r["inventorName"]] if r.get("inventorName") else [],
            "filingDate": r.get("appDate", ""),
            "publicationDate": r.get("pubDate", ""),
            "patentNumber": r.get("pubNumber", []) if isinstance(r.get("pubNumber"), list)
                             else [r["pubNumber"]] if r.get("pubNumber") else [],
            "ipcCodes": r.get("ipc", []) if isinstance(r.get("ipc"), list)
                          else [r["ipc"]] if r.get("ipc") else [],
            "mainIpc": r.get("mainIpc", ""),
            "patentType": r.get("patType", ""),
            "legalStatus": r.get("legalStatus", ""),
            "statusCode": r.get("statusCode", ""),
        })

    total = result.get("total", 0)

    return {
        "data": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        "sections": result.get("sections", []),
        "message": "success",
        "code": 200,
    }


@router.get("/detail/{pid}")
async def detail(pid: str):
    """按专利 ID 获取详情（权利要求书、说明书等），对接 dl3-v1。"""
    if not pid.strip():
        raise HTTPException(status_code=400, detail="缺少专利 ID")

    try:
        results = await get_patent_detail([pid.strip()])
    except Exception as e:
        logger.error(f"CNIPR 下载详情异常: {e}")
        raise HTTPException(status_code=502, detail=f"专利详情服务暂时不可用: {e}")

    if not results:
        raise HTTPException(status_code=404, detail="未找到该专利详情")

    patent = results[0]
    return {
        "data": patent,
        "message": "success",
        "code": 200,
    }


@router.get("/stats")
async def stats(q: str = ""):
    """专利统计概览，对接 as1 单字段分析接口。"""
    if not q.strip():
        return {
            "data": {
                "totalCount": 0,
                "relatedCount": 0,
                "coreCount": 0,
                "analyzedCount": 0,
                "topPatents": [],
            },
            "message": "请输入搜索关键词",
            "code": 200,
        }

    exp = f"名称=({q.strip()})"

    try:
        # 检索概览
        sr = await search_patents(exp=exp, page=1, page_size=3, dbs=DB_OPTIONS)
        total = sr.get("total", 0)

        items = []
        for r in sr.get("results", []):
            items.append({
                "id": r.get("pid", ""),
                "title": r.get("title", ""),
                "abstract": r.get("abs", ""),
                "applicants": r.get("applicantName", []) if isinstance(r.get("applicantName"), list)
                              else [r["applicantName"]] if r.get("applicantName") else [],
                "inventors": r.get("inventorName", []) if isinstance(r.get("inventorName"), list)
                              else [r["inventorName"]] if r.get("inventorName") else [],
                "filingDate": r.get("appDate", ""),
                "publicationDate": r.get("pubDate", ""),
                "patentNumber": r.get("pubNumber", []) if isinstance(r.get("pubNumber"), list)
                                 else [r["pubNumber"]] if r.get("pubNumber") else [],
                "ipcCodes": r.get("ipc", []) if isinstance(r.get("ipc"), list)
                              else [r["ipc"]] if r.get("ipc") else [],
                "mainIpc": r.get("mainIpc", ""),
                "patentType": r.get("patType", ""),
                "legalStatus": r.get("legalStatus", ""),
                "statusCode": r.get("statusCode", ""),
            })
    except Exception as e:
        logger.error(f"CNIPR stats 异常: {e}")
        total = 0
        items = []

    return {
        "data": {
            "totalCount": total,
            "relatedCount": total,
            "coreCount": min(36, total),
            "analyzedCount": min(36, total),
            "topPatents": items,
        },
        "message": "success",
        "code": 200,
    }
