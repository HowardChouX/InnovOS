import json
from fastapi import APIRouter, Query
from app.database import get_db

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
def search_patents(q: str = ""):
    db = get_db()
    if q:
        rows = db.execute(
            "SELECT * FROM patents WHERE title LIKE ? OR abstract LIKE ? ORDER BY relevance_score DESC LIMIT 20",
            (f"%{q}%", f"%{q}%"),
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM patents ORDER BY relevance_score DESC LIMIT 5").fetchall()
    db.close()
    return {"data": [row_to_patent(r) for r in rows], "total": len(rows), "message": "success", "code": 200}


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
