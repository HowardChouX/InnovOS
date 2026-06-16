import json
from fastapi import APIRouter, Depends, Query
from app.database import get_db, is_postgres
from app.auth import get_current_user
from typing import Optional

router = APIRouter(prefix="/api/patents", tags=["patents"])


def row_to_patent(r, relevance=None):
    return {
        "id": str(r["id"]), "title": r["title"], "abstract": r["abstract"],
        "applicants": json.loads(r["applicants"]), "inventors": json.loads(r["inventors"]),
        "filingDate": r["filing_date"], "publicationDate": r["publication_date"],
        "patentNumber": r["patent_number"], "ipcCodes": json.loads(r["ipc_codes"]),
        "relevanceScore": round(relevance * 100) if relevance is not None else r["relevance_score"],
    }


async def _hybrid_search(query: str, all_rows: list) -> dict:
    """混合搜索：合并关键词结果和向量结果，去重后用 Reranker 精排，归一化到 0~1"""
    try:
        from app.algorithm.model_resolver import model_resolver
        from app.algorithm.knowledge.reranker import Reranker

        cfg = model_resolver.resolve_rerank()
        if not cfg:
            composite = model_resolver.get_assigned_settings().get("rerank_model")
            if composite:
                cfg = model_resolver.resolve(composite)

        if not all_rows or not cfg:
            return {}

        reranker = Reranker(api_key=cfg.api_key, api_host=cfg.api_host, model=cfg.model_id)
        documents = [f"{r['title']}。{r['abstract'] or ''}" for r in all_rows]
        results = await reranker.rerank(query, documents, top_n=len(all_rows))

        if not results:
            return {}

        score_map = {}
        for item in results:
            idx = item["index"]
            patent_id = all_rows[idx]["id"]
            score_map[patent_id] = item["relevance_score"]
        return score_map
    except Exception as e:
        print(f"[WARN] 混合搜索失败: {e}", flush=True)
        import traceback; traceback.print_exc()
        return {}


@router.get("/search")
async def search_patents(
    q: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    ipc_code: str = "",
    applicant: str = "",
    sort_by: str = "relevance",  # relevance | date | score
    order: str = "desc",  # desc | asc
):
    """
    混合专利检索：关键词 LIKE + 向量语义召回 → Reranker 精排 → 归一化
    """
    db = get_db()

    if not q.strip():
        # 无搜索词，直接返回全部
        conditions = []
        params = []
        if ipc_code:
            conditions.append("ipc_codes LIKE ?")
            params.append(f"%{ipc_code}%")
        if applicant:
            conditions.append("applicants LIKE ?")
            params.append(f"%{applicant}%")
        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        sort_map = {"relevance": "relevance_score", "date": "filing_date", "score": "relevance_score"}
        sort_column = sort_map.get(sort_by, "relevance_score")
        sort_order = "DESC" if order == "desc" else "ASC"

        count_sql = f"SELECT COUNT(*) FROM patents {where_clause}"
        total = db.execute(count_sql, params).fetchone()[0]
        offset = (page - 1) * page_size
        rows = db.execute(
            f"SELECT * FROM patents {where_clause} ORDER BY {sort_column} {sort_order} LIMIT ? OFFSET ?",
            [*params, page_size, offset],
        ).fetchall()
        db.close()
        return {
            "data": [row_to_patent(r) for r in rows],
            "total": total, "page": page, "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
            "message": "success", "code": 200,
        }

    # === 混合搜索 ===

    # 1. 关键词召回
    keyword_rows = db.execute(
        "SELECT * FROM patents WHERE title LIKE ? OR abstract LIKE ?",
        [f"%{q}%", f"%{q}%"],
    ).fetchall()
    keyword_ids = {r["id"] for r in keyword_rows}

    # 2. 向量语义召回（top-20，扩展候选集）
    vector_rows_map = {}
    try:
        from app.algorithm.patent_search_engine import PatentSearchEngine
        engine = PatentSearchEngine()
        if engine.embedder:
            vec_results = await engine.search(q, top_k=20)
            for vr in vec_results:
                pid = vr.get("id")
                if pid and pid not in keyword_ids:
                    # 从 DB 补全完整信息
                    full = db.execute("SELECT * FROM patents WHERE id=?", (pid,)).fetchone()
                    if full:
                        vector_rows_map[pid] = full
    except Exception as e:
        print(f"[WARN] 向量召回失败: {e}", flush=True)

    db.close()

    # 3. 合并 → Reranker 精排 → 归一化
    all_rows = list(keyword_rows) + list(vector_rows_map.values())
    relevance_map = await _hybrid_search(q, all_rows)

    # 4. 按相关度排序，取前 5，分页返回
    scored = [(r, relevance_map.get(r["id"], 0)) for r in all_rows]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_results = scored[:5]
    total = len(scored)
    start = (page - 1) * page_size
    page_rows = top_results[start:start + page_size]

    return {
        "data": [row_to_patent(r, score) for r, score in page_rows],
        "total": len(top_results), "page": page, "page_size": page_size,
        "total_pages": 1,
        "message": "success", "code": 200,
    }


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
        "message": "success",
        "code": 200,
    }


@router.get("/{patent_id}")
def get_patent_detail(patent_id: int):
    db = get_db()
    row = db.execute("SELECT * FROM patents WHERE id=?", (patent_id,)).fetchone()
    db.close()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="专利不存在")
    return {"data": row_to_patent(row), "message": "success", "code": 200}
