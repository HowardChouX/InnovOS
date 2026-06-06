import json
from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user
from app.database import get_db
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class CreateDocInput(BaseModel):
    title: str
    content: str
    category: str = "未分类"
    tags: list[str] = []
    source: str = ""
    doc_type: str = "text"


class UpdateDocInput(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    source: Optional[str] = None
    is_active: Optional[int] = None


def row_to_doc(r):
    return {
        "id": str(r["id"]),
        "title": r["title"],
        "content": r["content"],
        "category": r["category"],
        "tags": json.loads(r["tags"]),
        "source": r["source"],
        "docType": r["doc_type"],
        "isActive": bool(r["is_active"]),
        "createdAt": r["created_at"],
        "updatedAt": r["updated_at"],
    }


@router.get("/docs")
def list_docs(
    user: dict = Depends(get_current_user),
    category: str = "",
    q: str = "",
    page: int = 1,
    page_size: int = 20,
):
    db = get_db()
    params: list = [user["id"]]
    where = "user_id = ?"

    if category:
        where += " AND category = ?"
        params.append(category)
    if q:
        where += " AND (title LIKE ? OR content LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    total = db.execute(f"SELECT COUNT(*) FROM knowledge_docs WHERE {where}", params).fetchone()[0]
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM knowledge_docs WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?",
        [*params, page_size, offset],
    ).fetchall()
    db.close()

    return {
        "data": [row_to_doc(r) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
        "message": "success",
        "code": 200,
    }


@router.post("/docs")
def create_doc(body: CreateDocInput, user: dict = Depends(get_current_user)):
    db = get_db()
    cursor = db.execute(
        """INSERT INTO knowledge_docs (title, content, category, tags, source, doc_type, user_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (body.title, body.content, body.category, json.dumps(body.tags), body.source, body.doc_type, user["id"]),
    )
    db.commit()
    row = db.execute("SELECT * FROM knowledge_docs WHERE id=?", (cursor.lastrowid,)).fetchone()
    db.close()
    return {"data": row_to_doc(row), "message": "success", "code": 200}


@router.get("/docs/{doc_id}")
def get_doc(doc_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute(
        "SELECT * FROM knowledge_docs WHERE id=? AND user_id=?",
        (doc_id, user["id"]),
    ).fetchone()
    db.close()
    if not row:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"data": row_to_doc(row), "message": "success", "code": 200}


@router.put("/docs/{doc_id}")
def update_doc(doc_id: int, body: UpdateDocInput, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute(
        "SELECT * FROM knowledge_docs WHERE id=? AND user_id=?",
        (doc_id, user["id"]),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="文档不存在")

    updates = []
    params: list = []
    if body.title is not None:
        updates.append("title = ?")
        params.append(body.title)
    if body.content is not None:
        updates.append("content = ?")
        params.append(body.content)
    if body.category is not None:
        updates.append("category = ?")
        params.append(body.category)
    if body.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(body.tags))
    if body.source is not None:
        updates.append("source = ?")
        params.append(body.source)
    if body.is_active is not None:
        updates.append("is_active = ?")
        params.append(body.is_active)

    if updates:
        updates.append("updated_at = datetime('now')")
        params.extend([doc_id, user["id"]])
        db.execute(
            f"UPDATE knowledge_docs SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            params,
        )
        db.commit()

    row = db.execute("SELECT * FROM knowledge_docs WHERE id=?", (doc_id,)).fetchone()
    db.close()
    return {"data": row_to_doc(row), "message": "success", "code": 200}


@router.delete("/docs/{doc_id}")
def delete_doc(doc_id: int, user: dict = Depends(get_current_user)):
    db = get_db()
    row = db.execute(
        "SELECT * FROM knowledge_docs WHERE id=? AND user_id=?",
        (doc_id, user["id"]),
    ).fetchone()
    if not row:
        db.close()
        raise HTTPException(status_code=404, detail="文档不存在")

    db.execute("DELETE FROM knowledge_docs WHERE id=? AND user_id=?", (doc_id, user["id"]))
    db.commit()
    db.close()
    return {"data": None, "message": "deleted", "code": 200}


@router.get("/categories")
def list_categories(user: dict = Depends(get_current_user)):
    db = get_db()
    rows = db.execute(
        "SELECT category, COUNT(*) as count FROM knowledge_docs WHERE user_id=? GROUP BY category",
        (user["id"],),
    ).fetchall()
    db.close()

    categories = []
    for r in rows:
        categories.append({
            "name": r["category"],
            "count": r["count"],
        })

    return {"data": categories, "message": "success", "code": 200}


@router.get("/search")
def search_knowledge(
    user: dict = Depends(get_current_user),
    q: str = "",
    limit: int = 10,
):
    """知识检索（用于RAG增强）"""
    db = get_db()
    if q:
        rows = db.execute(
            """SELECT id, title, content, category, tags, source, doc_type, updated_at,
               (CASE WHEN title LIKE ? THEN 3 ELSE 0 END +
                CASE WHEN content LIKE ? THEN 1 ELSE 0 END) as relevance
               FROM knowledge_docs
               WHERE user_id=? AND is_active=1 AND (title LIKE ? OR content LIKE ?)
               ORDER BY relevance DESC, updated_at DESC
               LIMIT ?""",
            (f"%{q}%", f"%{q}%", user["id"], f"%{q}%", f"%{q}%", limit),
        ).fetchall()
    else:
        rows = db.execute(
            """SELECT id, title, content, category, tags, source, doc_type, updated_at
               FROM knowledge_docs
               WHERE user_id=? AND is_active=1
               ORDER BY updated_at DESC LIMIT ?""",
            (user["id"], limit),
        ).fetchall()
    db.close()

    results = []
    for r in rows:
        results.append({
            "id": str(r["id"]),
            "title": r["title"],
            "content": r["content"],
            "category": r["category"],
            "tags": json.loads(r["tags"]),
            "source": r["source"],
            "docType": r["doc_type"],
            "relevance": r.get("relevance", 0),
            "updatedAt": r["updated_at"],
        })

    return {"data": results, "total": len(results), "message": "success", "code": 200}
