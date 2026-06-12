import json
from fastapi import APIRouter, Depends, Query
from app.database import get_db
from app.auth import get_current_user
from typing import Optional

router = APIRouter(prefix="/api/patents", tags=["patents"])


def row_to_patent(r):
    return {
        "id": str(r["id"]), "title": r["title"], "abstract": r["abstract"],
        "applicants": json.loads(r["applicants"]), "inventors": json.loads(r["inventors"]),
        "filingDate": r["filing_date"], "publicationDate": r["publication_date"],
        "patentNumber": r["patent_number"], "ipcCodes": json.loads(r["ipc_codes"]),
        "relevanceScore": r["relevance_score"],
    }


@router.get("/search")
def search_patents(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ipc_code: str = "",
    applicant: str = "",
    sort_by: str = "relevance",  # relevance | date | score
    order: str = "desc",  # desc | asc
):
    """
    专利检索（支持分页、过滤、排序）
    """
    db = get_db()
    
    # 构建 WHERE 条件
    conditions = []
    params = []
    
    if q:
        conditions.append("(title LIKE ? OR abstract LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])
    
    if ipc_code:
        conditions.append("ipc_codes LIKE ?")
        params.append(f"%{ipc_code}%")
    
    if applicant:
        conditions.append("applicants LIKE ?")
        params.append(f"%{applicant}%")
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    # 排序
    sort_map = {
        "relevance": "relevance_score",
        "date": "filing_date",
        "score": "relevance_score",
    }
    sort_column = sort_map.get(sort_by, "relevance_score")
    sort_order = "DESC" if order == "desc" else "ASC"
    
    # 查询总数
    count_sql = f"SELECT COUNT(*) FROM patents {where_clause}"
    total = db.execute(count_sql, params).fetchone()[0]
    
    # 分页查询
    offset = (page - 1) * page_size
    sql = f"""
        SELECT * FROM patents
        {where_clause}
        ORDER BY {sort_column} {sort_order}
        LIMIT ? OFFSET ?
    """
    rows = db.execute(sql, [*params, page_size, offset]).fetchall()
    db.close()
    
    return {
        "data": [row_to_patent(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "message": "success",
        "code": 200,
    }


@router.get("/{patent_id}")
def get_patent_detail(patent_id: int):
    """
    获取专利详情
    """
    db = get_db()
    row = db.execute("SELECT * FROM patents WHERE id=?", (patent_id,)).fetchone()
    db.close()
    
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="专利不存在")
    
    return {"data": row_to_patent(row), "message": "success", "code": 200}


@router.get("/stats")
def get_patent_stats():
    db = get_db()
    total = db.execute("SELECT COUNT(*) FROM patents").fetchone()[0]
    rows = db.execute("SELECT * FROM patents ORDER BY relevance_score DESC LIMIT 3").fetchall()
    db.close()
    return {
        "data": {
            "totalCount": total,
            "relatedCount": total,
            "coreCount": min(36, total),
            "analyzedCount": min(36, total),
            "topPatents": [row_to_patent(r) for r in rows],
        },
        "message": "success", "code": 200,
    }


@router.get("/semantic-search")
async def semantic_search(
    q: str = "",
    top_k: int = Query(10, ge=1, le=50),
    user: dict = Depends(get_current_user),
):
    """语义检索相似专利（RAG 向量搜索）"""
    if not q.strip():
        return {"data": [], "total": 0}

    from app.services.patent_rag_service import PatentRagService
    svc = PatentRagService()
    results = await svc.search(q, top_k=top_k)

    # 补充专利元数据
    if results:
        patent_ids = [r["patentId"] for r in results if r["patentId"]]
        if patent_ids:
            db = get_db()
            placeholders = ",".join("?" * len(patent_ids))
            rows = db.execute(
                f"SELECT * FROM patents WHERE id IN ({placeholders})",
                patent_ids,
            ).fetchall()
            db.close()
            patent_map = {str(r["id"]): r for r in rows}
            for r in results:
                pid = r["patentId"]
                if pid in patent_map:
                    p = patent_map[pid]
                    r["title"] = p["title"]
                    r["patentNumber"] = p["patent_number"]

    return {"data": results, "total": len(results)}
