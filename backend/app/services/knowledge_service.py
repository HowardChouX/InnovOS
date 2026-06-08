"""
知识库业务逻辑层 — 借鉴 CherryStudio RAG 架构
"""
import json
from app.database import get_db


class KnowledgeService:
    """知识库服务"""

    @staticmethod
    def list_docs(user_id: int, q: str = "", category: str = "", page: int = 1, page_size: int = 20):
        db = get_db()
        params = [user_id]
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
            "data": [KnowledgeService._row_to_doc(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def search(user_id: int, query: str, limit: int = 10):
        """知识检索（当前为 LIKE 检索，后续升级为 RAG）"""
        db = get_db()
        if query:
            rows = db.execute(
                """SELECT id, title, content, category, tags, source, doc_type, updated_at,
                   (CASE WHEN title LIKE ? THEN 3 ELSE 0 END +
                    CASE WHEN content LIKE ? THEN 1 ELSE 0 END) as relevance
                   FROM knowledge_docs
                   WHERE user_id=? AND is_active=1 AND (title LIKE ? OR content LIKE ?)
                   ORDER BY relevance DESC, updated_at DESC LIMIT ?""",
                (f"%{query}%", f"%{query}%", user_id, f"%{query}%", f"%{query}%", limit),
            ).fetchall()
        else:
            rows = db.execute(
                """SELECT id, title, content, category, tags, source, doc_type, updated_at
                   FROM knowledge_docs
                   WHERE user_id=? AND is_active=1
                   ORDER BY updated_at DESC LIMIT ?""",
                (user_id, limit),
            ).fetchall()
        db.close()

        return [KnowledgeService._row_to_doc(r) for r in rows]

    @staticmethod
    def create_doc(user_id: int, data: dict) -> dict:
        db = get_db()
        cursor = db.execute(
            """INSERT INTO knowledge_docs (title, content, category, tags, source, doc_type, user_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (data["title"], data.get("content", ""), data.get("category", "未分类"),
             json.dumps(data.get("tags", [])), data.get("source", ""), data.get("doc_type", "text"), user_id),
        )
        db.commit()
        row = db.execute("SELECT * FROM knowledge_docs WHERE id=?", (cursor.lastrowid,)).fetchone()
        db.close()
        return KnowledgeService._row_to_doc(row)

    @staticmethod
    def update_doc(doc_id: int, user_id: int, data: dict) -> dict | None:
        db = get_db()
        row = db.execute(
            "SELECT * FROM knowledge_docs WHERE id=? AND user_id=?", (doc_id, user_id)
        ).fetchone()
        if not row:
            db.close()
            return None

        updates, params = [], []
        for field in ["title", "content", "category", "source"]:
            if field in data and data[field] is not None:
                updates.append(f"{field} = ?")
                params.append(data[field])
        if "tags" in data:
            updates.append("tags = ?")
            params.append(json.dumps(data["tags"]))

        if updates:
            updates.append("updated_at = datetime('now')")
            params.extend([doc_id, user_id])
            db.execute(f"UPDATE knowledge_docs SET {', '.join(updates)} WHERE id = ? AND user_id = ?", params)
            db.commit()

        row = db.execute("SELECT * FROM knowledge_docs WHERE id=?", (doc_id,)).fetchone()
        db.close()
        return KnowledgeService._row_to_doc(row)

    @staticmethod
    def delete_doc(doc_id: int, user_id: int) -> bool:
        db = get_db()
        row = db.execute("SELECT id FROM knowledge_docs WHERE id=? AND user_id=?", (doc_id, user_id)).fetchone()
        if not row:
            db.close()
            return False
        db.execute("DELETE FROM knowledge_docs WHERE id=? AND user_id=?", (doc_id, user_id))
        db.commit()
        db.close()
        return True

    @staticmethod
    def list_categories(user_id: int):
        db = get_db()
        rows = db.execute(
            "SELECT category, COUNT(*) as count FROM knowledge_docs WHERE user_id=? GROUP BY category",
            (user_id,),
        ).fetchall()
        db.close()
        return [{"name": r["category"], "count": r["count"]} for r in rows]

    @staticmethod
    def _row_to_doc(r) -> dict:
        tags_raw = r["tags"]
        if isinstance(tags_raw, str):
            try:
                tags_raw = json.loads(tags_raw)
            except (json.JSONDecodeError, TypeError):
                tags_raw = []
        return {
            "id": str(r["id"]),
            "title": r["title"],
            "content": r["content"],
            "category": r["category"],
            "tags": tags_raw if isinstance(tags_raw, list) else [],
            "source": r["source"],
            "docType": r["doc_type"],
            "isActive": bool(r["is_active"]),
            "createdAt": r["created_at"],
            "updatedAt": r["updated_at"],
        }
